#!/usr/bin/env python
# -*- vim: expandtab tabstop=4 shiftwidth=4 smarttab autoindent


from itertools import chain

from data.base import BaseSet


def not_none(filter_me):
    """Devuelve los objetos de la lista que no son None"""
    return (x for x in filter_me if x is not None)


class DataSet(set):

    """Lista de DataObjects"""

    def __init__(self, _type, data=None):
        """Crea una lista vacia"""
        set.__init__(self, data or tuple())
        self._type = _type

    def __call__(self, **kw):
        """Busca los elementos de la lista que cumplan los criterios dados"""
        crit = self._type._adapt(kw)
        data = DataSet(self._type, (x for x in self if x._matches(crit)))
        return data if len(data) != 1 else data.pop()

    def __add__(self, other):
        """Concatena dos DataSets"""
        if self._type != other._type:
            raise TypeError(other._type)
        return DataSet(self._type, chain(self, other))

    def _chain(self, itemlist):
        self.update(chain(*tuple(itemlist)))
        return self

    def __getitem__(self, attrib):
        """Selecciona un item en la lista

        Devuelve un set con los distintos valores del atributo seleccionado
        en cada uno de los elementos de la lista.

        Si el atributo seleccionado es una sublista, en lugar de un set
        se devuelve un DataSet con todos los elementos encadenados.
        """
        items = not_none(x.get(attrib) for x in self)
        try:
            return DataSet(self._type._Children[attrib])._chain(items)
        except KeyError:
            return BaseSet(items)

    def __getattr__(self, attrib):
        return self[attrib]

    @property
    def up(self):
        data = not_none(x._up for x in self)
        return DataSet(self._type._Parent, data)
