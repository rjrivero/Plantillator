#!/usr/bin/env python
# -*- vim: expandtab tabstop=4 shiftwidth=4 smarttab autoindent


from itertools import chain

from ..data.base import BaseSet, Deferrer


def not_none(filter_me):
    """Devuelve los objetos de la lista que no son None"""
    return (x for x in filter_me if x is not None)


class CSVSet(set):

    """Lista de CSVObjects"""

    def __init__(self, _type, data=None):
        """Crea una lista vacia"""
        set.__init__(self, data or tuple())
        self._type = _type

    def __call__(self, **kw):
        """Busca los elementos de la lista que cumplan los criterios dados"""
        d = Deferrer()
        crit = dict((k, (v if hasattr(v, '__call__') else (d == v)))
                    for k, v in kw.iteritems())
        return self._type._DOMD.new_set(x for x in self if x._matches(crit))

    def __add__(self, other):
        """Concatena dos DataSets"""
        if self._type != other._type:
            raise TypeError(other._type)
        return self._type._DOMD.new_set(self, other)

    def __pos__(self):
        if len(self) == 1:
            return self.copy().pop()
        raise IndexError(0)

    def __getitem__(self, attr):
        """Selecciona un item en la lista

        Devuelve un set con los distintos valores del atributo seleccionado
        en cada uno de los elementos de la lista.

        Si el atributo seleccionado es una sublista, en lugar de un set
        se devuelve un DataSet con todos los elementos encadenados.
        """
        domd  = self._type._DOMD
        if attr in domd.attribs:
            return BaseSet(not_none(x.get(attr) for x in self))
        try:
            domd = domd.subtype(attr)._DOMD
        except AttributeError as details:
            raise KeyError(details)
        else:
            return domd.new_set(*tuple(not_none(x.get(attr) for x in self)))

    def __getattr__(self, attr):
        try:
            return self[attr]
        except KeyError as details:
            raise AttributeError(details)

    @property
    def up(self):
        data = not_none(x._up for x in self)
        return self._type._DOMD.parent._DOMD.new_set(data)
