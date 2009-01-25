#!/usr/bin/env python
# -*- vim: expandtab tabstop=4 shiftwidth=4 smarttab autoindent

from itertools import chain

from myoperator import MyFrozenset
from scopetype import DataSignature


class ScopeList(list, DataSignature):
    """Lista de ScopeDicts con un ScopeType comun"""

    __iter__ = list.__iter__

    def __init__(self, dicttype, data=None):
        """Crea una lista vacia"""
        list.__init__(self, data or tuple())
        self._type = dicttype

    def _collapse(self, key, dicttype, data):
        """Colapsa la tupla dada

        Si la tupla contiene un solo elemento, devuelve el elemento
        (que se supone que es un ScopeDict). Si tiene varios,
        devuelve un ScopeList del tipo indicado.

        Si la tupla tiene longitud 0, lanza un KeyError
        """
        if len(data) == 0:
            raise KeyError, key
        if len(data) == 1:
            return data[0]
        return ScopeList(dicttype, data)

    def __call__(self, *arg, **kw):
        """Busca los elementos de la lista que cumplan los criterios dados.

        Si solo hay un elemento en la lista que cumpla los criterios,
        devuelve ese elemento unico.

        Si hay mas de uno, devuelve un DataList "reducido" (no pueden
        insertarse campos).

        Si no hay ninguno, lanza un KeyError.
        """
        items = (x for x in self if x._matches(self._type.normcrit(arg, kw)))
        return self._collapse((arg, kw), self._dicttype, tuple(items))

    def __getattr__(self, attrib):
        """Selecciona un atributo en la lista

        Devuelve un set con los distintos valores del atributo seleccionado
        en cada uno de los elementos de la lista.

        Si el atributo seleccionado es una sublista, en lugar de un set
        se devuelve un ScopeList con todos los elementos encadenados.
        """
        items = (item.get(attrib, None) for item in self)
        items = tuple(x for x in items if x is not None)
        if not len(items):
            raise KeyError, attrib
        stype = self._type.subtypes.get(attrib, None)
        if stype:
            return self._collapse(attrib, stype, tuple(chain(*items)))
        return MyFrozenset(items)

    @property
    def up(self):
        sublist = tuple(item.up for item in self if item.up is not None)
        return self._collapse('up', self._type.up, sublist)


