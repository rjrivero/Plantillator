#!/usr/bin/env python
# -*- vim: expandtab tabstop=4 shiftwidth=4 smarttab autoindent encoding=utf-8


import operator
import re
from itertools import chain

from .ip import IPAddress


def BaseMaker(basetype):

    class BaseSequence(basetype):

        def __add__(self, other):
            """Concatena dos secuencias"""
            return BaseSequence(chain(self, asIter(other)))

        def __call__(self, arg):
            """Devuelve el subconjunto de elementos que cumple el criterio"""
            if not hasattr(arg, '__call__'):
                arg = (Deferrer() == arg)
            return BaseSequence(x for x in self if arg(x))

        def __pos__(self):
            if len(self) == 1:
                return list(self).pop()
            raise IndexError(0)

    return BaseSequence


BaseList = BaseMaker(tuple)
BaseSet  = BaseMaker(frozenset)


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


def asIter(item):
    """Se asegura de que el objeto es iterable"""
    return item if hasattr(item, '__iter__') else (item,)


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


class Deferrer(object):

    """Factoria de operadores

    Cuando se le aplica un operador de comparacion a un objeto de
    este tipo, el resultado es un version pospuesta de ese operador.

    Por ejemplo, (MyOperator() >= 5) devuelve un operador
    pospuesto que, al ser aplicado sobre una variable X, devuelve
    el resultado de "<X> >= 5".
    """

    def _defer(self, operator, operand):
        """Devuelve una funcion f(x) == operator(x, operand)
        Comprueba si x es una lista, y en ese caso, lo que compara es
        la longitud de x (es decir, f(x) == operator(len(x), operand))
        """
        def evaluate(deferred):
            if hasattr(deferred, '__iter__'):
                deferred = len(deferred)
            return operator(deferred, operand)
        return evaluate

    def __call__(self, item):
        return bool(item)

    def __eq__(self, other):
        return self._defer(operator.eq, other)

    def __ne__(self, other):
        return self._defer(operator.ne, other)

    def __lt__(self, other):
        return self._defer(operator.lt, other)

    def __le__(self, other):
        return self._defer(operator.le, other)

    def __gt__(self, other):
        return self._defer(operator.gt, other)

    def __ge__(self, other):
        return self._defer(operator.ge, other)

    def __mul__(self, arg):
        """Comprueba la coincidencia con una exp. regular"""
        return self._defer(lambda x, y: y.search(x) and True or False,
                          re.compile(arg))

    def __add__(self, arg):
        """Comprueba la pertenecia a una lista"""
        return self._defer(lambda x, y: x in asIter(y), arg)

    def __sub__(self, arg):
        """Comprueba la no pertenencia a una lista"""
        return self._defer(lambda x, y: x not in asIter(y), arg)



class Filter(Deferrer):

    """Factoria de operadores

    Cuando se le aplica un operador de comparacion a un objeto de
    este tipo, el resultado es un version pospuesta de ese operador.

    Por ejemplo, (MyOperator() >= 5) devuelve un operador
    pospuesto que, al ser aplicado sobre una variable X, devuelve
    el resultado de "len(<X(*arg, **kw)>)) >= 5".
    """

    def __init__(self, *arg, **kw):
        super(Filter, self).__init__()
        self.arg = arg
        self.kw = kw

    def _defer(self, operator, operand):
        """Devuelve una funcion f(x) == operator(len(x(*arg, **kw)), operand)
        Es decir, filtra x, y luego compara la longitud de la lista filtrada
        con el operand.
        """
        def evaluate(deferred):
            deferred = len(deferred(*self.arg, **self.kw))
            return operator(deferred, operand)
        return evaluate

    def __call__(self, deferred):
        return len(deferred(*self.arg, **self.kw)) == len(deferred)

