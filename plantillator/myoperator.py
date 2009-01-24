#!/usr/bin/env python
# -*- vim: expandtab tabstop=4 shiftwidth=4 smarttab autoindent encoding=utf-8

import operator
import re
import itertools


def normalize(item):
    """Normaliza un elemento

    Convierte los enteros en enteros, las cadenas vacias en None,
    y al resto le quita los espacios de alrededor.
    """
    item = item.strip()
    if item.isdigit():
        return int(item)
    item = item or None if not item.isspace() else None
    # si se quiera tratar un numero como una cadena de texto, hay que
    # escaparlo entre comillas simples.
    if item and item.startswith("'") and item.endswith("'"):
        item = item[1:-1] or None
    return item


def asList(varlist):
    """Interpreta una cadena de caracteres como una lista

    Crea al vuelo una lista a partir de una cadena de caracteres. La cadena
    es un conjunto de valores separados por ','.
    """
    return MyFrozenset(normalize(i) for i in str(varlist).split(","))


_RANGO = re.compile(r'^(?P<pref>.*[^\d])?(?P<from>\d+)\s*\-\s*(?P<to>\d+)(?P<suff>[^\d].*)?$')

def asRange(varrange):
    """Interpreta una cadena de caracteres como un rango

    Crea al vuelo un rango a partir de una cadena de caracteres.
    La cadena es un rango (numeros separados por '-'), posiblemente
    rodeado de un prefijo y sufijo no numerico.
    """
    match = _RANGO.match(str(varrange))
    rango = []
    if match:
        start = int(match.group('from'))
        stop = int(match.group('to'))
        pref = match.group('pref') or ''
        suff = match.group('suff') or ''
        for i in range(start, stop+1):
            rango.append(normalize("%s%d%s" % (pref, i, suff)))
    return MyFrozenset(rango)


def iterWrapper(expr):
    """Devuelve un iterable"""
    if operator.isMappingType(expr) or not hasattr(expr, '__iter__'):
        expr = (expr,)
    return expr


class MyFrozenset(frozenset):

    def __add__(self, other):
        if not hasattr(other, '__iter__'):
            other = asList(other)
        return MyFrozenset(itertools.chain(self, other))


class UnaryOperator(object):

    """Operador unario"""

    def __call__(self, item):
        raise NotImplementedError, "UnaryOperator"


class DeferredOperation(UnaryOperator):

    """Operador pospuesto

    Pospone la evaluacion de un operador binario
    """

    def __init__(self, operator, operand):
        self.operator = operator
        self.operand  = operand

    def __call__(self, deferred):
        return self.operator(deferred, self.operand)


class DeferredAny(UnaryOperator):

    """Operador pospuesto adaptado a listas

    Aplica un operador unario sobre cada elemento de una lista,
    evalua a verdadero si al menos un elemento de la lista evalua
    a verdadero.
    """

    def __init__(self, unary_operator):
        self.operator = unary_operator

    def __call__(self, deferred):
        return any(self.operator(item) for item in deferred)


class MyOperator(UnaryOperator):

    """Factoria de operadores

    Cuando se le aplica un operador de comparacion a un objeto de
    este tipo, el resultado es un version pospuesta de ese operador.

    Por ejemplo, (MyOperator() >= 5) devuelve un operador
    pospuesto que, al ser aplicado sobre una variable X, devuelve
    el resultado de "<X> >= 5".
    """

    def __eq__(self, other):
        return DeferredOperation(operator.eq, other)

    def __ne__(self, other):
        return DeferredOperation(operator.ne, other)

    def __lt__(self, other):
        return DeferredOperation(operator.lt, other)

    def __le__(self, other):
        return DeferredOperation(operator.le, other)

    def __gt__(self, other):
        return DeferredOperation(operator.gt, other)

    def __ge__(self, other):
        return DeferredOperation(operator.ge, other)

    def __call__(self, item):
        return bool(item)


class MySearcher(object):

    """Operador para comprobar la pertenencia a una lista"""

    def __eq__(self, arg):
        return DeferredOperation(lambda x, y: x in y, iterWrapper(arg))

    def __ne__(self, arg):
        return DeferredOperation(lambda x, y: x not in y, iterWrapper(arg))

