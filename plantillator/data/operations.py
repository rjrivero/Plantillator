#!/usr/bin/env python
# -*- vim: expandtab tabstop=4 shiftwidth=4 smarttab autoindent encoding=utf-8

import operator
import re
import itertools


class DeferredOp(object):

    """Operador pospuesto

    Pospone la evaluacion de un operador binario
    """

    def __init__(self, operator, operand):
        self.operator = operator
        self.operand  = operand

    def __call__(self, deferred):
        return self.operator(deferred, self.operand)


class DeferredAny(object):

    """Operador pospuesto adaptado a listas

    Aplica un operador unario sobre cada elemento de una lista,
    evalua a verdadero si al menos un elemento de la lista evalua
    a verdadero.
    """

    def __init__(self, unary_operator):
        self.operator = unary_operator

    def __call__(self, deferred):
        return any(self.operator(item) for item in deferred)


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
        return DeferredOp(lambda x, y: y.search(x) and True or False, re.compile(arg))

    def __add__(self, arg):
        """Comprueba la pertenecia a una lista"""
        return DeferredOp(lambda x, y: x in y, arg)

    def __sub__(self, arg):
        """Comprueba la no pertenencia a una lista"""
        return DeferredOp(lambda x, y: x not in y, arg)

