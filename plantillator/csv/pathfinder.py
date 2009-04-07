#!/usr/bin/env python
# -*- vim: expandtab tabstop=4 shiftwidth=4 smarttab autoindent

import os.path
from gettext import gettext as _


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


class FileSource(LineSource):

    """Wrapper sobre un fichero"""

    def __init__(self, includepath, filename):
        LineSource.__init__(self, os.path.abspath(filename))
        self.path = PathFinder(includepath)
        self.path.insert(0, os.path.dirname(self.id))

    def readlines(self, mode="r"):
        return open(self.id, mode).readlines()

    def resolve(self, sourcename):
        return FileSource(self.path, self.path(sourcename))


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

    def __init__(self, path):
        """Establece el path de busqueda."""
        list.__init__(self, path)
        if not "." in self:
            self.append(".")

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
        raise ValueError, _("No se encuentra %s en %s" % (fname, self))
