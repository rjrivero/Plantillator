#/usr/bin/env python

import csv
import os
import os.path
from itertools import count, chain
from copy import copy
from chardet.universaldetector import UniversalDetector

import fields
from meta import Meta, DataObject, DataSet, BaseSet


class CSVRow(object):

    """Fila de un fichero CSV, en unicode"""

    __slots__ = ("lineno", "cols")

    def __init__(self, lineno, cols):
        self.lineno = lineno
        self.cols = cols

    def normalize(self, columns):
        """Normaliza los datos de las columnas en funcion del tipo"""
        for col in columns:
            self.cols[col.index] = col.coltype.convert(self.cols[col.index])


class Column(object):

    """Columna del fichero CSV

    - index: indice de la columna en la fila del CSV.
    - selector: si la columna es parte de un filtro o selector, nombre de
        de la tabla que filtra.
    - coltype: objeto Field que identifica el tipo de columna.
    - colname: nombre de la columna.
    """

    def __init__(self, index, selector, coltype, colname):
        self.index = index
        self.selector = selector
        self.coltype = coltype
        self.colname = colname


class ColumnList(object):

    """Lista de columnas asociada a un path"""

    def __init__(self, path, columns):
        """Construye la lista de columnas.

        path: path de la lista, ya procesado (en forma de tuple).
        columns: columnas de la lista, ya procesadas.
        """
        # Por si acaso columns es un iterator (no estaria definido __len__)
        self.path, columns = tuple(path), tuple(columns)
        self.selects = tuple(c for c in columns if c.selector)
        self.attribs = columns[len(self.selects):]
        self._expand_selectors(tuple(columns))

    def _expand_selectors(self, columns):
        """Expande la lista de selectores"""
        # Me aseguro de que todas las columnas con selector estan al principio
        # de la lista
        if any(x.selector for x in self.attribs):
            raise SyntaxError("Orden de cabeceras incorrecto")
        # Comparo los selectores con los elementos del path, y los
        # expando si estan abreviados.
        cursor = self.path[:-1]
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

    def _object(self, meta, parent, row_cols):
        """Construye un objeto con los datos de una fila"""
        obj = DataObject(meta, parent)
        for col in self.attribs:
            value = row_cols[col.index]
            if value is not None:
                setattr(obj, col.colname, value)
        return obj

    def prepare(self, meta):
        """Prepara la carga de datos, analizando el path"""
        # Creo o accedo al meta y le inserto los nuevos campos.
        # Lo hago en esta fase y no en el constructor, porque aqui
        # ya compruebo que todos los tipos padres existan... eso
        # solo funcionara si el proceso se hace por orden, del nivel
        # mas alto al mas bajo.
        for step in self.path[:-1]:
            meta = meta.subtypes[step]
        meta = meta.child(self.path[-1])
        meta.summary = tuple(c.colname for c in self.attribs)[:3]
        for col in self.attribs:
            meta.fields[col.colname] = col.coltype
        self.meta = meta
        # Creo una pila de operaciones, que filtra el dataset raiz
        # hasta llegar al punto donde tengo que insertar los datos.
        selects, stack = list(self.selects), list()
        for step in self.path[:-1]:
            def getsubtype(dset, vector):
                return getattr(dset, step)
            stack.append(getsubtype)
            while selects and selects[0].selector == step:
                select = selects.pop(0)
                def search(dset, vector):
                    return dset(**{str(select.colname): vector.next()})
                stack.append(search)
        self.stack = stack

    def addrow(self, row_cols, rootset):
        """Crea el objeto y lo inserta en la posicion adecuada del rootset"""
        attrib = self.path[-1]
        vector = (row_cols[s.index] for s in self.selects)
        nitems = set()
        # Desciendo en el rootset hasta llegar al DataSet del que
        # cuelga el objeto
        for op in self.stack:
            rootset = op(rootset, vector)
        # Creo un objeto con los datos, que luego ire copiando
        data = ((c.colname, row_cols[c.index]) for c in self.attribs)
        data = dict((k, v) for (k, v) in data if v is not None)
        # Inserto el objeto en cada elemento del dataset.
        for item in rootset:
            obj = DataObject(self.meta, item if self.stack else None)
            obj.__dict__.update(data)
            getattr(item, attrib).add(obj)
            nitems.add(obj)
        return None if not nitems else DataSet(self.meta, nitems)


class TableBlock(ColumnList):

    """Bloque de lineas de CSV representando una tabla"""

    HEADERS = 1

    def __init__(self, csvrows):
        """Analiza la cabecera y prepara la carga de los datos"""
        typeline = csvrows[0].cols[1:]
        headline = csvrows[1].cols[1:]
        columns = tuple(self._columns(typeline, headline))
        path = tuple(x.strip() for x in csvrows[1].cols[0].split(u"."))
        super(TableBlock, self).__init__(path, columns)
        self.body = csvrows[2:]
        for row in self.body:
            row.normalize(columns)

    def _columns(self, typeline, headline):
        """Construye los objetos columna con los datos de la cabecera"""
        for index, coltype, colname in zip(count(1), typeline, headline):
            if not coltype or not colname or colname.startswith(u"!"):
                continue
            selector, nameparts = None, colname.split(u".")
            if len(nameparts) > 1:
                selector = nameparts.pop(0).strip()
            colname = nameparts.pop(0).strip()
            if colname:
                coltype = fields.Map.resolve(coltype)
                yield Column(index, selector, coltype, colname)

    def process(self, meta, data):
        rootset = DataSet(meta, (data,))
        self.prepare(meta)
        for row in self.body:
            self.addrow(row.cols, rootset)


class LinkBlock(object):

    """Bloque de lineas de CSV representando un enlace"""

    HEADERS = 2

    def __init__(self, csvrows):
        """Analiza la cabecera y prepara la carga de los datos"""
        selectline = csvrows[0].cols[1:]
        typeline = csvrows[1].cols[1:]
        headline = csvrows[2].cols[1:]
        self.columns = tuple(self._columns(selectline, typeline, headline))
        self.path = csvrows[2].cols[0][1:].split(u".").pop(0).strip()
        self.groups = tuple(self._groups())
        self.peercolumns = tuple(x for x in self.columns if not x.selector)
        self.body = csvrows[3:]
        for row in self.body:
            row.normalize(self.columns)

    def process(self, meta, data):
        """Procesa los datos"""
        # Preparo los grupos y descarto los que correspondan a paths
        # no validos.
        valid = set()
        for group in self.groups:
            # Preparo cada uno de los bloques
            try:
                group.prepare(meta)
            except IndexError:
                # Este error se lanza cuando el path es invalido.
                # Como cada columna puede tener selectores combinados,
                # es posible que al demultiplezar haya creado una
                # combinacion invalida... asi que simplemente la ignoro.
                pass
            else:
                valid.add(group)
        # A cada grupo valido le incluyo un sub-atributo:
        # - si solo hay dos grupos, el sub-atributo es "PEER"
        # - si hay mas de dos grupos, el subatributo es "PEERS"
        attrib = "PEER" if self.p2p else "PEERS"
        for group in valid:
            group.meta.fields[attrib] = fields.Field()
            group.meta.fields["POSITION"] = fields.IntField()
        # Y ahora, voy procesando linea a linea
        rootset = DataSet(meta, (data,))
        for row in self.body:
            # Creo todos los objetos y los agrego a una lista
            inserted = ((g.position, g.addrow(row.cols, rootset)) for g in valid)
            inserted = tuple((p, r) for (p, r) in inserted if r)
            # Y los cruzo para construir los peerings
            for index, result in enumerate(inserted):
                # Los peers son el resultado de todos los procesos excepto
                # el que estamos evaluando.
                # Los peers pueden ser de distintos tipos, asi que en
                # general no puedo meterlos en un DataSet... como mucho,
                # en un BaseSet.
                peers = tuple(r for (i, r) in enumerate(inserted) if i != index)
                peers = BaseSet(chain(*(p[1] for p in peers)))
                if peers:
                    if self.p2p:
                        peers = +peers
                    position, items = result
                    for item in items:
                        setattr(item, attrib, peers)
                        item.POSITION = position

    def _columns(self, selectline, typeline, headline):
        """Construye los objetos columna con los datos de la cabecera"""
        for index, selector, coltype, colname in zip(count(1), selectline, typeline, headline):
            if not coltype or not colname or colname.startswith("!") or colname.strip() == "*":
                continue
            selector = selector.strip() or None
            coltype = fields.Map.resolve(coltype)
            yield Column(index, selector, coltype, colname.strip())

    def _groups(self):
        """Divide la lista de columnas en sub-listas.

        Cada sub-lista tiene las columnas comunes y las especificas
        de una parte del enlace.
        """
        groups, commons, columns = list(), list(), list(self.columns)
        while columns:
            # Voy dividiendo las columnas en subgrupos
            sublist = list()
            # Primera parte: columnas formadas por selectores
            while columns and columns[0].selector:
                sublist.append(columns.pop(0))
            # Segunda parte: columnas formadas por campos
            while columns and not columns[0].selector:
                column = columns.pop(0)
                # si el campo empieza por "*", es comun a todos los grupos
                if column.colname.startswith("*"):
                    column.colname = column.colname[1:].strip()
                    commons.append(column)
                # Si no comienza por "*", es exclusivo de este grupo
                else:
                    sublist.append(column)
            groups.append(sublist)
        # Extiendo cada grupo con los grupos comunes
        self.p2p = (len(groups) == 2)
        for group in groups:
            group.extend(commons)
        # "des-multiplexo" los selectores y los convierto en ColumnLists.
        self.groups = list()
        for pos, group in enumerate(groups):
            for demux in self._demux(group):
                path = list(x.selector for x in demux if x.selector)
                path.append(self.path)
                clist = ColumnList(path, demux)
                # Marco la posicion del grupo dentro del enlace, para
                # hacer mas facil de-multiplexarlos si fuera necesario.
                clist.position = pos
                yield clist

    def _demux(self, columns):
        """Desmultiplexa grupos con selectores combinados"""
        # Para salir de la recursion: si la lista esta vacia, la devolvemos.
        if not columns or not columns[0].selector:
            yield tuple(columns)
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

    @property
    def depth(self):
        """Devuelve el nivel de anidamiento de la tabla"""
        return max(x.depth for x in self.groups)


class CSVSource(object):

    def __init__(self, data, name, codec="utf-8", delimiter=";"):
        self.name = name
        rows = self._clean(data.splitlines(), delimiter, codec)
        self.blocks = self._split(rows)

    def _clean(self, lines, delimiter, codec):
        reader = csv.reader(lines, delimiter=delimiter)
        for lineno, row in enumerate(reader):
            # decodifico despues de reconocer el csv, porque por lo
            # visto, el csv.reader no se lleva muy bien con el texto
            # unicode.
            for index, item in enumerate(row):
                row[index] = item.decode(codec).strip()
            if len(row) >= 2 and (row[0] or row[1]) and row[0] != u"!":
                yield CSVRow(lineno, row)

    def _split(self, rows):
        labels, rows = list(), tuple(rows)
        # Busco todas las lineas que marcan un inicio de tabla
        for index, row in ((i, r) for (i, r) in enumerate(rows) if r.cols[0]):
            blk = LinkBlock if row.cols[0].startswith("*") else TableBlock
            labels.append((index-blk.HEADERS, blk))
        if not labels:
            raise GeneratorExit()
        labels.append((len(rows), None))
        # Divido la entrada en bloques
        for (i, blk), (j, skip) in zip(labels, labels[1:]):
            yield blk(rows[i:j])

    def __iter__(self):
        return iter(self.blocks)


class CSVShelf(object):

    """Libreria de ficheros CSV"""

    FILES   = "data_files"
    DATA    = "data_root"
    VERSION = "data_version"
    CURRENT = 1

    def __init__(self, path, datashelf):
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
        """
        files = dict(chain(*(self._findcsv(dirname) for dirname in path)))
        try:
            if datashelf[CSVShelf.VERSION] == CSVShelf.CURRENT:
                sfiles = datashelf[CSVShelf.FILES]
                fnames = set(files.keys())
                snames = set(sfiles.keys())
                if not fnames.symmetric_difference(snames):
                    if all(files[name] <= sfiles[name] for name in fnames):
                        # Todo correcto, los datos estan cargados
                        self.data = datashelf[CSVShelf.DATA]
                        return
        except KeyError:
            pass
        self._update(files, datashelf)

    def _findcsv(self, dirname):
        files = (x for x in os.listdir(dirname) if x.lower().endswith(".csv"))
        files = (f for f in files if os.path.isfile(f))
        return ((os.path.abspath(f), os.stat(f).st_mtime) for f in files)

    def _update(self, files, datashelf):
        fdata = tuple((f, open(f, "rb").read()) for f in files.keys())
        # Asumo que todos los ficheros CSV han sido generados
        # por el mismo editor, y que deben usar el mismo encoding.
        detector = UniversalDetector()
        for fname, data in fdata:
            detector.feed(data)
            if detector.done:
                break
        detector.close()
        codec   = detector.result['encoding']
        sources = (CSVSource(data, f, codec) for (f, data) in fdata)
        blocks  = chain(*sources)
        meta = Meta("", None)
        data = DataObject(meta)
        nesting = dict()
        for block in blocks:
            nesting.setdefault(block.depth, list()).append(block)
        for depth in sorted(nesting.keys()):
            for item in nesting[depth]:
                item.process(meta, data)
        # OK, todo cargado... ahora guardo los datos en el shelf.
        self.data = data
        datashelf[CSVShelf.VERSION] = CSVShelf.CURRENT
        datashelf[CSVShelf.DATA] = data
        datashelf[CSVShelf.FILES] = files
        datashelf.sync()


if __name__ == "__main__":

    import pprint
    import code
    import shelve

    from resolver import Resolver

    shelf = shelve.open("data.shelf", protocol=2)
    data  = CSVShelf((".",), shelf).data
    shelf.close()

##    def plain_data(data):
##        subfields = dict()
##        for sf in data._meta.subtypes.keys():
##            if sf == "PEERS":
##                # los peers se enlazan unos a otros, tenemos que saltarnoslos
##                # para evitar bucles.
##                continue
##            subfields[sf] = tuple(plain_data(x) for x in data.get(sf))
##        return {
##            'summary': unicode(data),
##            'fields' : dict((i, data.get(i)) for i in data._meta.fields.keys()),
##            'subfields': subfields,}
##    pprint.pprint(plain_data(data))


    symbols  = ("x", "y", "z", "X", "Y", "Z")
    resolver = Resolver("self")
    for s in symbols:
        setattr(data, s, resolver)
    data.NONE = DataSet.NONE
    data.ANY = DataSet.ANY
    code.interact(local = data.__dict__)
