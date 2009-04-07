#!/usr/bin/env python
# -*- vim: expandtab tabstop=4 shiftwidth=4 smarttab autoindent


from data.datatype import DataType
from data.datalist import DataSet


class DataObject(object):

    """Objeto accesible por "scopes"

    Puede accederse a los atributos del  objeto como si fueran valores de
    un diccionario. Si se hace referencia a un atributo que no existe, se sube
    en la jerarquia buscandolo.
    """

    def __init__(self, mytype, data=None, fallback=None):
        """Inicializa el DataObject con los datos y fallback especificados"""
        self.__dict__.update(data or dict())
        self.__type, self.up = mytype, fallback

    def __iter__(self):
        yield self

    def __getattr__(self, attrib):
        """Busca el atributo en el objeto y los fallbacks"""
        if self.up and attrib not in self.__type.blocked:
            return getattr(self.up, attrib)
        try:
            return DataSet(self.__type.subtypes[attrib])
        except KeyError:
            raise AttributeError, attrib

    def __setattr__(self, attrib, val):
        def iter(object):
            yield object
        if not hastattr(val, '__call__') or not hastattr(val, '__iter__'):
            newtype = type("newtype", (type(val),), {'__iter__': iter})
            try:
                val.__class__ = newtype
            except TypeError:
                val = newtype(val)
        object.__setattr__(self, attrib, val)

    def __getitem__(self, key):
        """Busca el atributo en el objeto y los fallbacks"""
        try:
            return getattr(self, key)
        except AttributeError:
            raise KeyError, key

    __setitem__ = setattr

    def __matches(self, kw):
        """Comprueba si el atributo indicado cumple el criterio."""
        return all(crit(self.__get(key)) for key, crit in kw.iteritems)

    def __get(self, attrib, defval=None):
        """Busca el atributo, devuelve "defval" si no lo encuentra"""
        try:
            return getattr(self, attrib)
        except AttributeError:
            return defval

    def __call__(self, **kw):
        """Devuelve el elemento actual, si cumple los criterios dados"""
        crit = self.__type.adapt(kw)
        return self if self.__matches(crit) else DataSet(self.__type)
