#!/usr/bin/env python
# -*- vim: expandtab tabstop=4 shiftwidth=4 smarttab autoindent


from data.datatype import DataType
from data.datalist import DataList

     
class NamedDict(object):

    """Objeto cuyos atributos pueden accederse como diccionario"""

    def __init__(self, data=None):
        """Inicializa el NamedDict con los datos especificados"""
        if data:
            self.__dict__.update(data)

    def __getitem__(self, key):
        """Busca el atributo en el objeto y los fallbacks"""
        try:
            return getattr(self, key)
        except AttributeError:
            raise KeyError, key

    def __setitem__(self, key, val):
        """Almacena un valor en el diccionario"""
        return setattr(self, key, val)

    def __contains__(self, key):
        """Devuelve True si hay un atributo con ese nombre"""
        return key in self.__dict__


class DataObject(NamedDict):

    """Objeto accesible por "scopes"

    Puede accederse a los valores del diccionario por clave, o como
    atributos del abjeto. Si se hace referencia a una clave que no
    existe, sube en la jerarquia buscando la clave.
    """

    def __init__(self, mytype, data=None, fallback=None):
        """Inicializa el DataObject con los datos y fallback especificados"""
        NamedDict.__init__(self, data)
        self.__type, self.up = mytype, fallback

    def __getattr__(self, attrib):
        """Busca el atributo en el objeto y los fallbacks

        Si el atributo no esta, lanza un KeyError, a menos que la clave
        corresponda a un subtipo. En ese caso, devuelve una lista vacia
        del subtipo adecuado.
        """
        if self.up and attrib not in self.__type.blocked:
            return getattr(self.up, attrib)
        try:
            return DataList(self.__type.subtypes[attrib])
        except KeyError:
            raise AttributeError, attrib

    def __matches(self, kw):
        """Comprueba si el atributo indicado cumple el criterio."""
        return all(crit(self.__get(key)) for key, crit in kw.iteritems)

    def __get(self, attrib, defval=None):
        """Busca el atributo, devuelve "defval" si no lo encuentra"""
        try:
            return getattr(self, attrib)
        except AttributeError:
            return defval

