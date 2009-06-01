#!/usr/bin/env python
# -*- vim: expandtab tabstop=4 shiftwidth=4 smarttab autoindent


import os.path
import itertools

from data.pathfinder import PathFinder, FileSource
from data.base import normalize
from csvread.datatokenizer import DataTokenizer


DATA_COMMENT = "!"


class TableLoader(object):
    """Cargador de ficheros de datos

    Un fichero de datos es basicamente una forma mas resumida de definir
    una estructura de "diccionarios" python, mediante CSV

    todos los objetos de un fichero de datos son diccionarios
    con una ruta, y un conjunto de valores.
    """

    def read(self, source):
        """Carga un fichero de datos

        Devuelve un diccionario de tablas. Los indices del diccionario
        son los nombres de la tabla (ejemplo: nodo.switches.interfaces).
        Los valores son listas de bloques, donde cada bloque es un conjunto
        de lineas consecutivas debajo de un mismo encabezado.
        """
        tokenizer = DataTokenizer(source, DATA_COMMENT)
        title, lines, tables = None, [], dict()
        for line in tokenizer.tokens():
            body = list(normalize(field) for field in line)
            head = body.pop(0)
            if head:
                if title is not None:
                    tables.setdefault(title, []).append(lines)
                title, lines = head, []
            lines.append((tokenizer.lineno, body))
        if title is not None:
            tables.setdefault(title, []).append(lines)
        return tables


if __name__ == "__main__":
    import sys
    import pprint
    for f in sys.argv[1:]:
        finder = PathFinder()
        source = FileSource(finder(f), finder)
        loader = TableLoader()
        pprint.pprint(loader.read(source))

