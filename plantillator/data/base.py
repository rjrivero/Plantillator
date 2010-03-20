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
            if not hasattr(arg, '_verify'):
                arg = (Deferrer() == arg)
            return BaseSequence(x for x in self if arg._verify(x))

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


class ChainedResolver(object):

    """Resolvedor encadenado

    Sirve como base para los reolvedores de atributos y filtrado,
    y permite que se encadenen unos con otros:

    x = ChainedResolver().attrib1.attrib2(*arg, **kw).attrib3
    y = x._resolve(item) ==> y = item.attrib1.attrib2(*arg, **kw).attrib3
    """

    def __init__(self, parent=None):
        self._parent = parent

    def __getattr__(self, attrib):
        if attrib.startswith("_"):
            raise AttributeError(attrib)
        return AttrResolver(self, attrib)

    def __call__(self, *arg, **kw):
        return FilterResolver(self, arg, kw)

    def __pos__(self):
        return PosResolver(self)

    def _resolve(self, item):
        return item if not self._parent else self._parent._resolve(item)


class AttrResolver(ChainedResolver):

    """Resolvedor de atributos

    Sirve para posponer el acceso a los atributos de un objeto. Por ejemplo,

    x = AttrResolver().attrib1.attrib2
    y = x._resolve(item) ==> y = item.attrib1.attrib2
    """

    def __init__(self, parent, attrib):
        super(AttrResolver, self).__init__(parent)
        self._attrib = attrib

    def _resolve(self, item):
        item = super(AttrResolver, self)._resolve(item)
        return item.get(self._attrib)


class FilterResolver(ChainedResolver):

    """Resolvedor de filtrados

    Sirve para posponer el filtrado de una lista. Por ejemplo,

    x = FilterResolver(*args, *kw)
    y = x._resolve(item) ==> y = item(*args, **kw)
    """

    def __init__(self, parent, *arg, **kw):
        super(FilterResolver, self).__init__(parent)
        self._arg = arg
        self._kw = kw

    def _resolve(self, item):
        item = super(FilterResolver, self)._resolve(item)
        return item(*self._arg, **self._kw)


class PosResolver(ChainedResolver):

    """Resolvedor del operador prefijo "+"

    Permite posponer la extraccion de un elemento de una lista.
    """

    def __init__(self, parent):
        super(PosResolver, self).__init__(parent)

    def _resolve(self, item):
        item = super(PosResolver, self)._resolve(item)
        return +item


class ListResolver(object):

    """Resolvedor de listas

    Resuelve una lista con referencias dinamicas a un objeto
    """

    def __init__(self, items):
        self.items = items

    def _resolve(self, item):
        return tuple(x if not hasattr(x, '_resolve') else x._resolve(item)
                       for x in self.items)


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
        self.operator = operator
        self.operand = operand

    def _verify(self, value, item=None):
        if hasattr(value, '__iter__'):
            value = len(value)
        return self.operator(value, self.operand)

    def _resolve(self, item):
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
        self.dynamic = operand

    def _verify(self, value, item):
        self.operand = self.dynamic._resolve(item)
        return super(DynamicCrit, self)._verify(value, item)

    def _resolve(self, item):
        """Resuelve los parametros dinamicos y devuelve un criterio estatico"""
        return StaticCrit(self.operator, self.dynamic._resolve(item))


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
        self.prefilter = prefilter

    def _verify(self, value, item):
        return super(FilterCrit, self)._verify(self.prefilter(value), item)


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

    def _verify(self, value, item=None):
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

    def _resolve(self, item):
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
        super(Filter, self).__init__()
        self.arg = arg
        self.kw = kw

    def _defer(self, operator, operand):
        """Devuelve una funcion f(x) == operator(len(x(*arg, **kw)), operand)
        Es decir, filtra x, y luego compara la longitud de la lista filtrada
        con el operand.
        """
        def prefilter(value):
            return len(value(*self.arg, **self.kw))
        return FilterCrit(operator, operand, prefilter)

    def _verify(self, value, item=None):
        return len(value(*self.arg, **self.kw)) == len(value)

