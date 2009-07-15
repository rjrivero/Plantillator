#!/usr/bin/env python
# -*- vim: expandtab tabstop=4 shiftwidth=4 smarttab autoindent


import os.path
import itertools

from data.pathfinder import PathFinder, FileSource
from data.base import normalize
from csvread.datatokenizer import DataTokenizer
from csvread.tableparser import TableParser, ValidHeader


DATA_COMMENT = "!"


class Block(object):

    """Bloque de datos"""

    def __init__(self, headers, lines):
        self.headers = [ValidHeader(x) for x in headers]
        self.lines   = lines

    def __iter__(self):
        for (lineno, line) in self.lines:
            line = (normalize(x) for x in line)
            data = dict((x, y) for (x, y) in zip(self.headers, line)
                        if x is not None and y is not None)
            yield (lineno, data)


class ParserDict(dict):

    """Factoria de propiedades"""

    def __call__(self, cls, attr):
        attr = ValidHeader(attr)
        parser = self[".".join(cls._Path, (attr,))]
        parser._type = cls._SubType(attr, self)
        return parser

            
class TableLoader(ParserDict):
    """Cargador de ficheros de datos

    Un fichero de datos es basicamente una forma mas resumida de definir
    una estructura de "diccionarios" python, mediante CSV

    todos los objetos de un fichero de datos son diccionarios
    con una ruta, y un conjunto de valores.
    """

    def __init__(self, root):
        ParserDict.__init__(self)
        self.root  = root

    def read(self, source):
        """Actualiza el ParserDict con los datos de la fuente."""
        tokenizer = DataTokenizer(source, DATA_COMMENT)
        path, title, lines = None, None, []
        for (self.lineno, line) in tokenizer.tokens():
            head = line.pop(0)
            if head:
                head = (ValidHeader(x) for x in line.pop(0).split("."))
                if path and title and lines:
                    self._update(source, path, title, lines)
                path, title, lines = head, line, []
            elif line:
                lines.append((tokenizer.lineno, line))
        if path and title and lines:
            self._update(source, path, title, lines)
        return tables

    def _update(self, source, path, title, lines):
        """Agrega un bloque de datos al ParserDict"""
        label = ".".join(path)
        try:
            parser = self[label]
        except KeyError:
            parser = self.setdefault(label, TableParser(path, self.root))
        parser.append((source, Block(title, lines)))


if __name__ == "__main__":
    import sys
    import pprint
    for f in sys.argv[1:]:
        finder = PathFinder()
        source = FileSource(finder(f), finder)
        loader = TableLoader()
        pprint.pprint(loader.read(source))

