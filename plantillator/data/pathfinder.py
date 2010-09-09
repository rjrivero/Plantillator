#!/usr/bin/env python
# -*- vim: expandtab tabstop=4 shiftwidth=4 smarttab autoindent


import os
import os.path


class InputSource(object):

    """Proveedor de entrada

    Objeto file-like que implementa la funcion read()
    """

    def __init__(self, id=None):
        """El ID debe ser univoco.

        Se usa, por ejemplo, para evitar procesar dos veces el mismo fichero.
        """
        self.id = id

    def read(self, mode="r"):
        """Lee la fuente como un bloque"""
        pass

    def resolve(self, sourcename):
        """Devuelve una nueva fuente correspondiente al nombre dado"""
        raise NotImplementedError, "%s.resolve" % self.__class.__name__

    def __str__(self):
        return str(self.id)


class FileSource(InputSource):

    """Wrapper sobre un fichero"""

    def __init__(self, fullpath=None, resolvepath=None):
        super(FileSource, self).__init__(os.path.abspath(fullpath))
        self.path = PathFinder(resolvepath)
        self.path.insert(0, os.path.dirname(self.id))

    def read(self, mode="r"):
        return open(self.id, mode).read()

    def resolve(self, sourcename):
        return FileSource(self.path(sourcename), self.path)

    def __str__(self):
        return os.path.basename(self.id)


class StringSource(InputSource):

    """Wrapper sobre un string"""

    def __init__(self, desc, stream):
        super(StringSource, self).__init__(desc)
        self.stream = stream

    def read(self, mode="r"):
        return self.stream


class PathFinder(list):

    """Localizador de ficheros

    Busca ficheros en un path determinado.
    """

    def __init__(self, path=None):
        """Establece el path de busqueda."""
        super(PathFinder, self).__init__(path or [])
        self.insert(0, ".")

    def __call__(self, fname):
        """Busca el fichero en la ruta definida

        Si encuentra el fichero, devuelve su path completo. Si no lo
        encuentra, lanza un ValueError.
        """
        try:
            return next(self.every(fname))
        except StopIteration:
            raise ValueError("File %s not found in %" % (fname, os.pathsep.join(self)))

    def every(self, fname):
        """Itera sobre todos los ficheros coincidentes en la ruta definida"""
        for fpath in (os.path.join(dir, fname) for dir in self):
            if os.path.isfile(fpath):
                yield fpath

    def insert(self, pos, item):
        """Si el objeto ya estaba en la lista, lo cambia"""
        try:
            self.pop(self.index(item))
        except ValueError:
            pass
        super(PathFinder, self).insert(pos, item)

    def __getslice__(self, i, j):
        return PathFinder(super(PathFinder, self).__getslice__(i, j))
