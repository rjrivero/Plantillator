#/usr/bin/env python


import csv
import chardet
from itertools import count, chain
from copy import copy

import fields
from meta import Meta, RootMeta, DataSet, DataObject
from resolver import Resolver


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
        self.path, self.columns = tuple(path), tuple(columns)
        self.attribs = tuple(x for x in self.columns if not x.selector)
        self._expand_selectors()

    def _expand_selectors(self):
        """Expande la lista de selectores"""
        # Me aseguro de que todas las columnas con selector estan al principio
        # de la lista
        selcount = len(self.columns)-len(self.attribs)
        if any(x.selector for x in self.columns[selcount:]):
            raise SyntaxError("Orden de cabeceras incorrecto")
        # Comparo los selectores con los elementos del path, y los
        # expando si estan abreviados.
        cursor = self.path[:-1]
        for column in self.columns[0:selcount]:
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

    def _object(self, meta, row_cols):
        """Construye un objeto con los datos de una fila"""
        obj = DataObject(meta)
        for col in (x for x in self.columns if not x.selector):
            value = row_cols[col.index]
            if value is not None:
                setattr(obj, col.colname, value)
        return obj

    def process(self, normalized_body, meta, data):
        """Carga los datos, creando los objetos y metadatos necesarios"""
        # Creo o accedo al meta y le inserto los nuevos campos.
        # Lo hago en esta fase y no en el constructor, porque aqui
        # ya compruebo que todos los tipos padres existan... eso
        # solo funcionara si el proceso se hace por orden, del nivel
        # mas alto al mas bajo.
        for step in self.path[:-1]:
            meta = meta.subtypes[step]
        meta = meta.child(self.path[-1])
        for col in self.columns:
            meta.fields[col.colname] = col.coltype
        # Y ahora, aplico los filtros y cargo cada elemento...
        return DataSet(meta)


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
            row.normalize(self.columns)

    def _columns(self, typeline, headline):
        """Construye los objetos columna con los datos de la cabecera"""
        for index, coltype, colname in zip(count(1), typeline, headline):
            if not coltype or not colname:
                continue
            selector, nameparts = None, colname.split(u".")
            if len(nameparts) > 1:
                selector = nameparts.pop(0).strip()
            colname = nameparts.pop(0).strip()
            if colname:
                coltype = fields.Map.resolve(coltype)
                yield Column(index, selector, coltype, colname)

    def process(self, meta, data):
        return super(TableBlock, self).process(self.body, meta, data)


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
        self.groups = tuple(self._groups(self.columns))
        self.peercolumns = tuple(x for x in self.columns if not x.selector)
        self.body = csvrows[3:]
        for row in self.body:
            row.normalize(self.columns)

    def process(self, meta, data):
        """Procesa los datos"""
        inserted = list()
        for group in self.groups:
            # proceso los datos en cada uno de los bloques
            inserted.append(group.process(self.body, meta, data))
        # Inserto el peering
        for index, result in enumerate(inserted):
            if result is None:
                continue
            # Creo un subtipo "PEERS"  del tipo insertado.
            peermeta = result._meta.child("PEERS")
            for col in self.peercolumns:
                peermeta.fields[col.colname] = col.coltype
            # Meto todos los peers creados en cada resultado.
            if result:
                peers = DataSet(peermeta, chain(*(r for (i, r) in enumerate(inserted) if r and (i != index))))
                for item in result:
                    items.PEERS = peers

    def _columns(self, selectline, typeline, headline):
        """Construye los objetos columna con los datos de la cabecera"""
        for index, selector, coltype, colname in zip(count(1), selectline, typeline, headline):
            if not coltype or not colname or colname.strip() == "*":
                continue
            selector = selector.strip() or None
            coltype = fields.Map.resolve(coltype)
            yield Column(index, selector, coltype, colname.strip())

    def _groups(self, columns):
        """Divide la lista de columnas en sub-listas.

        Cada sub-lista tiene las columnas comunes y las especificas
        de una parte del enlace.
        """
        groups, commons, columns = list(), list(), list(columns)
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
        for group in groups:
            group.extend(commons)
        # "des-multiplexo" los selectores y los convierto en ColumnLists.
        self.groups = list()
        for group in chain(*(self._demux(group) for group in groups)):
            path = list(x.selector for x in group if x.selector)
            path.append(self.path)
            yield ColumnList(path, group)

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

    def __init__(self, data, name, delimiter=";"):
        self.name = name
        codec = chardet.detect(data)['encoding']
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


if __name__ == "__main__":

    import unittest
    import sys
    import collections
    import os
    import os.path
    import pprint

    files   = (x for x in os.listdir(".") if x.lower().endswith(".csv"))
    files   = (f for f in files if os.path.isfile(f))
    files   = (os.path.abspath(f) for f in files)
    sources = (CSVSource(open(f, "rb").read(), f) for f in files)
    blocks  = chain(*sources)

    meta = RootMeta()
    data = DataObject(meta)
    nesting = dict()
    for block in blocks:
        nesting.setdefault(block.depth, list()).append(block)
    for depth in sorted(nesting.keys()):
        for item in nesting[depth]:
            item.process(meta, data)

    def plain_meta(meta):
        return {
            'path'  : meta.path,
            'types' : dict((x, plain_meta(y)) for x, y in meta.subtypes.iteritems()),
            'fields': meta.fields.keys()}
    pprint.pprint(plain_meta(meta))
