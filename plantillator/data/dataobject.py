#!/usr/bin/env python
# -*- vim: expandtab tabstop=4 shiftwidth=4 smarttab autoindent


from data.datatype import DataType
from data.datalist import DataList


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

    def __getattr__(self, attrib):
        """Busca el atributo en el objeto y los fallbacks"""
        if self.up and attrib not in self.__type.blocked:
            return getattr(self.up, attrib)
        try:
            return DataList(self.__type.subtypes[attrib])
        except KeyError:
            raise AttributeError, attrib

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

