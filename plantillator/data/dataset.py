#!/usr/bin/env python
# -*- vim: expandtab tabstop=4 shiftwidth=4 smarttab autoindent


from itertools import chain

from .base import BaseSet, Deferrer


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
        d = Deferrer()
        crit = dict((k, (v if hasattr(v, '__call__') else (d == v)))
                    for k, v in kw.iteritems())
        return self._type._NewSet(x for x in self if x._matches(crit))

    def __add__(self, other):
        """Concatena dos DataSets"""
        if self._type != other._type:
            raise TypeError(other._type)
        return self._type._NewSet(self, other)

    def __pos__(self):
        if len(self) == 1:
            return self.copy().pop()
        raise IndexError(0)

    def __getitem__(self, attrib):
        """Selecciona un item en la lista

        Devuelve un set con los distintos valores del atributo seleccionado
        en cada uno de los elementos de la lista.

        Si el atributo seleccionado es una sublista, en lugar de un set
        se devuelve un DataSet con todos los elementos encadenados.
        """
        if attrib in self._type.__dict__:
            raise AttributeError, attrib
        items = not_none(x.get(attrib) for x in self)
        try:
            return self._type._Properties[attrib]._type._NewSet(*tuple(items))
        except (KeyError, AttributeError):
            return BaseSet(items)

    def __getattr__(self, attrib):
        return self[attrib]

    @property
    def up(self):
        data = not_none(x._up for x in self)
        return self._type._Parent._NewSet(data)

