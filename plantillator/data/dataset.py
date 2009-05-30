#!/usr/bin/env python
# -*- vim: expandtab tabstop=4 shiftwidth=4 smarttab autoindent

import itertools
import re
from os import linesep

from data.operations import Deferrer


def not_none(filter_me):
    """Devuelve los objetos de la lista que no son None"""
    return (x for x in filter_me if x is not None)


def BaseMaker(basetype):

    class BaseSequence(basetype):

        def __add__(self, other):
            """Concatena dos secuencias"""
            return BaseSequence(itertools.chain(self, asIter(other)))

        def __call__(self, arg):
            """Devuelve el subconjunto de elementos que cumple el criterio"""
            if not hasattr(arg, '__call__'):
                arg = (Deferrer() == arg)
            return BaseSequence(x for x in self if arg(x))

    return BaseSequence


BaseList = BaseMaker(tuple)
BaseSet = BaseMaker(frozenset)


def normalize(item):
    """Normaliza un elemento

    Convierte los enteros en enteros, las cadenas vacias en None,
    y al resto le quita los espacios de alrededor.

    Si se quiera tratar un numero como una cadena de texto, hay que
    escaparlo entre comillas simples.
    """
    item = item.strip()
    if item.isdigit():
        return int(item)
    if item.startswith("'") and item.endswith("'"):
        return item[1:-1]
    return item or None if not item.isspace() else None


def asList(varlist):
    """Interpreta una cadena de caracteres como una lista

    Crea al vuelo una lista a partir de una cadena de caracteres. La cadena
    es un conjunto de valores separados por ','.
    """
    return BaseList(normalize(i) for i in str(varlist).split(","))


def asSet(varlist):
    """Interpreta una cadena de caracteres como un set

    Crea al vuelo una lista a partir de una cadena de caracteres. La cadena
    es un conjunto de valores separados por ','.
    """
    return BaseSet(normalize(i) for i in str(varlist).split(","))


_RANGO = re.compile(r'^(?P<pref>.*[^\d])?(?P<from>\d+)\s*\-\s*(?P<to>\d+)(?P<suff>[^\d].*)?$')

def asRange(varrange):
    """Interpreta una cadena de caracteres como un rango

    Crea al vuelo un rango a partir de una cadena de caracteres.
    La cadena es un rango (numeros separados por '-'), posiblemente
    rodeado de un prefijo y sufijo no numerico.
    """
    match, rango = _RANGO.match(str(varrange)), []
    if match:
        start = int(match.group('from'))
        stop = int(match.group('to'))
        pref = match.group('pref') or ''
        suff = match.group('suff') or ''
        for i in range(start, stop+1):
            rango.append(normalize("%s%d%s" % (pref, i, suff)))
    return BaseList(rango)


def asIter(item):
    return item if hasattr(item, "__iter__") else (item,)


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

