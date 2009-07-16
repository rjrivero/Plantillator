#!/usr/bin/env python
# -*- vim: expandtab tabstop=4 shiftwidth=4 smarttab autoindent


from itertools import chain

from data.base import normalize
from data.dataobject import RootType
from csvread.datatokenizer import DataTokenizer
from csvread.tableparser import TableParser, ValidHeader, DataError


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

    """Factoria de propiedades

    Diccionario path -> parser. Para cada ruta conocida, determina
    el parser (factoria de objetos) que carga los datos de esa ruta.
    Todas las propiedades son ScopeSets.
    """

    def __init__(self):
        dict.__init__(self)

    def __call__(self, cls, attr):
        attr = ValidHeader(attr)
        parser = self[".".join(chain(cls._Path, (attr,)))]
        parser._type = cls._SubType(attr, self)
        return parser

            
class TableLoader(ParserDict):
    """Cargador de ficheros de datos

    Un fichero de datos es basicamente una forma mas resumida de definir
    una estructura de "diccionarios" python, mediante CSV

    todos los objetos de un fichero de datos son diccionarios
    con una ruta, y un conjunto de valores.
    """

    def read(self, source, data):
        """Actualiza el ParserDict con los datos de la fuente."""
        try:
            self.lineno = "N/A"
            self.data   = data
            self._doread(source)
        except (SyntaxError, ValueError) as details:
            raise DataError(source, self.lineno, details)

    def _doread(self, source):
        """Realiza el procesamiento, no filtra excepciones"""
        tokenizer = DataTokenizer(source, DATA_COMMENT)
        path, title, lines = None, None, []
        for (self.lineno, line) in tokenizer.tokens():
            head = line.pop(0).strip() or None
            if head:
                head = [ValidHeader(x) for x in head.split(".")]
                if path and title and lines:
                    self._update(source, path, title, lines)
                path, title, lines = head, line, []
            elif line:
                lines.append((self.lineno, line))
        if path and title and lines:
            self._update(source, path, title, lines)

    def _update(self, source, path, title, lines):
        """Agrega un bloque de datos al ParserDict"""
        label = ".".join(path)
        try:
            parser = self[label]
        except KeyError:
            parser = self.setdefault(label, TableParser(self.data, path))
        parser.append((source, Block(title, lines)))
