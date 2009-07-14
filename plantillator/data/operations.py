#!/usr/bin/env python
# -*- vim: expandtab tabstop=4 shiftwidth=4 smarttab autoindent encoding=utf-8


import operator
import re


def asIter(item):
    """Se asegura de que el objeto es iterable"""
    return item if hasattr(item, '__iter__') else (item,)


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
        self.arg = arg
        self.kw = kw

    def _defer(self, operator, operand):
        """Devuelve una funcion f(x) == operator(len(x(*arg, **kw)), operand)
        Es decir, filtra x, y luego compara la longitud de la lista filtrada
        con el operand.
        """
        def evaluate(deferred):
            deferred = deferred(*self.arg, **self.kw)
            return operator(len(deferred), operand)
        return evaluate

    def __call__(self, deferred):
        return len(deferred(*self.arg, **self.kw)) == len(deferred)
