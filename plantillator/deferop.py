#!/usr/bin/env python
# -*- vim: expandtab tabstop=4 shiftwidth=4 smarttab autoindent encoding=utf-8

import operator


class DeferredOperation(object):

    """Operador pospuesto

    Pospone la evaluacion de un operador binario
    """

    def __init__(self, operator, operand):
        self.operator = operator
        self.operand  = operand

    def __call__(self, deferred):
        if hasattr(deferred, "__iter__"):
            return any(self.operator(item, self.operand) for item in deferred)
        return self.operator(deferred, self.operand)


def binary_in(op1, op2):
    return op1 in op2

def binary_notin(op1, op2):
    return op1 not in op2


class DeferOp(object):

    """Factoria de operadores

    Cuando se le aplica un operador de comparacion a un objeto de
    este tipo, el resultado es un version pospuesta de ese operador.

    Por ejemplo, (DeferOp() >= 5) devuelve un operador
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

    def __add__(self, other):
        return DeferredOperation(binary_in, other)

    def __sub__(self, other):
        return DeferredOperation(binary_notin, other)

    def __call__(self, item):
        return bool(item)

