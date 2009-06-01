#!/usr/bin/env python
# -*- vim: expandtab tabstop=4 shiftwidth=4 smarttab autoindent

import itertools
import re
from os import linesep

from data.operations import Deferrer
from data.base import not_none, BaseSet


class DataSet(set):

    """Lista de DataObjects con un DataType comun"""

    def __init__(self, mytype, data=None):
        """Crea una lista vacia"""
        set.__init__(self, data or tuple())
        self._type = mytype

    def __call__(self, *arg, **kw):
        """Busca los elementos de la lista que cumplan los criterios dados"""
        crit = self._type.adapt(arg, kw)
        dset = DataSet(self._type, (x for x in self if x._matches(crit)))
        return dset if len(dset) != 1 else dset.pop()

    def __add__(self, other):
        """Concatena dos DataSets"""
        if self._type != other._type:
            raise TypeError, other._type
        return DataSet(self._type, itertools.chain(self, other))

    def __getitem__(self, item):
        """Selecciona un item en la lista

        Devuelve un set con los distintos valores del atributo seleccionado
        en cada uno de los elementos de la lista.

        Si el atributo seleccionado es una sublista, en lugar de un set
        se devuelve un ScopeList con todos los elementos encadenados.
        """
        items = not_none(x.get(item) for x in self)
        stype = self._type.subtypes.get(item, None)
        if stype is not None:
            return DataSet(stype, itertools.chain(*tuple(items)))
        return BaseSet(items)

    def __getattr__(self, attrib):
        return self[attrib]

    @property
    def up(self):
        return DataSet(self._type.up, not_none(x.up for x in self))
