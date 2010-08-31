#/usr/bin/env python


from copy import copy
from itertools import count, chain

import fields
from meta import Meta, RootMeta, DataSet, DataObject
from resolver import Resolver


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


def normalize(columns, rows):
    """Normaliza los datos de las columnas en funcion del tipo"""
    for row in rows:
        for col in columns:
            row[col.index] = col.coltype.convert(row[col.index])
    return rows


class ColumnList(object):

    def __init__(self, path, columns):
        """Construye la lista de columnas.

        path: path de la lista, ya procesado (en forma de tuple).
        columns: columnas de la lista, ya procesadas.
        """
        self.path = path
        self.columns = columns
        self._expand()

    def _expand(self):
        """Expande la lista de selectores"""
        # Me aseguro de que todas las columnas con selector estan al principio
        # de la lista
        selcount = len(list(x for x in self.columns if x.selector))
        if any(x.selector for x in self.columns[selcount:]):
            raise SyntaxError(u"Cabecera invalida: " + u", ".join(x.colname for x in self.columns))
        # Comparo los selectores con los elementos del path, y los
        # expando si estan abreviados.
        path = list(self.path)
        for column in self.columns[0:selcount]:
            # Busco un elemento del path que coincida con el selector
            while path and not path[0].lower().startswith(column.selector.lower()):
                path.pop(0)
            # Si lo hay: expando el selector.
            if path:
                column.selector = path[0]
            # si no lo hay: Error!
            else:
                raise SyntaxError(u"Lista " + u", ".join(x.selector for x in self.columns[:selcount]) + u" no valida en path " + u".".join(self.path))

    @property
    def depth(self):
        """Devuelve el nivel de anidamiento de la tabla"""
        return len(self.path)

    def _object(self, meta, row):
        obj = DataObject(meta)
        for col in (x for x in self.columns if not x.selector):
            value = row[col.index]
            if value is not None:
                setattr(obj, col.colname, value)
        return obj

    def process(self, normalized_body, metaroot, dataroot):
        """Carga los datos, creando los objetos y metadatos necesarios"""
        # Creo o accedo al meta y le inserto los nuevos campos.
        # Lo hago en esta fase y no en el constructor, porque aqui
        # ya compruebo que todos los tipos padres existan... eso
        # solo funcionara si el proceso se hace por orden, del nivel
        # mas alto al mas bajo.
        meta = metaroot
        for step in self.path[:-1]:
            # si no existe la ruta completa, lanza KeyError
            meta = metaroot.subtypes[step]
        meta = meta.child(self.path[-1])
        for col in self.columns:
            meta.fields[col.colname] = col.coltype
        # Y ahora, aplico los filtros y cargo cada elemento...
        print "PATH %s, META: %s" % (str(self.path), str(meta))

    def __str__(self):
        return "\n".join((str(self.path), "\n|t".join(str(x) for x in self.columns)))


class TableBlock(ColumnList):

    def __init__(self, path, typeline, headline, body):
        """Analiza la cabecera y prepara la carga de los datos.

        path: path de la lista, en bruto (cadena separada por ".").
        """
        columns = (self._column(*x) for x in zip(count(1), typeline, headline))
        columns = tuple(x for x in columns if x is not None)
        path = tuple(x.strip() for x in path.split(u"."))
        super(TableBlock, self).__init__(path, columns)
        self.body = normalize(self.columns, body)

    def _column(self, index, coltype, colname):
        """Construye un objeto columna con los datos de la cabecera"""
        if coltype and colname:
            selector, nameparts = None, colname.split(u".")
            if len(nameparts) > 1:
                selector = nameparts.pop(0).strip()
            colname = nameparts.pop(0).strip()
            if colname:
                coltype = fields.Map.resolve(coltype)
                return Column(index, selector, coltype, colname)

    def process(self, metaroot, dataroot):
        super(TableBlock, self).process(self.body, metaroot, dataroot)


class LinkBlock(object):

    def __init__(self, path, indexline, typeline, headline, body):
        """Analiza la cabecera y prepara la carga de los datos

        path: path de la lista, en bruto ("*nombre.<relleno>").
        groups: Grupos de ColumLists distintos en los que se ha dividido
            la cabecera
        peercolumns: conjunto de las columnas de datos de todos los grupos.
        """
        self.path = path[1:].split(u".").pop(0).strip()
        columns = (self._column(*x) for x in zip(count(1), indexline, typeline, headline))
        columns = list(col for col in columns if col is not None)
        self.groups = tuple(self._checkcolumns(columns))
        # checkcolumns ya ha dejado las columnas bien normalizadas,
        # ahora podemos quedarnos con las comunes y normalizar los datos.
        self.peercolumns = list(x for x in columns if not x.selector)
        self.body = normalize(columns, body)

    def process(self, metaroot, dataroot):
        """Procesa los datos"""
        inserted = list()
        for group in self.groups:
            # proceso los datos en cada uno de los bloques
            inserted.append(group.process(self.body, metaroot, dataroot))
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

    def _column(self, index, selector, coltype, colname):
        """Construye un objeto columna con los datos de la cabecera"""
        if coltype and colname:
            selector = selector.strip() or None
            coltype = fields.Map.resolve(coltype)
            return Column(index, selector, coltype, colname.strip())

    def _checkcolumns(self, columns):
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
                    colname = column.colname[1:].strip()
                    if colname:
                        column.colname = colname
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


if __name__ == "__main__":
    
    import unittest
    import csv
    import sys
    import collections
    import os
    import os.path

    files = (x for x in os.listdir(".") if x.lower().endswith(".csv"))
    files = (f for f in files if os.path.isfile(f))
    lines = (l.strip() for l in chain(*(open(f, "r").readlines() for f in files)))
    lines = (l for l in lines if not l.startswith("!"))
    lines = csv.reader(lines, delimiter=";")
    lines = (l for l in lines if len(l) >= 2)
    lines = list(l for l in lines if l[0].strip() or l[1].strip())
    heads = list()
    tails = list()
    
    for index, row in enumerate(lines):
        if row[0]:
            heads.append(index)
    if not heads:
        sys.exit(0)
    for item in heads[1:]:
        if lines[item][0].startswith("*"):
            tails.append(item-2)
        else:
            tails.append(item-1)
    tails.append(len(lines))

    blocks = list()
    for first, last in zip(heads, tails):
        row = lines[first]
        if row[0].startswith("*"):
            indexes = lines[first-2][1:]
            types = lines[first-1][1:]
            blocks.append(LinkBlock(row[0], indexes, types, row[1:], lines[first+1:last]))
        else:
            types = lines[first-1][1:]
            blocks.append(TableBlock(row[0], types, row[1:], lines[first+1:last]))

    metaroot = RootMeta()
    data = DataObject(metaroot)
    nesting = dict()
    for block in blocks:
        nesting.setdefault(block.depth, list()).append(block)
    for depth in sorted(nesting.keys()):
        for item in nesting[depth]:
            item.process(metaroot, data)
