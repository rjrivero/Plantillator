#!/usr/bin/env python
# -*- vim: expandtab tabstop=4 shiftwidth=4 smarttab autoindent


import os
import os.path
import sys
import codecs

try:
    import chardet
except ImportError:
    pass

from codecs import BOM_UTF8

# Creo el locale para poder luego consultar el encoding por defecto
try:
    import locale
    locale.setlocale(locale.LC_CTYPE, "")
except (ImportError, locale.Error):
    pass


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

    @classmethod
    def get_default_encoding(cls):
        try:
            return cls.ENCODING
        except AttributeError:
            pass
        if sys.platform == 'win32':
            encoding = locale.getdefaultlocale()[1]
        else:
            try:
                encoding = locale.nl_langinfo(locale.CODESET)
            except (NameError, AttributeError):
                encoding = locale.getdefaultlocale()[1]
        try:
            encoding = encoding.lower() if encoding else 'ascii'
            codecs.lookup(encoding)
        except LookupError:
            encoding = 'ascii'
        cls.ENCODING = encoding
        return encoding

    def as_unicode(self, data):
        if data.startswith(BOM_UTF8):
            return unicode(data[3:], "utf-8")
        try:
            return unicode(data)
        except UnicodeError:
            pass
        try:
            return unicode(data, FileSource.get_default_encoding())
        except UnicodeError:
            pass
        try:
            codec = chardet.detect(data)["encoding"]
            return unicode(data, codec)
        except (NameError, UnicodeError):
            pass
        return data

    def __init__(self, abspath, resolvepath=None):
        super(FileSource, self).__init__(abspath)
        if resolvepath is not None:
            # Si no nos pasaran un resolvepath, seria porque no se va a usar
            # la parafernalia de resoluciones... solo la instanciamos si la
            # vamos a usar.
            self.path = PathFinder(resolvepath)
            self.path.insert(0, os.path.dirname(self.id))

    def read(self):
        """Devuelve el texto del fichero, en un formato estandar.
        
        Actualmente lo devuelve en utf-8 porque este modulo es para
        python 2.X, y hay cosas que con unicode no funcionan bien (ej:
        el modulo csv).
        
        Lamentablemente, en python <= 3.1, el modulo csv tampoco funciona
        bien con unicode... habra que esperar.
        """
        with open(self.id, "rb") as infile:
            return self.as_unicode(infile.read()).replace(u"\r\n", u"\n").encode("utf-8")

    def resolve(self, sourcename):
        assert(hasattr(self, "path"))
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
            raise ValueError("File %s not found in %s" % (fname, os.pathsep.join(self)))

    def every(self, fname):
        """Itera sobre todos los ficheros coincidentes en la ruta definida"""
        for fpath in (os.path.join(dir, fname) for dir in self):
            if os.path.isfile(fpath):
                yield os.path.abspath(fpath)

    def insert(self, pos, item):
        """Si el objeto ya estaba en la lista, lo cambia"""
        try:
            self.pop(self.index(item))
        except ValueError:
            pass
        super(PathFinder, self).insert(pos, item)

    def __getslice__(self, i, j):
        return PathFinder(super(PathFinder, self).__getslice__(i, j))
