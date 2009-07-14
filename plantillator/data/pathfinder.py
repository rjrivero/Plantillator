#!/usr/bin/env python
# -*- vim: expandtab tabstop=4 shiftwidth=4 smarttab autoindent


import os
import os.path
from gettext import gettext as _


_FILE_NOT_FOUND = _("No se encuentra %(file)s en %(path)s")


class LineSource(object):

    """Proveedor de lineas

    Objeto file-like que implementa la funcion readlines().
    """

    def __init__(self, id=None):
        """El ID debe ser univoco.

        Se usa, por ejemplo, para evitar procesar dos veces el mismo fichero.
        """
        self.id = id

    def readlines(self, mode="r"):
        pass

    def resolve(self, sourcename):
        """Devuelve una nueva fuente correspondiente al nombre dado"""
        raise NotImplementedError, "%s.resolve" % self.__class.__name__

    def __str__(self):
        return str(self.id)


class FileSource(LineSource):

    """Wrapper sobre un fichero"""

    def __init__(self, fullpath=None, resolvepath=None):
        LineSource.__init__(self, os.path.abspath(fullpath))
        self.path = PathFinder(resolvepath)
        self.path.insert(0, os.path.dirname(self.id))

    def readlines(self, mode="r"):
        return open(self.id, mode).readlines()

    def resolve(self, sourcename):
        return FileSource(self.path(sourcename), self.path)

    def __str__(self):
        return os.path.basename(self.id)


class StringSource(LineSource):

    """Wrapper sobre un string"""

    def __init__(self, id, stream):
        LineSource.__init__(self, desc)
        self.lines = stream.split("\n")

    def readlines(self, mode="r"):
        return self.lines


class PathFinder(list):

    """Localizador de ficheros

    Busca ficheros en un path determinado.
    """

    def __init__(self, path=None):
        """Establece el path de busqueda."""
        list.__init__(self, path or [])
        self.insert(0, ".")

    def __getslice__(self, i, j):
        return PathFinder(list.__getslice__(self, i, j))

    def insert(self, pos, item):
        """Si el objeto ya estaba en la lista, lo cambia"""
        try:
            self.pop(self.index(item))
        except ValueError:
            pass
        list.insert(self, pos, item)

    def __call__(self, fname):
        """Busca el fichero en la ruta definida

        Si encuentra el fichero, devuelve un FileSource conectado con el
        fichero. Si no lo encuentra, lanza un ValueError.
        """
        for fpath in (os.path.join(dir, fname) for dir in self):
            if os.path.isfile(fpath):
                return fpath
        raise ValueError(_FILE_NOT_FOUND %
                         {'file': fname, 'path': os.pathsep.join(self)})
