#!/usr/bin/env python
# -*- vim: expandtab tabstop=4 shiftwidth=4 smarttab autoindent


from itertools import chain, izip_longest

from ..data.base import normalize, DataError
from .tokenizer import Tokenizer
from .parser import TableParser, ValidHeader, DataError


DATA_COMMENT = "!"
DATA_ANNOTATION = "#"
ANNOTATIONS = "_annotations"


def zip_none(keys, values):
    """Agrupa los elementos no nulos de dos listas"""
    return ((k, v) for (k, v) in zip(keys, values)
                   if k is not None and v is not None)


class CSVLine(object):

    """Linea de un fiichero CSV"""

    def __init__(self, lineno, line):
        self.lineno = lineno
        self.line = line
        self.notes = None

    def as_dict(self, headers):
        """Devuelve un diccionario con los valores de la linea"""
        data = dict(zip_none(headers, (normalize(x) for x in self.line)))
        if self.notes:
            # agrupo las notas de cada atributo en tuplas
            notes = izip_longest(*self.notes)
            # uno las lineas de las notas de cada atributo
            notes = ("".join(x for x in n if x) or None for n in notes)
            # y almaceno las anotaciones como un dict.
            data[ANNOTATIONS] = dict(zip_none(headers, notes))
        return data

    def annotate(self, notes):
        """Agrupa lineas de anotaciones"""
        if self.notes is None:
            self.notes = list()
        self.notes.append(x.strip() or None for x in notes)


class Block(object):

    """Bloque de datos"""

    def __init__(self, headers, lines):
        self.headers = [ValidHeader(x) for x in headers]
        self.lines = lines

    def __iter__(self):
        for csvline in self.lines:
            yield (csvline.lineno, csvline.as_dict(self.headers))


class TableLoader(dict):
    """Cargador de ficheros de datos

    Un fichero de datos es basicamente una forma mas resumida de definir
    una estructura de "diccionarios" python, mediante CSV

    todos los objetos de un fichero de datos son diccionarios
    con una ruta, y un conjunto de valores.

    Este objeto carga y almacena, por cada ruta, un parser capaz de
    cargar los datos correspondientes a esa ruta.

    Las claves del diccionario son los paths serializados, con sus
    componentes separados por un ".".
    """

    def __init__(self):
        dict.__init__(self)

    def read(self, source, data):
        """Actualiza el ParserDict con los datos de la fuente."""
        try:
            self.lineno = "N/A"
            self.data = data
            self._doread(source)
        except (SyntaxError, ValueError) as details:
            raise DataError(source, self.lineno, details)

    def _doread(self, source):
        """Realiza el procesamiento, no filtra excepciones"""
        tokenizer = Tokenizer(source, DATA_COMMENT)
        path, title, lines = None, None, []
        for (self.lineno, line) in tokenizer.tokens():
            head = line.pop(0).strip() or None
            if head:
                # si es una anotacion, la agregamos a la linea
                if head == DATA_ANNOTATION:
                    if lines:
                        lines[-1].annotate(line)
                # si no lo es, pasamos de tabla.
                else:
                    head = [ValidHeader(x) for x in head.split(".")]
                    if path and title and lines:
                        self._update(source, path, title, lines)
                    path, title, lines = head, line, []
            elif line:
                lines.append(CSVLine(self.lineno, line))
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

