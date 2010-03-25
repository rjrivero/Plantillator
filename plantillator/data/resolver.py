#!/usr/bin/env python
# -*- vim: expandtab tabstop=4 shiftwidth=4 smarttab autoindent encoding=utf-8


def asIter(item):
    """Se asegura de que el objeto es iterable"""
    return item if hasattr(item, '__iter__') else (item,)


class ChainedResolver(object):

    """Resolvedor encadenado

    Sirve como base para los resolvedores de atributos y filtrado,
    y permite que se encadenen unos con otros:

    x = ChainedResolver().attrib1.attrib2(*arg, **kw).attrib3
    y = x._resolve(item) ==> y = item.attrib1.attrib2(*arg, **kw).attrib3
    """

    def __init__(self, parent):
        self._parent = parent

    def __getattr__(self, attrib):
        if attrib.startswith("_"):
            raise AttributeError(attrib)
        return AttrResolver(self, attrib)

    def __call__(self, *arg, **kw):
        return FilterResolver(self, arg, kw)

    def __pos__(self):
        return PosResolver(self)

    def _resolve(self, symbols):
        return self._parent._resolve(symbols)


class RootResolver(ChainedResolver):

    """Resolvedor raiz

    Sirve como raiz de una cadena de Resolvedores. Almacena
    el atributo "_symbol"
    """

    def __init__(self, symbol):
        super(RootResolver, self).__init__(None)
        self._symbol = symbol

    def _resolve(self, symbols):
        return symbols[self._symbol]


class AttrResolver(ChainedResolver):

    """Resolvedor de atributos

    Sirve para posponer el acceso a los atributos de un objeto. Por ejemplo,

    x = AttrResolver().attrib1.attrib2
    y = x._resolve(item) ==> y = item.attrib1.attrib2
    """

    def __init__(self, parent, attrib):
        super(AttrResolver, self).__init__(parent)
        self._attrib = attrib

    def _resolve(self, symbols):
        item = super(AttrResolver, self)._resolve(symbols)
        return item.get(self._attrib)


class FilterResolver(ChainedResolver):

    """Resolvedor de filtrados

    Sirve para posponer el filtrado de una lista. Por ejemplo,

    x = FilterResolver(*args, *kw)
    y = x._resolve(item) ==> y = item(*args, **kw)
    """

    def __init__(self, parent, arg, kw):
        super(FilterResolver, self).__init__(parent)
        self._arg = arg
        self._kw = kw

    def _resolve(self, symbols):
        item = super(FilterResolver, self)._resolve(symbols)
        return item(*self._arg, **self._kw)


class PosResolver(ChainedResolver):

    """Resolvedor del operador prefijo "+"

    Permite posponer la extraccion de un elemento de una lista.
    """

    def __init__(self, parent):
        super(PosResolver, self).__init__(parent)

    def _resolve(self, symbols):
        item = super(PosResolver, self)._resolve(symbols)
        return +item


class ListResolver(object):

    """Resolvedor de listas

    Resuelve una lista con referencias dinamicas a un objeto
    """

    def __init__(self, items):
        self._items = items

    def _resolve(self, symbols):
        return tuple(x if not hasattr(x, '_resolve') else x._resolve(symbols)
                       for x in self._items)

