#!/usr/bin/env python
# -*- vim: expandtab tabstop=4 shiftwidth=4 smarttab autoindent encoding=utf-8

import re
from itertools import chain

from .ip import IPAddress
from .oset import OrderedSet
from .resolver import asIter
from .filter import Deferrer

SYMBOL_SELF   = 0
SYMBOL_FOLLOW = 1


class DataError(Exception):

    """Error de lectura de datos. Incluye source, id y mensaje"""

    def __init__(self, source, itemid, errmsg):
        self.source = source
        self.itemid = itemid
        self.errmsg = errmsg

    def __str__(self):
        error = [
            "%s [ %s ]" % (str(self.source), str(self.itemid)),
            str(self.errmsg)
        ]
        # error.extend(traceback.format_exception(*self.exc_info))
        return "\n".join(error)


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
    # NUEVO: normalizo IPs
    if item.count("/") == 1:
        try:
            return IPAddress(item).validate()
        except Exception:
            pass
    # si no es ni entero ni IP ni escapado, limpio y devuelvo.
    return item or None if not item.isspace() else None


def BaseMaker(basetype):

    class BaseSequence(basetype):

        def __add__(self, other):
            """Concatena dos secuencias"""
            return self.__class__(chain(self, asIter(other)))

        def __call__(self, *args):
            """Devuelve el subconjunto de elementos que cumple el criterio"""
            return self._filter({}, args)

        def __pos__(self):
            if len(self) == 1:
                return list(self).pop()
            raise IndexError(0)

        def _matches(self, symbols, args):
            """Devuelve los objetos que cumplen los criterios"""
            # Normalizo los criterios y los convierto en objetos
            d = Deferrer()
            args = tuple(x if hasattr(x, '_verify') else (d == x)
                           for x in args)
            # Filtro los elementos con los criterios
            for item in self:
                symbols[SYMBOL_SELF] = item
                if all(x._verify(symbols, item) for x in args):
                    yield item

        def follow(self, table, **kw):
            """Sigue una referencia

            Devuelve un diccionario donde cada clave es uno de los elementos del set,
            y el valor correspondiente es el resultado de filtrar la tabla
            con los criterios dados.
            """
            domd = table._domd
            crit = domd.crit(kw)
            return dict((x, domd.filterset({SYMBOL_FOLLOW: x}, table, crit)) for x in self)

        def _filter(self, symbols, args):
            """como __call__, pero recibe una tabla de simbolos."""
            return self.__class__(self._matches(symbols, args))

    return BaseSequence


BaseList = BaseMaker(tuple)
BaseSet  = BaseMaker(OrderedSet)


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
    else:
        rango = [normalize(str(varrange))]
    return BaseList(rango)

