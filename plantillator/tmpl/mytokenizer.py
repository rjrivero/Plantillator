#!/usr/bin/env python
# -*- vim: expandtab tabstop=4 shiftwidth=4 smarttab autoindent

import os.path
from gettext import gettext as _


class LineSource(object):

    """Proveedor de lineas

    Objeto file-like que implementa la funcion readlines().
    """

    def __init__(self, uniqid=None):
        """El ID debe ser univoco.

        Se usa, por ejemplo, para evitar procesar dos veces el mismo fichero.
        """
        self.id = uniqid

    def readlines(self, mode="r"):
        """Lee las lineas de la fuente indicada"""
        raise NotImplementedError, "%s.readlines" % self.__class.__name__

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
        return self.path.find(sourcename)

    def __str__(self):
        return os.path.basename(self.id)


class StringSource(LineSource):

    """Wrapper sobre un string"""

    def __init__(self, uniqid, stream):
        LineSource.__init__(self, uniqid)
        self.lines = stream.split("\n")

    def readlines(self, mode="r"):
        return self.lines

    def __str__(self):
        return self.id


class PathFinder(list):

    """Localizador de ficheros

    Busca ficheros en un path determinado.
    """

    _FILENOTFOUND = _("File %(file)s not found in %(path)s")

    def __init__(self, path):
        """Establece el path de busqueda."""
        list.__init__(self, path)
        if not "." in self:
            self.append(".")

    def __getslice__(self, i, j):
        return PathFinder(list.__getslice__(self, i, j))

    def find(self, fname):
        """Busca el fichero en la ruta definida

        Si encuentra el fichero, devuelve un FileSource conectado con el
        fichero. Si no lo encuentra, lanza un ValueError.
        """
        for dir in self:
            fpath = os.path.join(dir, fname)
            if os.path.isfile(fpath):
                return FileSource(self, fpath)
        raise ValueError, self._FILENOTFOUND % {
            'file': fname, 'path': str(self) }


class Tokenizer(object):

    """Flujo de tokens

    Divide la entrada en lineas, y cada linea en "tokens".
    Los tokens los define la aplicacion, sobrecargando la funcion "_tokenize".
    """

    _ERRMESSAGE = _("SOURCE %(source)s, LINE %(line)d: %(message)s")

    def __init__(self, source):
        """Conecta el tokenizer a un flujo de lineas

        Genera los atributos:
            "source": objeto source.
            "lineno": numero de linea, comienza en 0.
        """
        self.source = source
        self.lineno = 0

    def tokens(self):
        """Iterador que genera un flujo de tokens"""
        for self.lineno, line in enumerate(self.source.readlines()):
            for token in self._tokenize(line):
                yield token

    def error(self, msg):
        """Genera un error de sintaxis con el mensaje dado"""
        raise SyntaxError, self._ERRMESSAGE % {
                'source': self.source,
                'line': self.lineno+1,
                'message': msg
            }

    def _tokenize(self, line):
        """Divide una linea en tokens"""
        return (line.rstrip(),)

    def __str__(self):
        """Genera un mensaje indicando fuente y linea actual"""
        return "%s, LINE %d" % (str(self.source), self.lineno+1)


