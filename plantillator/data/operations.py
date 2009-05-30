#!/usr/bin/env python
# -*- vim: expandtab tabstop=4 shiftwidth=4 smarttab autoindent encoding=utf-8

import operator
import re
import itertools


def asIter(item):
    """Se asegura de que un objeto es iterable"""
    return item if hasattr(item, '__iter__') else (item,)


class DeferredOp(object):

    """Operador pospuesto

    Pospone la evaluacion de un operador binario
    """

    def __init__(self, operator, operand):
        self.operator = operator
        self.operand  = operand

    def __call__(self, deferred):
        """Ejecuta la operacion diferida"""
        if hasattr(deferred, '__iter__'):
            deferred = len(deferred)
        return self.operator(deferred, self.operand)


class DeferredFilter(object):

    """Operador pospuesto

    Pospone la evaluacion de un operador binario sobre una lista filtrada
    """

    def __init__(self, operator, operand, filt):
        self.filt = filt
        self.operator = operator
        self.operand  = operand

    def __call__(self, deferred):
        """Ejecuta la operacion diferida"""
        return self.operator(len(self.filt(deferred)), self.operand)


class Deferrer(object):

    """Factoria de operadores

    Cuando se le aplica un operador de comparacion a un objeto de
    este tipo, el resultado es un version pospuesta de ese operador.

    Por ejemplo, (MyOperator() >= 5) devuelve un operador
    pospuesto que, al ser aplicado sobre una variable X, devuelve
    el resultado de "<X> >= 5".
    """

    def __eq__(self, other):
        return DeferredOp(operator.eq, other)

    def __ne__(self, other):
        return DeferredOp(operator.ne, other)

    def __lt__(self, other):
        return DeferredOp(operator.lt, other)

    def __le__(self, other):
        return DeferredOp(operator.le, other)

    def __gt__(self, other):
        return DeferredOp(operator.gt, other)

    def __ge__(self, other):
        return DeferredOp(operator.ge, other)

    def __call__(self, item):
        return bool(item)

    def __mul__(self, arg):
        """Comprueba la coincidencia con una exp. regular"""
        return DeferredOp(lambda x, y: y.search(x) and True or False,
                          re.compile(arg))

    def __add__(self, arg):
        """Comprueba la pertenecia a una lista"""
        return DeferredOp(lambda x, y: x in asIter(y), arg)

    def __sub__(self, arg):
        """Comprueba la no pertenencia a una lista"""
        return DeferredOp(lambda x, y: x not in asIter(y), arg)


class Filter(object):

    """Factoria de operadores

    Cuando se le aplica un operador de comparacion a un objeto de
    este tipo, el resultado es un version pospuesta de ese operador.

    Por ejemplo, (MyOperator() >= 5) devuelve un operador
    pospuesto que, al ser aplicado sobre una variable X, devuelve
    el resultado de "len(filter(<X>)) >= 5".
    """

    def __init__(self, *arg, **kw):
        self.arg = arg
        self.kw = kw

    def __call__(self, deferred):
        return deferred(*self.arg, **self.kw)

    def __eq__(self, other):
        return DeferredFilter(operator.eq, other, self)

    def __ne__(self, other):
        return DeferredFilter(operator.ne, other, self)

    def __lt__(self, other):
        return DeferredFilter(operator.lt, other, self)

    def __le__(self, other):
        return DeferredFilter(operator.le, other, self)

    def __gt__(self, other):
        return DeferredFilter(operator.gt, other, self)

    def __ge__(self, other):
        return DeferredFilter(operator.ge, other, self)

