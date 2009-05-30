#!/usr/bin/env python
# -*- vim: expandtab tabstop=4 shiftwidth=4 smarttab autoindent


from gettext import gettext as _

from data.pathfinder import PathFinder, FileSource
from data.datatype import TypeTree
from data.dataobject import DataObject
from data.dataset import DataSet
from csvread.tableloader import TableLoader
from csvread.tableparser import TableParser


class DataSource(TableLoader):

    """Carga e interpreta ficheros de datos"""

    _HOOKS = (
        "DEPENDENCIAS", "VARIABLES"
    )

    def __init__(self, typetree, dataobject):
        TableLoader.__init__(self)
        self.lineno = 0
        self.dataobject = dataobject
        self.dataset = DataSet(typetree.root, [dataobject])
        self.parser = TableParser(typetree)

    def read(self, source):
        """Carga un fichero de datos, actualiza el diccionario.

        Devuelve una lista con las dependencias del fichero.
        """
        tables = TableLoader.read(self, source)
        self.dependencies = list()
        for datapath, blocks in tables.iteritems():
            if datapath.upper() in self._HOOKS:
                hook = getattr(self, "onHook_%s" % datapath.upper())
            else:
                hook = None
            for block in blocks:
                self.lineno, header = block.pop(0)
                filters = list(self.parser.get_filters(datapath, header))
                last = filters.pop()
                if hook is None:
                    header = self.parser.do_type(last.dtype, header)
                    for self.lineno, line in block:
                        self.addrow(filters, last, header, line)
                else:
                    for self.lineno, line in block:
                        hook(line)                    
        return self.dependencies

    def onHook_DEPENDENCIAS(self, line):
        self.dependencies.append(line[0])

    def onHook_VARIABLES(self, line):
        try:
            self.dataobject[line[0]] = line[1]
        except KeyError:
            raise SyntaxError, line[0]

    def addrow(self, filters, last, header, line):
        """inserta una linea del CSV en los datos."""
        base, line = self.parser.do_filter(self.dataset, filters, line)
        if not last.fields:
            vals = dict((x, y) for (x, y) in zip(header, line)
                if x is not None and y is not None)
            for item in base:
                getattr(item, last.name).add(DataObject(last.dtype, vals, item))
        else:
            fields = dict(zip(last.fields, line))
            values = dict((x, y) for (x, y) in zip(header, line[len(fields):])
                if x is not None and y is not None)
            for item in getattr(base, last.name)(**fields):
                item.update(values)


if __name__ == "__main__":
    import sys
    import pprint
    finder = PathFinder()
    ttree = TypeTree()
    dataobject = DataObject(ttree.root)
    loader = DataSource(ttree, dataobject)
    for f in sys.argv[1:]:
        source = FileSource(finder(f), finder)
        loader.read(source)
        #print(ttree)
        print(dataobject)

