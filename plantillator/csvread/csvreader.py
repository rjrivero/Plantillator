#/usr/bin/env python

import csv
import os
import os.path
import sys
import codecs
import chardet

try:
    from codecs import BOM_UTF8
except ImportError:
    # only available since Python 2.3
    BOM_UTF8 = '\xef\xbb\xbf'


# Try setting the locale, so that we can find out
# what encoding to use
try:
    import locale
    locale.setlocale(locale.LC_CTYPE, "")
except (ImportError, locale.Error):
    pass

from contextlib import contextmanager
from itertools import count, chain, repeat
from copy import copy

from ..data import DataException, Meta, DataObject, DataSet, PeerSet
from ..data import FieldMap, ObjectField, IntField


class CSVRow(object):

    """Fila de un fichero CSV"""

    __slots__ = ("lineno", "cols")

    def __init__(self, lineno, cols):
        self.lineno = lineno
        self.cols = cols

    def normalize(self, columns):
        """Normaliza los datos de las columnas en funcion del tipo"""
        for col in columns:
            self.cols[col.index] = col.coltype.convert(self.cols[col.index])

    def __repr__(self):
        return " (%s) " % ", ".join(self.cols)


class Column(object):

    """Columna del fichero CSV

    - index: indice de la columna en la fila del CSV.
    - selector: si la columna es parte de un filtro o selector, nombre
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

    def __init__(self, source, index, path, columns):
        """Construye la lista de columnas.

        source: origen del bloque (nombre de fichero).
        index: numero de linea de la cabecera en el fichero.
        path: path de la lista, ya procesado (en forma de tuple).
        columns: columnas de la lista, ya procesadas.

        En caso de excepcion al construir el objeto, el constructor
        lanza la excepcion desnuda, sin envolver en un DataException.
        """
        # Por si acaso columns es un iterator (no estaria definido __len__)
        self.source = source
        self.index = index
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

    def _prepare(self, meta):
        """Prepara la carga de datos, analizando el path"""
        # Creo o accedo al meta y le inserto los nuevos campos.
        # Lo hago en esta fase y no en el constructor, porque aqui
        # ya compruebo que todos los tipos padres existan... eso
        # solo funciona si el proceso se hace por orden, del nivel
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
        selects = list(self.selects)
        ops = (self._consume(selects, step) for step in self.path[:-1])
        self.stack = tuple(chain(*ops))

    def _consume(self, selects, step):
        """Genera operaciones para descender un paso con los selectores"""
        # Primera operacion: descender un nivel.
        def getsubtype(dset, vector):
            return getattr(dset, step)
        yield getsubtype
        # Segunda operacion: hacer los filtrados
        indexes = list()
        while selects and selects[0].selector == step:
            indexes.append(str(selects.pop(0).colname))
        if indexes:
            def search(dset, vector):
                for key in indexes:
                    dset = dset(**{key: vector.next()})
                return dset
            yield search
    
    def _addrow(self, row_cols, rootset):
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


@contextmanager
def wrap_exception(source, index):
    """Envuelve una excepcion normal en un DataException"""
    try:
        yield
    except Exception:
        raise DataException(source, index, sys.exc_info())


class TableBlock(ColumnList):

    """Bloque de lineas de CSV representando una tabla"""

    HEADERS = 1

    def __init__(self, source, index, csvrows):
        """Analiza la cabecera y prepara la carga de los datos

        En caso de excepcion al construir el objeto, el constructor
        lanza la excepcion desnuda, sin envolver en un DataException.
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
            colname = nameparts.pop(0).strip()
            if colname:
                coltype = FieldMap.resolve(coltype)
                yield Column(index, selector, coltype, colname)

    def process(self, data):
        """Procesa las lineas del bloque actualizando los datos.

        En caso de excepcion al procesar los objetos, la excepcion se
        lanza envuelta en un DataException.
        """
        rootset = DataSet(data._meta, (data,))
        with wrap_exception(self.source, self.index):
            self._prepare(data._meta)
        for row in self.body:
            with wrap_exception(self.source, row.lineno):
                row.normalize(self.columns)
                self._addrow(row.cols, rootset)


class LinkBlock(object):

    """Bloque de lineas de CSV representando un enlace"""

    HEADERS = 2

    def __init__(self, source, index, csvrows):
        """Analiza la cabecera y prepara la carga de los datos.

        En caso de excepcion al construir el objeto, el constructor
        lanza la excepcion desnuda, sin envolver en un DataException.
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
                clist = ColumnList(self.source, self.index, path, demux)
                # Marco la posicion del grupo dentro del enlace, para
                # hacer mas facil de-multiplexarlos si fuera necesario.
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

    def process(self, data):
        """Procesa los datos.

        En caso de excepcion al procesar los objetos, la excepcion se
        lanza envuelta en un DataException.
        """
        # Preparo los grupos y descarto los que correspondan a paths
        # no validos.
        meta, valid = data._meta, set()
        with wrap_exception(self.source, self.index):
            for group in self.groups:
                # Preparo cada uno de los bloques
                try:
                    group._prepare(meta)
                except IndexError:
                    # Este error se lanza cuando el path es invalido.
                    # Como cada columna puede tener selectores
                    # combinados, es posible que al demultiplezar haya
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
        attrib = "PEER" if self.p2p else "PEERS"
        for group in valid:
            group.meta.fields[attrib] = ObjectField()
            group.meta.fields["POSITION"] = IntField()
        # Y ahora, voy procesando linea a linea
        rootset = DataSet(meta, (data,))
        for row in self.body:
            with wrap_exception(self.source, row.lineno):
                # Creo todos los objetos y los agrego a una lista
                row.normalize(self.columns)
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
                    peers = PeerSet(chain(*(p[1] for p in peers)))
                    if peers:
                        if self.p2p:
                            peers = +peers
                        for item in items:
                            setattr(item, attrib, peers)

    @property
    def depth(self):
        """Devuelve el nivel de anidamiento de la tabla"""
        return max(x.depth for x in self.groups)


class CSVSource(object):

    @classmethod
    def get_default_encoding(cls):
        try:
            return cls.ENCODING
        except AttributeError:
            pass
        if sys.platform == 'win32':
            encoding = locale.getdefaultlocale()[1]
        else:
            try:
                encoding = locale.nl_langinfo(locale.CODESET)
            except (NameError, AttributeError):
                encoding = locale.getdefaultlocale()[1]
        try:
            encoding = encoding.lower() if encoding else 'ascii'
            codecs.lookup(encoding)
        except LookupError:
            encoding = 'ascii'
        cls.ENCODING = encoding
        return encoding

    def as_unicode(self, chars):
        if chars.startswith(BOM_UTF8):
            return unicode(chars, 'utf-8')
        try:
            return unicode(chars)
        except UnicodeError:
            pass
        try:
            return unicode(chars, CSVSource.get_default_encoding())
        except UnicodeError:
            pass
        codec = chardet.detect(chars)['encoding']
        return unicode(chars, codec)

    def __init__(self, path):
        # Auto-detecto el separador de campos... en funcion del
        # programa que exporte a CSV, algunos utilizan "," y otros ";".
        # Asumimos que el encoding de entrada es compatible con ASCII:
        # - csv.reader va a ser capaz de leerlo
        # - los caracteres ",", ";", "*" y "!" son iguales que en ASCII.
        with open(path, "rb") as infile:
            data = self.as_unicode(infile.read())
        # Codifico a utf-8 para el csv.reader
        data = data.encode('utf-8')
        lines, delim = data.splitlines(), ";"
        for line in lines:
            if line and line[0] in (",", ";"):
                delimiter = str(line[0])
                break
        rows = tuple(self._clean(lines, delimiter))
        self.blocks = self._split(path, rows)        

    def _clean(self, lines, delimiter):
        """Elimina las columnas comentario o vacias"""
        reader = csv.reader(lines, delimiter=delimiter)
        for lineno, row in enumerate(reader):
            for index, val in enumerate(row):
                # No lo volvemos a pasar a unicode, hacemos todo el proceso
		# en utf-8.
		# Cuando pasemos a python-3, lo que habra que hacer sera
		# no convertir la cadena a utf-8 desde el principio, sino
		# dejarla en unicode.
                row[index] = row[index].strip()
            if len(row) >= 2 and (row[0] or row[1]) and row[0] != "!":
                yield CSVRow(lineno, row)

    def _split(self, path, rows):
        """Divide el fichero en tablas"""
        labels = list()
        # Busco todas las lineas que marcan un inicio de tabla
        for index, row in ((i, r) for (i, r) in enumerate(rows) if r.cols[0]):
            blk = LinkBlock if row.cols[0].strip().startswith("*") else TableBlock
            labels.append((index-blk.HEADERS, blk))
        if not labels:
            raise GeneratorExit()
        labels.append((len(rows), None))
        # Divido la entrada en bloques
        for (i, blk), (j, skip) in zip(labels, labels[1:]):
            with wrap_exception(path, i):
                yield blk(path, i, rows[i:j])

    def __iter__(self):
        return iter(self.blocks)


class CSVShelf(object):

    """Libreria de ficheros CSV"""

    VARTABLE = "variables"
    FILES    = "data_files"
    DATA     = "data_root"
    VERSION  = "data_version"
    CURRENT  = 1

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
                        self.data = copy(datashelf[CSVShelf.DATA])
                        return
        except:
            # Si el pickle falla o no es completo, recargamos los datos
            # (cualquiera que sea el error)
            pass
        self._update(files, datashelf)

    def _findcsv(self, dirname):
        """Encuentra todos los ficheros CSV en el path"""
        files = (x for x in os.listdir(dirname) if x.lower().endswith(".csv"))
        files = (f for f in files if os.path.isfile(f))
        return ((os.path.abspath(f), os.stat(f).st_mtime) for f in files)

    def _update(self, files, datashelf):
        """Procesa los datos y los almacena en el shelf"""
        nesting = self._read_blocks(files)
        meta = Meta("", None)
        data = DataObject(meta)
        for depth in sorted(nesting.keys()):
            for item in nesting[depth]:
                item.process(data)
        # Proceso la tabla de variables
        self._set_vars(data)
        # OK, todo cargado... ahora guardo los datos en el shelf.
        self._save(datashelf, files, data.__dict__)

    def _read_blocks(self, files):
        """Carga los ficheros y genera los bloques de datos"""
        blocks  = chain(*(CSVSource(path) for path in files))
        nesting = dict()
        for block in blocks:
            nesting.setdefault(block.depth, list()).append(block)
        return nesting

    def _set_vars(self, data):
        # proceso la tabla especial "variables"
        meta = data._meta
        keys = dict((k.lower(), k) for k in meta.subtypes.keys())
        vart = keys.get(CSVShelf.VARTABLE.lower(), None)
        if vart:
            submeta = meta.subtypes[keys[vart]]
            key, typ, val = submeta.summary[:3]
            for item in getattr(data, str(vart)):
                vname = str(item._get(key))
                vtyp  = item._get(typ)
                vval  = item._get(val)
                if all(x is not None for x in (vname, vtyp, vval)):
                    vtyp = FieldMap.resolve(vtyp)
                    vval = vtyp.convert(vval)
                    if vval is not None:
                        setattr(data, vname, vval)
            delattr(data, str(vart))
            del(meta.subtypes[vart])

    def _save(self, datashelf, files, data):
        datashelf[CSVShelf.VERSION] = CSVShelf.CURRENT
        datashelf[CSVShelf.DATA] = data
        datashelf[CSVShelf.FILES] = files
        datashelf.sync()
        self.data = copy(data)

    @staticmethod
    def loader(path, datashelf):
        return CSVShelf(path, datashelf).data


if __name__ == "__main__":

    import pprint
    import code
    import shelve
    from resolver import Resolver

    shelfname = "data.shelf"
    csvpath = (".",)

    if os.path.isfile(shelfname):
        os.unlink(shelfname)
    shelf = shelve.open(shelfname, protocol=2)
    try:
        csvshelf = CSVShelf(csvpath, shelf)
        data = csvshelf.data
    except DataException as details:
        print details
        sys.exit(-1)
    finally:
        shelf.close()
    symbols  = ("x", "y", "z", "X", "Y", "Z")
    for s in symbols:
        data[s] = Resolver("self")
    data['NONE'] = DataSet.NONE
    data['ANY'] = DataSet.ANY
    if len(sys.argv) > 1:
        code.interact(local = data)
    else:
        print "USO: %s <cualquier cosa>" % sys.argv[0]
