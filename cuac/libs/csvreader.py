#/usr/bin/env python


import csv
import os
import os.path

from itertools import count, chain, repeat, izip
from collections import defaultdict
from copy import copy

from cuac.libs.pathfinder import FileSource
from cuac.libs.fields import FieldMap, IntField
from cuac.libs.meta import *


class CSVMeta(Meta):

    """Metadatos para objeto extraido de CSV.

    Amplia el Meta basico con algunos campos necesarios
    para hacer seguimiento de la jerarquia.
    """

    def __init__(self, path, parent=None):
        super(CSVMeta, self).__init__(parent)
        self.fields["PK"] = IntField(indexable=True)
        self.path = path
        self.subtypes = dict()
        self.blocks = list()

    def __getstate__(self):
        """Guardo todo menos el rootset, que se recrea cada vez"""
        state = dict(self.__dict__)
        state['rootset'] = None
        return state

    def __setstate__(self, state):
        self.__dict__.update(state)

    def child(self, name):
        """Devuelve un tipo hijo, creandolo si es necesario"""
        try:
            return self.subtypes[name]
        except KeyError:
            submeta = CSVMeta(".".join((self.path, name)), self)
            self.fields[name] = CSVDataSetField(submeta)
            return self.subtypes.setdefault(name, submeta)

    def process(self, warnings=None, lazy=False):
        """fuerza el proceso de un bloque cargado en modo lazy"""
        if hasattr(self, "blocks"):
            blocks = self.blocks
            del(self.blocks) # Para que no se vuelva a ejecutar
            for blk in blocks:
                blk.process(self.rootset, warnings=warnings)
        # He detectado casos en que un meta puede no tener bloques, 
        # pero aun asi puede tener submetas sin procesar. Es un caso raro, pero
        # se da... tengo que sacar este "if lazy" fuera del "hasattr" porque,
        # si no, los datos no se cargan correctamente.
        if not lazy:
            for subtype in self.subtypes.values():
                subtype.process(warnings=warnings, lazy=lazy)


class CSVDataObject(DataObject):

    PK = 0

    def __init__(self, meta, parent=None):
        cls = CSVDataObject
        super(cls, self).__init__(meta, parent)
        self.PK = cls.next()

    @classmethod
    def next(cls):
        pk = cls.PK+1
        cls.PK = pk
        return pk


def flip(self):
    """Da la vuelta a un enlace (cambia las POSITION)"""
    for item in self:
        item.POSITION, item.PEER.POSITION = item.PEER.POSITION, item.POSITION


def split(self, attrib, new_attrib):
    """Divide los enlaces en funcion del valor de un campo"""
    meta = self.__dict__.get('_meta', None)
    if meta:
        meta.fields[new_attrib] = Field()
    new_items, dummy = [], [None]
    for item in self:
        for value in item.get(attrib, dummy):
            new_item = copy(item)
            setattr(new_item, new_attrib, value)
            if item.PEER:
                new_item.PEER = copy(item.PEER)
                setattr(new_item.PEER, new_attrib, value)
            new_items.append(new_item)
    return self._new(meta, new_items, False)


def merge(self, key):
    """Combina varios enlaces en funcion del valor de una clave"""
    meta = self.__dict__.get('_meta', None)
    if meta:
        meta.fields[meta.path[-1]] = CSVDataSetField(meta)
    keys, values = dict(), list()
    for item in self:
        keys.setdefault(key(item), []).append(item)
    for itemlist in keys.values():
        if len(itemlist) == 1:
            values.append(itemlist[0])
        else:
            return self._new(meta, values, False)


class CSVDataSet(DataSet):

    """Incluye la funcion "FLIP", para darle la vuelta a los enlaces"""
    FLIP  = flip
    SPLIT = split

    def _new(self, meta, items=None, indexable=False):
        if meta:
            return CSVDataSet(meta, items, indexable)
        else:
            return CSVPeerSet(items)

    def update(self, items):
        assert(not hasattr(self, '_indexes'))
        self._children.update(items)

    def add(self, item):
        assert(not hasattr(self, '_indexes'))
        self._children.add(item)

    def pop(self):
        assert(not hasattr(self, '_indexes'))
        item = self._children.pop()


class CSVPeerSet(PeerSet):

    """Incluye la funcion "FLIP", para darle la vuelta a los enlaces"""
    FLIP = flip
    SPLIT = split

    def _new(self, meta, items, indexable=False):
        if meta:
            return CSVDataSet(meta, items, indexable)
        return CSVPeerSet(items)


class CSVObjectField(ObjectField):
    
    def _new(self, items=None, indexable=False):
        if self.meta:
            return CSVDataSet(self.meta, items, indexable)
        return CSVPeerSet(items)



class DictField(ObjectField):

    """Campo diccionario
    
    El campo es un diccionario formado por multiples columnas
    que contribuyen al mismo objeto.
    """

    def collect(self, dset, attr):
        """Devuelve un dict donde cada entrada es el compendio de entradas"""
        sumup = defaultdict(set)
        items = (item.get(attr) for item in dset._children)
        items = (x for x in items if x)
        for item in items:
            for key, val in item.iteritems():
                sumup[key].add(val)
        # Convierto el resultado en un dict de BaseSets,
        # para hacerlo inmutable.
        return dict((key, BaseSet(val)) for key, val in sumup.iteritems())


class CSVDataSetField(DataSetField):

    def _new(self, items=None, indexable=True):
        """Crea objetos de tipo CSVDataSet"""
        if self.meta:
            return CSVDataSet(self.meta, items, indexable)
        return CSVPeerSet(items)

    def collect(self, dset, attrib):
        #
        # Recopilo los datos del meta actual en la jerarquia, pero
        # con lazy=True me aseguro de que no va a profundizar y recolectar
        # los datos de otros nodos hijo. Esto hay que hacerlo asi porque
        # se me han dado casos como el siguiente:
        #
        # - sedes_fo se procesa.
        # - la recursion (!lazy) se dispara, y empieza a procesarse
        #   el primer hijo (sedes_fo.pilas)
        # - durante el proceso, sedes_fo.pilas hace busquedas y dispara la
        #   funcion "collect" de CSVDataSet, sobre sedes_fo.
        # - sedes_fo ya no tiene bloques, asi que no procesa bloques. Pero
        #   si que vuelve a disparar (!lazy), y vuelve a invocar "process"
        #   en sedes_fo.pilas
        # - sedes_fo.pilas tampoco tiene ya bloques (ha ejecutado el
        #   del(self.blocks), asi que salta directamente al (!lazy)
        #   sedes_fo.pilas.interfaces empieza a procesarse antes de que
        #   termine sedes_fo.pilas.
        #
        # Es un caso muy jodido. Lo que hago es evitar que se procesen los
        # sub-campos cuando no hace falta, con lazy=True.
        #
        self.meta.process(lazy=True)
        return super(CSVDataSetField, self).collect(dset, attrib)


class CSVRow(object):

    """Fila de un fichero CSV"""

    __slots__ = ("lineno", "cols")

    def __init__(self, lineno, cols):
        self.lineno = lineno
        self.cols = cols

    @staticmethod
    def normalize(lineno, rows, columns, warnings):
        """Normaliza los datos de las filas en funcion del tipo
        
        Si se le pasa un array de warnings, el formato de los warnings que
        devuelve son tuplas (numero de linea, lista de warnings)
        """
        # Normalizamos todas las columnas menos los alias (evitamos
        # normalizarlas dos veces)
        columns = tuple((col.index, col.coltype.convert)
                        for col in columns if not col.canonical)
        errors  = list()
        minlen  = max(x[0] for x in columns) + 1;
        for loffset, row in enumerate(r.cols for r in rows):
            # Si la fila es demasiado corta, tengo que extenderla
            # hasta que alcance una longitud minima, para que no me
            # de error de "index out of range"
            if len(row) < minlen:
                row.extend(('',) * (minlen - len(row)))
            for index, convert in columns:
                row[index] = convert(row[index].strip(), errors.append)
            if errors:
                warnings.append((lineno + loffset, errors))
                errors = list()
        return rows

    def __iter__(self):
        return iter(self.cols)

    def truncate(self, length):
        self.cols = self.cols[:length]

    def __repr__(self):
        return " (%s) " % ", ".join(str(x) for x in self.cols)


class Column(object):

    """Columna del fichero CSV

    - index: indice de la columna en la fila del CSV.
    - selector: si la columna es parte de un filtro o selector, nombre
        de la tabla que filtra.
    - coltype: objeto Field que identifica el tipo de columna.
    - colname: nombre de la columna.
    - colkey: Si la columna es tipo "diccionario", valor de la clave.
    - canonical: Si la columna es un alias, nombre canonico.
    """

    def __init__(self, index, selector, coltype, colname, canonical=None):
        self.selector = selector
        self.index = index
        self.coltype = coltype
        nameparts, colkey = colname.split("["), None
        self.colname = nameparts.pop(0).strip()
        self.canonical = canonical
        if nameparts:
            colkey = nameparts[0].split("]")[0].strip() or None
            if colkey and colkey.isdigit():
                colkey = int(colkey)
        self.colkey = colkey


class ColumnList(object):

    """Lista de columnas asociada a un path"""

    def __init__(self, source, index, path, columns):
        """Construye la lista de columnas.

        source: origen del bloque (nombre de fichero).
        index: numero de linea de la cabecera en el fichero.
        path: path de la lista, ya procesado (en forma de tuple).
        columns: columnas de la lista, ya procesadas.

        En caso de excepcion al construir el objeto, el constructor
        lanza la excepcion desnuda, sin envolver en un DataError.
        """
        self.source = source
        self.index = index
        # Por si acaso columns es un iterator (no estaria definido __len__)
        self.path, self.columns = tuple(path), tuple(columns)
        self.selects = tuple(c for c in self.columns if c.selector)
        self.attribs = self.columns[len(self.selects):]
        self._expand_selectors(self.columns)

    def _expand_selectors(self, columns):
        """Expande la lista de selectores"""
        # Me aseguro de que todas las columnas con selector estan al principio
        # de la lista
        if any(x.selector for x in self.attribs):
            raise SyntaxError("Orden de cabeceras incorrecto")
        # Comparo los selectores con los elementos del path, y los
        # expando si estan abreviados.
        cursor = list(self.path[:-1])
        for column in self.selects:
            # Busco un elemento del path que coincida con el selector
            while cursor and not cursor[0].lower().startswith(column.selector.lower()):
                cursor.pop(0)
            # si no lo hay: Error!
            if not cursor:
                raise SyntaxError("Cabecera fuera de ruta")
            column.selector = cursor[0]

    @property
    def depth(self):
        """Devuelve el nivel de anidamiento de la tabla"""
        return len(self.path)

    def prepare(self, meta, block):
        """Prepara la carga de datos, analizando el path"""
        # Separo los atributos que sean "diccionarios" de los que no
        alias   = tuple(col for col in self.attribs if col.canonical)
        attribs = tuple(col for col in self.attribs if not col.canonical and not col.colkey)
        colkeys = tuple(col for col in self.attribs if not col.canonical and col.colkey )
        dicts   = defaultdict(list)
        for col in colkeys:
            dicts[col.colname].append(col)
        self.attribs = attribs
        self.dicts = dicts
        # Creo o accedo al meta y le inserto los nuevos campos.
        # Lo hago en esta fase y no en el constructor, porque aqui
        # ya compruebo que todos los tipos padres existan... eso
        # solo funciona si el proceso se hace por orden, del nivel
        # mas alto al mas bajo.
        try:
            for step in self.path[:-1]:
                meta = meta.subtypes[step]
        except KeyError:
            print("No se encuentra %s en %s\n" % (step, repr(meta.path)))
            raise
        meta = meta.child(self.path[-1])
        meta.summary = tuple(c.colname for c in self.attribs)[:3]
        for col in alias:
            meta.create_alias(col.colname, col.canonical)
        for col in attribs:
            meta.fields[col.colname] = col.coltype
        for key, cols in dicts.iteritems():
            meta.fields[key] = DictField()
        meta.blocks.append(block)        
        self.meta = meta
        # Creo una pila de operaciones, que filtra el dataset raiz
        # hasta llegar al punto donde tengo que insertar los datos.
        selects = list(self.selects) # copio para poder hacer pops()
        self.stack = tuple(self._consume(selects, step) for step in self.path[:-1])

    def _consume(self, selects, step):
        """Genera operaciones para descender un paso en el path"""
        # Obtengo los filtrados que corresponden al paso que voy a descender.
        indexes = list()
        while selects and selects[0].selector == step:
            indexes.append(str(selects.pop(0).colname))
        return (step, indexes)
    
    def _addrow(self, row_cols, rootset):
        """Crea el objeto y lo inserta en la posicion adecuada del rootset"""
        attrib = self.path[-1]
        vector = (row_cols[s.index] for s in self.selects)
        # Desciendo en el rootset hasta llegar al DataSet del que
        # cuelga el objeto. Si en algun paso me quedo sin dataset,
        # el indice no apunta a nadie, asi que salgo de la funcion.
        for step, indexes in self.stack:
            rootset = getattr(rootset, step)
            for key, val in izip(indexes, vector):
                # Si alguno de los indices es "None", es que no se
                # quiere procesar esta fila. Salgo devolviendo None.
                if val is None:
                    return
                rootset = rootset(**{key: val})
            if not rootset:
                return
        # Creo un objeto con los datos, que luego ire copiando
        data = ((c.colname, row_cols[c.index]) for c in self.attribs)
        data = dict((k, v) for (k, v) in data if v is not None)
        for key, cols in self.dicts.iteritems():
            val = ((c.colkey, row_cols[c.index]) for c in cols)
            val = dict((k, v) for (k, v) in val if v is not None)
            data[key] = val
        if not data:
            return
        # Inserto el objeto en cada elemento del dataset.
        nitems = list()
        for item in rootset:
            # El "parent" del objeto es el item que estamos procesando
            # si hemos tenido que bajar en la jerarquia (stack is not None).
            # En otro caso "item" es el objeto raiz y no queremos que los
            # objetos de primer nivel lo tengan como padre.
            obj = CSVDataObject(self.meta, item if self.stack else None)
            obj.__dict__.update(data)
            getattr(item, attrib).add(obj)
            nitems.append(obj)
        return nitems


class TableBlock(ColumnList):

    """Bloque de lineas de CSV representando una tabla"""

    HEADERS = 1

    def __init__(self, source, index, csvrows):
        """Analiza la cabecera y prepara la carga de los datos

        En caso de excepcion al construir el objeto, el constructor
        lanza la excepcion desnuda, sin envolver en un DataError.
        """
        typeline   = csvrows[0].cols[1:]
        headline   = csvrows[1].cols[1:]
        self.body  = csvrows[2:]
        path       = tuple(x.strip() for x in csvrows[1].cols[0].split("."))
        columns    = tuple(self._columns(typeline, headline))
        super(TableBlock, self).__init__(source, index, path, columns)

    def _columns(self, typeline, headline):
        """Construye los objetos columna con los datos de la cabecera"""
        for index, coltype, colname in zip(count(1), typeline, headline):
            # Me salto las columnas excluidas
            if not coltype or not colname or colname.startswith("!"):
                continue
            # Divido el nombre en selector y atributo
            selector, nameparts = None, colname.split(".")
            if len(nameparts) > 1:
                selector = nameparts.pop(0).strip()
                colname = nameparts[0].strip()
            if not colname:
                return
            # Creo el objeto columna principal y lo lanzo, si es correcto.
            coltype  = FieldMap.resolve(coltype)
            colalias = colname.split("//")
            col = Column(index, selector, coltype, colalias.pop(0))
            if not col.colname:
                return
            canonical = col.colname
            while col:
                if col.colname:
                    yield col
                col = None
                # Y voy lanzando los alias, si hay.
                if colalias:
                    alias = colalias.pop(0)
                    col = Column(index, selector, coltype, alias, canonical)

    def prepare(self, rootmeta):
        """Prepara los datos para su proceso"""
        super(TableBlock, self).prepare(rootmeta, self)

    def process(self, rootset, warnings=None):
        """Procesa las lineas del bloque actualizando los datos.

        En caso de excepcion al procesar los objetos, si no se
        ha pasado una lista de warnings, la excepcion se lanza envuelta en
        un DataError.
        
        Si se ha pasado un diccionario en warnings, los errores se acumulan
        en los warnings, con formato de diccionario:
            [source] => (numero de linea, lista de warnings)
        """
        if not self.body:
            return 
        source, lineno, errors = self.source, self.index, list()
        body, self.body = self.body, None # para que no se vuelva a ejecutar
        rows = CSVRow.normalize(lineno, body, self.columns, errors)
        if warnings is None:
            # No hay warnings, si se produce un error hay que lanzarlo.
            if errors:
                raise DataError(source, lineno, warnings=errors, stack=False)
            try:
                for row in rows:
                    lineno = row.lineno
                    self._addrow(row.cols, rootset)
            except Exception as details:
                raise DataError(source, lineno)
            # Cortamos aqui, el resto solo se procesa si warnings is not None
            return
        # Hay lista de warnings, se almacenan los errores.
        for row in rows:
            try:
                lineno = row.lineno
                self._addrow(row.cols, rootset)
            except Exception as details:
                errors.append((lineno, (str(details),)))
        if errors:
            warnings.setdefault(source, list()).extend(errors)


class LinkBlock(object):

    """Bloque de lineas de CSV representando un enlace"""

    HEADERS = 2

    def __init__(self, source, index, csvrows):
        """Analiza la cabecera y prepara la carga de los datos.

        En caso de excepcion al construir el objeto, el constructor
        lanza la excepcion desnuda, sin envolver en un DataError.
        """
        selectline = csvrows[0].cols[1:]
        typeline = csvrows[1].cols[1:]
        headline = csvrows[2].cols[1:]
        self.path = csvrows[2].cols[0][1:].split(".").pop(0).strip()
        self.source = source
        self.index = index
        self.columns = tuple(self._columns(selectline, typeline, headline))
        self.groups = tuple(self._groups())
        self.peercolumns = tuple(x for x in self.columns if not x.selector)
        self.body = csvrows[3:]

    def _columns(self, selectline, typeline, headline):
        """Construye los objetos columna con los datos de la cabecera"""
        for index, selector, coltype, colname in zip(count(1), selectline, typeline, headline):
            # Me salto las lineas excluidas
            if not coltype or not colname or colname.startswith("!") or colname == "*":
                continue
            selector = selector.strip() or None
            coltype = FieldMap.resolve(coltype)
            for alias in colname.strip().split("//"):
                col = Column(index, selector, coltype, alias)
                if col.colname:
                    yield col

    def _groups(self):
        """Divide la lista de columnas en sub-listas.

        Cada sub-lista tiene las columnas comunes y las especificas
        de una parte del enlace.
        """
        selectors, attribs, columns = list(), list(), list(self.columns)
        shared_selectors, shared_attribs = list(), list()
        while columns:
            # Voy dividiendo las columnas en subgrupos
            subsel, subattr, selindex = list(), list(), len(shared_selectors)
            # Primera parte: columnas formadas por selectores
            while columns and columns[0].selector:
                column = columns.pop(0)
                # si el campo empieza por "*", es comun a todos los grupos
                if column.colname.startswith("*"):
                    column.colname = column.colname[1:].strip()
                    # el orden de los selectores importa, asi que lo guardo
                    # para luego insertarlos en el mismo orden.
                    shared_selectors.append((selindex, column))
                # Si no comienza por "*", es exclusivo de este grupo
                else:
                    subsel.append(column)
                selindex += 1
            # Segunda parte: incluyo los "shared selectors" que haya
            # definidos hasta ahora.
            #
            # A diferencia de los campos comunes, que son comunes para todos
            # los peers, los selectores solo son comunes a partir del peer en
            # que se definen.
            for index, selector in shared_selectors:
                subsel.insert(index, selector)
            # Tercera parte: columnas formadas por campos
            while columns and not columns[0].selector:
                column = columns.pop(0)
                # si el campo empieza por "*", es comun a todos los grupos
                if column.colname.startswith("*"):
                    column.colname = column.colname[1:].strip()
                    shared_attribs.append(column)
                # Si no comienza por "*", es exclusivo de este grupo
                else:
                    subattr.append(column)
            selectors.append(subsel)
            attribs.append(subattr)
        # Extiendo cada grupo con los grupos comunes
        groups = list()
        for subsel, subattr in zip(selectors, attribs):
            # Los campos comunes los pongo al principio de las listas,
            # para que si un grupo los re-define despues, el nuevo
            # valor tenga prioridad sobre el comun.
            subsel.extend(shared_attribs)
            subsel.extend(subattr)
            groups.append(subsel)
        # self.p2p = (len(groups) == 2)
        # "des-multiplexo" los selectores y los convierto en ColumnLists.
        self.groups = list()
        for pos, group in enumerate(groups):
            for demux in self._demux(group):
                path = list(x.selector for x in demux if x.selector)
                path.append(self.path)
                clist = ColumnList(self.source, self.index, path, demux)
                # Marco la posicion del grupo dentro del enlace, para
                # hacer mas facil de-multiplexarlos.
                clist.position = pos
                yield clist

    def _demux(self, columns):
        """Desmultiplexa grupos con selectores combinados"""
        # Para salir de la recursion: si la lista esta vacia, la devolvemos.
        if not columns or not columns[0].selector:
            yield columns
        else:
            # Demultiplexamos el primer elemento
            column = columns.pop(0)
            selectors = (x.strip() for x in column.selector.split(","))
            for selector in (x for x in selectors if x):
                # Creamos un objeto columna con un solo selector
                newcol = Column(column.index, selector, column.coltype, column.colname)
                # y demultiplexamos a partir del siguiente elemento
                for subdemux in self._demux(columns):
                    yield tuple(chain((newcol,), subdemux))

    def prepare(self, rootmeta):
        """Prepara los datos para el posterior procesamiento"""
        # Preparo los grupos y descarto los que correspondan a paths
        # no validos.
        valid = set()
        for group in self.groups:
            # Preparo cada uno de los bloques
            try:
                group.prepare(rootmeta, self)
            except IndexError:
                # Este error se lanza cuando el path es invalido.
                # Como cada columna puede tener selectores
                # combinados, es posible que al demultiplexar haya
                # creado una combinacion invalida... asi que
                # simplemente la ignoro.
                pass
            else:
                valid.add(group)
        # Si no hay combinaciones validas, habra que lanzar un
        # error, digo yo...
        if not valid:
            raise SyntaxError("Ningun enlace valido")
        # A cada grupo valido le incluyo un sub-atributo:
        # - si solo hay dos grupos, el sub-atributo es "PEER"
        # - si hay mas de dos grupos, el subatributo es "PEERS"
        #
        # No he encontrado ningun use-case en el que necesite un peering
        # de mas de dos objetos. Sin embargo, si he encontrado use-cases
        # en que necesite peering de un objeto con dos posibles objetos
        # alternativos.
        #
        # Por ejemplo, en el ayto. de Sevilla: un enlace de un switch de una
        # sede de fibra optica a otro switch de otra sede o a un PE. Las rutas
        # de los switches_fo y de los PEs son completamente distintas, asi
        # que necesito dos bloques de selectores. Pero cada enlace utiliza
        # uno solo de los dos bloques, y el otro queda vacio.
        #
        # Asi que he decidido cambiar esta logica. Los enlaces son siempre
        # punto a punto, si hay multiples bloques seran alternativas.
        #
        # attrib = "PEER" if self.p2p else "PEERS"
        attrib = "PEER"
        for group in valid:
            # La POSITION no va a ser un campo indexable, porque se
            # puede utilizar "FLIP" para cambiarla.
            group.meta.fields["POSITION"] = IntField(indexable=False)
            group.meta.fields[attrib] = CSVObjectField()
        self.groups = valid

    def process(self, rootset, warnings=None):
        """Procesa las lineas del bloque actualizando los datos.

        En caso de excepcion al procesar los objetos, si no se
        ha pasado una lista de warnings, la excepcion se lanza envuelta en
        un DataError.
        
        Si se ha pasado un diccionario en warnings, los errores se acumulan
        en los warnings, con formato de diccionario:
            [source] => (numero de linea, lista de warnings)
        """
        if not self.body:
            return
        source, lineno, errors = self.source, self.index, list()
        valid, attrib  = self.groups, "PEER"
        # attrib = "PEER" if self.p2p else "PEERS"
        body, self.body = self.body, None # para que no se vuelva a ejecutar
        rows = CSVRow.normalize(lineno, body, self.columns, warnings)
        if errors and (warnings is None):
            raise DataError(source, lineno, warnings=errors, stack=False)
        for row in rows:
            try:
                lineno = row.lineno # por si lanzo excepcion
                # Creo todos los objetos y los agrego a una lista
                inserted = ((g.position, g._addrow(row.cols, rootset)) for g in valid)
                inserted = tuple((p, r) for (p, r) in inserted if r)
                # Y los cruzo para construir los peerings
                for index, result in enumerate(inserted):
                    # Los peers son el resultado de todos los procesos
                    # excepto el que estamos evaluando.
                    # Los peers pueden ser de distintos tipos, asi que
                    # en general no puedo meterlos en un DataSet...
                    # como mucho, en un PeerSet.
                    position, items = result
                    for item in items:
                        item.POSITION = position
                    peers = tuple(r for (i, r) in enumerate(inserted) if i != index)
                    peers = CSVPeerSet(chain(*(p[1] for p in peers)))
                    if peers:
                        # if self.p2p:
                        #    peers = +peers
                        peers = +peers
                        for item in items:
                            setattr(item, attrib, peers)
            except Exception as details:
                if warnings is None:
                    raise DataError(source, lineno, msg='Fila: %s' % str(row))
                errors.append((lineno, (str(details),)))
        if errors:
            warnings.setdefault(source, list()).extend(errors)

    @property
    def depth(self):
        """Devuelve el nivel de anidamiento de la tabla"""
        return max(x.depth for x in self.groups)


class CSVSource(FileSource):

    def read(self):
        # Auto-detecto el separador de campos... en funcion del
        # programa que exporte a CSV, algunos utilizan "," y otros ";".
        data = super(CSVSource, self).read()
        lines, delimiter = data.splitlines(), ";"
        for line in lines:
            if line and line[0] in (",", ";"):
                delimiter = line[0]
                break
        rows = tuple(self._clean(lines, delimiter))
        return self._split(rows)        

    def _clean(self, lines, delimiter):
        """Elimina las columnas comentario o vacias"""
        """Elimina las columnas comentario o vacias"""
        lineno = 0
        try:
            reader = csv.reader(lines, delimiter=delimiter)
            for lineno, row in enumerate(reader):
                for index, val in enumerate(row):
                    # Necesito el strip para que la comparacion de abajo
                    # (row[0].startswith("!")) sea fiable, lo mismo que el
                    # distinguir tipos de tabla por su marca
                    # ("*" => enlaces, resto => tablas)
                    row[index] = row[index].strip()
                if len(row) >= 2 and (row[0] or row[1]) and not row[0].startswith("!"):
                    yield CSVRow(lineno, row)
        except Exception as details:
            raise DataError(self.id, lineno)

    def _split(self, rows):
        """Divide el fichero en tablas"""
        # Extraigo el caracter de la primera columna, que me sirve como
        # discriminador.
        marks = ((i, r.cols[0][0]) for (i, r) in enumerate(rows) if r.cols[0])
        # Me salto las lineas que empiezan por "#", que sirven para
        # compatibilizar el nuevo csvreader con la version anterior (que
        # simplemente las trata como comentario). 
        marks = ((i, m) for (i, m) in marks if m != "#")
        # Identifico el bloque corresponde a cada marca
        marks = ((i, LinkBlock if m == "*" else TableBlock) for (i, m) in marks)
        # Y recalculo las etiquetas
        labels = list((i - blk.HEADERS, blk) for (i, blk) in marks)
        if not labels:
            raise StopIteration()
        labels.append((len(rows), None))
        # Divido la entrada en bloques
        source, lineno = self.id, -1
        try:
            for (lineno, blk), (j, skip) in zip(labels, labels[1:]):
                # Me quedo solo con las cabeceras hasta el primer '!'
                headers = rows[lineno:j]
                for hnum, hrow in enumerate(headers):
                    for idx, hcol in enumerate(hrow):
                        if hcol == '!':
                            hrow.truncate(idx)
                            break
                # Y creo un bloque
                yield blk(source, lineno, headers)
        except:
            raise DataError(source, lineno)


class CSVShelf(object):

    """Libreria de ficheros CSV"""

    VARTABLE = "variables"
    FILES    = "data_files"
    DATA     = "data_root"
    VERSION  = "data_version"
    CURRENT  = 2

    def __init__(self, shelf):
        self.shelf = shelf
        self.dirty = False

    def set_datapath(self, datapath, warnings=None, lazy=False):
        """Busca todos los ficheros CSV en el path.

        Compara la lista de ficheros encontrados con la
        que hay en el shelf.

        - Si la version del objeto en el shelf es menor que
          la actual, carga los datos y actualiza el shelf.
        - Si la lista de ficheros no coincide, carga los
          datos y actualiza el shelf.
        - Si algun fichero es mas reciente en disco que
          en el shelf, carga los datos y actualiza el
          shelf.

        Si se le pasa una lista en warnings, acumula ahi los posibles errores
        que encuentre al procesar la lista de variables u otros elementos.
        
        Para generar los warnings hay que leer todos los ficheros y cargarlos
        completos, asi que si [warnings is not None], el valor de lazy se
        ignora.
        """
        files = dict(chain(*(self._findcsv(dirname) for dirname in datapath)))
        self.dirty = False
        try:
            if self.shelf[CSVShelf.VERSION] == CSVShelf.CURRENT:
                sfiles = self.shelf[CSVShelf.FILES]
                fnames = set(files.keys())
                snames = set(sfiles.keys())
                if not files or not fnames.symmetric_difference(snames):
                    if not files or all(files[x] <= sfiles[x] for x in fnames):
                        # Todo correcto, los datos estan cargados
                        backup = self.shelf[CSVShelf.DATA]
                        # Convierto lo almacenado en el shelf en un DataObject
                        meta = backup['_meta']
                        data = CSVDataObject(meta)
                        # Le actualizo los datos y construyo el rootset
                        data.__dict__.update(backup)
                        self._add_rootset(meta, CSVDataSet(meta, (data,)))
                        # Me quedo solo con el diccionario, lo demas
                        # me sobra.
                        self.data = dict(data.__dict__)
                        # Y actualizo el contador de Primary Keys, por si se
                        # tienen que instanciar mas objetos (modo lazy)
                        CSVDataObject.PK = data.PK
                        return
        except:
            pass
        # Si el pickle falla o no es completo, recargamos los datos
        # (cualquiera que sea el error)
        if warnings is not None:
            lazy = False
        self._update(files, warnings=warnings, lazy=lazy)

    def dump_warnings(self, warnings):
        if not warnings:
            return
        for source, warn in warnings.iteritems():
            print "Errores en fichero %s\n******************" % source
            for lineno, msgs in warn:
                print "linea %d\n  %s" % (lineno, "\n  ".join(msgs))

    def _add_rootset(self, rootmeta, rootset):
        rootmeta.rootset = rootset
        for submeta in rootmeta.subtypes.values():
            self._add_rootset(submeta, rootset)

    def _findcsv(self, dirname):
        """Encuentra todos los ficheros CSV en el path"""
        if not os.path.isdir(dirname):
            return tuple()
        files = (x for x in os.listdir(dirname) if x.lower().endswith(".csv"))
        files = (os.path.join(dirname, x) for x in files)
        files = (f for f in files if os.path.isfile(f))
        return ((os.path.abspath(f), os.stat(f).st_mtime) for f in files)

    def _update(self, files, warnings=None, lazy=False):
        """Procesa los datos y los almacena en el shelf"""
        nesting = self._read_blocks(files)
        meta = CSVMeta("", None)
        for depth in sorted(nesting.keys()):
            for item in nesting[depth]:
                try:
                    item.prepare(meta)
                except:
                    raise DataError(item.source, item.index)
        # ejecuto la carga de datos (solo de las tablas de primer nivel,
        # el resto se carga bajo demanda)
        data = CSVDataObject(meta)
        rset = CSVDataSet(meta, (data,))
        self._add_rootset(meta, rset)
        for key, subtype in meta.subtypes.iteritems():
            subtype.process(warnings=warnings, lazy=lazy)
            # Me aseguro de instanciar el atributo, porque si hay una
            # tabla vacia, subtype.process no hace nada.
            # data.get(key)
        # Proceso la tabla de variables
        self._set_vars(data, warnings)
        # OK, todo cargado... ahora guardo los datos en el shelf.
        data.PK = CSVDataObject.next()
        self._save(files, data.__dict__)

    def _read_blocks(self, files):
        """Carga los ficheros y genera los bloques de datos"""
        blocks  = chain(*tuple(CSVSource(path).read() for path in files))
        nesting = dict()
        for block in blocks:
            nesting.setdefault(block.depth, list()).append(block)
        return nesting

    def _set_vars(self, data, warnings=None):
        # proceso la tabla especial "variables"
        meta = data._meta
        keys = dict((k.lower(), k) for k in meta.subtypes.keys())
        vart = keys.get(CSVShelf.VARTABLE.lower(), None)
        if vart:
            submeta = meta.subtypes[vart]
            key, val, typ = submeta.summary[:3]
            vwarn = list()
            for item in getattr(data, str(vart)):
                vname = str(item.get(key))
                vtyp  = item.get(typ)
                vval  = item.get(val).strip()
                if all(x is not None for x in (vname, vtyp, vval)):
                    vtyp = FieldMap.resolve(vtyp)
                    vval = vtyp.convert(vval, vwarn.append) if vval else None
                    if vval is not None:
                        setattr(data, vname, vval)
                        meta.fields[vname] = vtyp
                    elif vwarn and (warnings is not None):
                        warnings.append((vname, vwarn))
                        vwarn = list()
            delattr(data, str(vart))
            del(meta.fields[vart])
            del(meta.subtypes[vart])

    def _save(self, files, data):
        self.data = dict(data) # hago una copia
        self.shelf[CSVShelf.VERSION] = CSVShelf.CURRENT
        self.shelf[CSVShelf.DATA] = data
        self.shelf[CSVShelf.FILES] = files
        self.dirty = True
