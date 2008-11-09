#!/usr/bin/env python
# -*- vim: expandtab tabstop=4 shiftwidth=4 smarttab autoindent encoding=utf-8

import operator


class UnaryOperator(object):

    """Operador unario"""

    def __call__(self):
        pass

    def __repr__(self):
        pass

    def __str__(self):
        pass


class DeferredOperation(UnaryOperator):

    """Operador pospuesto

    Pospone la evaluacion de un operador binario
    """

    def __init__(self, name, operator, operand):
        self.name = name
        self.operator = operator
        self.operand  = operand

    def __call__(self, deferred):
        return self.operator(deferred, self.operand)

    def __repr__(self):
        return "DeferredOperation(%s, %s, %s)" % (
                repr(self.name),
                repr(self.operator),
                repr(self.operand))

    def __str__(self):
        return "<X> %s %s" % (self.name, self.operand)


class DeferredAny(UnaryOperator):

    """Operador pospuesto adaptado a listas

    Aplica un operador unario sobre cada elemento de una lista,
    evalua a verdadero si al menos un elemento de la lista evalua
    a verdadero.
    """

    def __init__(self, unary_operator):
        self.operator = operator

    def __call__(self, deferred):
        return any(self.operator(item) for item in deferred)

    def __repr__(self):
        return "DeferredAny(%s)" % repr(self.operator)

    def __str__(self):
        return "any (%s) for <X> in [Y]" % (self.operator)


class MyOperator(UnaryOperator):

    """Factoria de operadores

    Cuando se le aplica un operador de comparacion a un objeto de
    este tipo, el resultado es un version pospuesta de ese operador.

    Por ejemplo, (MyOperator() >= 5) devuelve un operador
    pospuesto que, al ser aplicado sobre una variable X, devuelve
    el resultado de "<X> >= 5".
    """

    def __eq__(self, other):
        return DeferredOperation("==", operator.eq, other)

    def __ne__(self, other):
        return DeferredOperation("!=", operator.ne, other)

    def __lt__(self, other):
        return DeferredOperation("<",  operator.lt, other)

    def __le__(self, other):
        return DeferredOperation("<=", operator.le, other)

    def __gt__(self, other):
        return DeferredOperation(">",  operator.gt, other)

    def __ge__(self, other):
        return DeferredOperation(">=", operator.ge, other)

    def __call__(self, item):
        return bool(item)

    def __repr__(self):
        return "MyOperator()"

    def __str__(self):
        return "<X> == cualquiera"


class MySearcher(object):

    """Operador para comprobar la pertenencia a una lista"""

    def __eq__(self, arg):
        return DeferredOperation("any", lambda x, y: x in y, arg)

    def __ne__(self, *arg):
        return DeferredOperation("no", lambda x, y: x not in y, arg)

    def __repr__(self):
        return "MySearcher()"

    def __str__(self):
        return "<X> == [cualquiera ==|!=]"

