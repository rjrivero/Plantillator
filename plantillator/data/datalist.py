#!/usr/bin/env python
# -*- vim: expandtab tabstop=4 shiftwidth=4 smarttab autoindent


from itertools import chain
from data.operations import Deferrer


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
        """Busca los elementos de la lista que cumplan los criterios dados.

        Si se llama sin ningun argumento, "colapsa" la lista:
             * Si la lista tiene un solo elemento, lo extrae y lo devuelve
             * Si tiene varios elementos (o ninguno), lanza KeyError
        """
        crit = self.__type.adapt(kw)
        return DataList(self.__type, (x for x in self if x.__matches(crit)))

    def __add__(self, other):
        """Concatena dos DataLists"""
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
        items = (x.__get(attrib, None) for x in self)
        items = (x for x in items if x is not None)
        stype = self.__type.subtypes.get(attrib, None)
        if stype is not None:
            return DataSet(subtype, chain(*tuple(items)))
        return BaseSet(items)

    @property
    def up(self):
        subset = (item.up for item in self if item.up is not None)
        return DataSet(self.__type.up, subset)

