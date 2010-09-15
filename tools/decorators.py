#!/usr/bin/env python


from collections import defaultdict

from plantillator.resolver import Resolver
from plantillator.meta import SYMBOL_SELF


def resolver(func):
    """Decorador que convierte una funcion en un RootResolver
    
    La funcion debe recibir un item y devolver el valor resuelto.
    """
    class Inner(Resolver):
        def __init__(self):
            super(Inner, self).__init__(symbol=SYMBOL_SELF)
        def _resolve(self, symbol_table):
            item = super(Inner, self)._resolve(symbol_table)
            return func(item)
    return Inner()


def format(formatstr):
    """Un resolvedor muy simple, aplica formato a un objeto.
    
    Por ejemplo,
    
    Nodos(format("%(id)s, %(nombre)s")=="3, Emasesa")
    """
    @resolver
    def apply_format(item):
        return formatstr % dict(item.iteritems())
    return apply_format
