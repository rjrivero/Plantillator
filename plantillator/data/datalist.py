#!/usr/bin/env python
# -*- vim: expandtab tabstop=4 shiftwidth=4 smarttab autoindent


from itertools import chain
from data.operations import Deferrer


def not_none(filter_me):
    """Devuelve los objetos de la lista que no son None"""
    return (x for x in filter_me if x is not None)


class BaseSet(set):

    def __add__(self, other):
        """Concatena dos sets"""
        return BaseSet(itertools.chain(self, other))

    def __call__(self, arg):
        """Devuelve el subconjunto de elementos que cumple el criterio"""
        if not hasattr(arg, '__call__'):
            arg = (Deferrer() == arg)
        return BaseSet(x for x in self if arg(x))


class DataSet(set):

    """Lista de DataObjects con un DataType comun"""

    def __init__(self, mytype, data=None):
        """Crea una lista vacia"""
        set.__init__(self, data or tuple())
        self.__type = mytype

    def __call__(self, **kw):
        """Busca los elementos de la lista que cumplan los criterios dados"""
        crit = self.__type.adapt(kw)
        return DataList(self.__type, (x for x in self if x.__matches(crit)))

    def __add__(self, other):
        """Concatena dos DataSets"""
        if self.__type != other.__type:
            raise TypeError, other
        return DataSet(self.__type, chain(self, other))

    def __getattr__(self, attrib):
        """Selecciona un atributo en la lista

        Devuelve un set con los distintos valores del atributo seleccionado
        en cada uno de los elementos de la lista.

        Si el atributo seleccionado es una sublista, en lugar de un set
        se devuelve un ScopeList con todos los elementos encadenados.
        """
        items = not_none(item.__get(attrib) for item in self)
        stype = self.__type.subtypes.get(attrib, None)
        if stype is not None:
            return DataSet(subtype, chain(*tuple(items)))
        return BaseSet(items)

    @property
    def up(self):
        return DataSet(self.__type.up, not_none(item.up for item in self))

