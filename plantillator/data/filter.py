#!/usr/bin/env python
# -*- vim: expandtab tabstop=4 shiftwidth=4 smarttab autoindent encoding=utf-8

import operator
import re

from .resolver import asIter, ListResolver


class StaticCrit(object):

    """Criterio estatico.

    Callable que comprueba si un par (atributo, objeto) cumple
    un cierto criterio.

    En este caso, el criterio es la comparacion del valor dado
    con un valor estatico.

    Si el atributo es una lista, lo que se compara es
    la longitud de esa lista. 
    """

    def __init__(self, operator, operand):
        self._operator = operator
        self._operand = operand

    def _verify(self, symbols, value):
        if hasattr(value, '__iter__'):
            value = len(value)
        return self._operator(value, self._operand)

    def _resolve(self, symbols):
        """Resuelve los parametros dinamicos y devuelve un criterio estatico"""
        return self


class DynamicCrit(StaticCrit):

    """Criterio dinamico

    Callable que comprueba si un par (atributo, objeto) cumple
    un cierto criterio.

    En este caso, el criterio es la comparacion del valor dado
    con un valor dinamico. El valor dinamico se calcula en funcion del
    propio objeto que se esta comparando.

    Si el atributo es una lista, lo que se compara es
    la longitud de esa lista. 
    """

    def __init__(self, operator, operand):
        super(DynamicCrit, self).__init__(operator, None)
        self._dynamic = operand

    def _verify(self, symbols, value):
        self._operand = self._dynamic._resolve(symbols)
        return super(DynamicCrit, self)._verify(symbols, value)

    def _resolve(self, symbols):
        """Resuelve los parametros dinamicos y devuelve un criterio estatico"""
        return StaticCrit(self._operator, self._dynamic._resolve(symbols))


class FilterCrit(StaticCrit):

    """Criterio estatico con prefiltro

    Callable que comprueba si un par (atributo, objeto) cumple
    un cierto criterio.

    En este caso, antes de comparar el valor, se le aplica un
    prefiltro.

    Si el atributo es una lista, lo que se compara es
    la longitud de esa lista. 
    """

    def __init__(self, operator, operand, prefilter):
        super(FilterCrit, self).__init__(operator, operand)
        self._prefilter = prefilter

    def _verify(self, symbols, value):
        value = self._prefilter(symbols, value)
        return super(FilterCrit, self)._verify(symbols, value)


class Deferrer(object):

    """Factoria de operadores

    Cuando se le aplica un operador de comparacion a un objeto de
    este tipo, el resultado es un version pospuesta de ese operador.

    Por ejemplo, (Deferrer() >= 5) devuelve un callable que, al ser
    invocado como <X>(item, attr) devuelve el resultado de
    "item.getattr(attr) >= 5".
    """

    def _dynlist(self, items):
        """Verifica si una lista tiene elementos dinamicos.

        Si no los tiene, devuelve la lista. Si los tiene, devuelve un
        callable que aplica el item a los elementos dinamicos de la lista.
        """
        # si "items" es un elemento dinamico, no lo convertimos a lista, sino
        # que confiamos en que el resultado de evaluarlo sera una lista.
        if hasattr(items, '_resolve'):
            return items
        # si no es un callable, nos aseguramos de que es iterable y
        # revisamos si tiene algun elemento dinamico.
        items = asIter(items)
        if not any(hasattr(x, '_resolve') for x in items):
            return items
        return ListResolver(items)

    def _defer(self, operator, operand):
        """Devuelve el criterio adecuado"""
        if not hasattr(operand, '_resolve'):
            return StaticCrit(operator, operand)
        return DynamicCrit(operator, operand)

    def _verify(self, symbols, value):
        return bool(value)

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
        return self._defer(lambda x, y: x in y, self._dynlist(arg))

    def __sub__(self, arg):
        """Comprueba la no pertenencia a una lista"""
        return self._defer(lambda x, y: x not in y, self._dynlist(arg))

    def _resolve(self, symbols):
        return self


class Filter(Deferrer):

    """Factoria de operadores

    Cuando se le aplica un operador de comparacion a un objeto de
    este tipo, el resultado es un version pospuesta de ese operador.

    Por ejemplo, (Filter() >= 5) devuelve un operador
    pospuesto que, al ser aplicado sobre una variable X, devuelve
    el resultado de "len(<X(*arg, **kw)>)) >= 5".
    """

    def __init__(self, *arg, **kw):
        if arg and kw:
            raise SyntaxError("Criterios incompatibles")
        super(Filter, self).__init__()
        self.params = arg or kw

    def _defer(self, operator, operand):
        """Devuelve una funcion f(x) == operator(len(x(*arg, **kw)), operand)
        Es decir, filtra x, y luego compara la longitud de la lista filtrada
        con el operand.
        """
        def prefilter(symbols, value):
            symbols = symbols.copy() # para que no machaque el self
            return len(value._filter(symbols, self.params))
        return FilterCrit(operator, operand, prefilter)

    def _verify(self, symbols, value):
        # copio la tabla de simbolos para que no me machaque el "self".
        symbols = symbols.copy()
        return len(value._filter(symbols, self.params)) == len(value)

