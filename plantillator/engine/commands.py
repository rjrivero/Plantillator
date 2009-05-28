#!/usr/bin/env python
# -*- vim: expandtab tabstop=4 shiftwidth=4 smarttab autoindent encoding=utf-8


import re
import functools
from gettext import gettext as _


# nombres de variables permitidos
VARPATTERN = {
    'varflat': r'[a-zA-Z][\w\_]*',
}
# marcadores de parametros a reemplazar
PLACEHOLD = re.compile(r'\?(?P<expr>[^\?]+)\?')

_RUNTIME_ERROR = _("Error ejecutando %(command)s")
_ERROR_LOCATION = _("Origen %(fname)s, linea $(lineno)d")


class CommandError(Exception):

    """Excepcion que se lanza al detectar un error procesando el template.

    Encapsula la excepcion original, y el bloque que la ha originado:

    - self.token:     Token que levanto la excepcion
    - self.data:      datos que se estaban evaluando
    - self.exc_info:  datos de la excepcion original

    Estas excepciones son excepciones de tiempo de proceso. Las excepciones
    durante el parsing se indican con SyntaxErrors.
    """

    def __init__(self, source, token, data):
        self.source = source
        self.token  = token
        self.data   = data
        self.exc_info = exc_info()


def as_iterator(func):
    """Decorador que se asegura de que la funcion devuelva algo iterable"""
    @functools.wraps(func)
    def wrap(self, data):
        result = func(self, data)
        return result or tuple()
    return wrap


class Literal(object):

    def __init__(self, token):
        self.token = token

    def run(data):
        try:
            yield PLACEHOLD.sub(data.replace, token.body)
        except KeyError:
            raise CommandError(None, token, data)

    def __str__(self):
        return self.token.head or self.token.body


def Condition(list):

    def __init__(self, token, expr):
        list.__init__(self)
        self.token = token
        self.expr = expr

    def match(self, data):
        try:
            return eval(self.expr, data) if self.expr else True
        except AttributeError, KeyError:
            return False
        
    def run(self, data):
        for item in self:
            for block in item.run(data):
                yield block


def ConditionFalse(Condition):

    def match(self, data):
        try:
            return not eval(self.expr, data) if self.expr else True
        except AttributeError, KeyError:
            return True


def ConditionExist(Condition):

    def __init__(self, token, var, expr):
        list.__init__(self)
        self.token = token
        self.var = var
        self.expr = expr

    def match(self, data):
        try:
            expr = eval(self.expr, data)
            if (self.var in expr) and expr[self.var]:
                return True
        except AttributeError, KeyError:
            return False
        

def ConditionNotExist(ConditionExist):

    def match(self, data):
        try:
            expr = eval(self.expr, data)
            if not (self.var in expr) or not expr[self.var]:
                return True
        except AttributeError, KeyError:
            return True


def Command_If(list):

    def __init__(self, token):
        list.__init__(self)
        self.token = token

    def match(self, data):
        for item in self:
            if item.match(data):
                return item

    def run(self, data):
        try:
            match = self.match(data)
        except:
            raise CommandError(self.token, data)
        else:
            return match.run(data)
