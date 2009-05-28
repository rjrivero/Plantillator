#!/usr/bin/env python
# -*- vim: expandtab tabstop=4 shiftwidth=4 smarttab autoindent encoding=utf-8


import re
import functools
from gettext import gettext as _

from data.datatype import DataType
from data.dataobject import DataObject


# nombres de variables permitidos
VARPATTERN = {
    'var': r'[a-zA-Z][\w\_]*',
    'en':  r'en(\s+(el|la|los|las))?',
    'de':  r'(en|de|del)(\s+(el|la|los|las))?'
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

    def __init__(self, source, token, glob, data):
        self.source = source
        self.token  = token
        self.glob   = glob
        self.data   = data
        self.exc_info = exc_info()


def as_iterator(func):
    """Decorador que se asegura de que la funcion devuelva algo iterable"""
    @functools.wraps(func)
    def wrap(self, glob, data):
        result = func(self, glob, data)
        return result or tuple()
    return wrap


class Literal(object):
    def __init__(self, token):
        self.token = token

    def run(self, glob, data):
        yield PLACEHOLD.sub(data.replace, self.token.body)


class Command(list):

    def __init__(self, up, token, match):
        list.__init__(self)
        self.__dict__.update(match.groupdict())
        self.up = up
        self.token = token

    def __str__(self):
        return str(self.token)

    def chain(self, command):
        return self.up.chain(command)

    def run(self, glob, data):
        for item in self:
            try:
                for block in item.run(glob, data):
                    yield block
            except CommandError:
                raise
            except:
                raise CommandError(None, item.token, glob, data)


class Condition(Command):

    def match(self, glob, data):
        try:
            return bool(eval(self.expr, glob, data)) if self.expr else True
        except AttributeError, KeyError:
            return False


class ConditionFalse(Condition):

    def match(self, glob, data):
        try:
            return not bool(eval(self.expr, glob, data)) if self.expr else True
        except AttributeError, KeyError:
            return True


class ConditionExist(Condition):

    def match(self, glob, data):
        try:
            expr = eval(self.expr, glob, data)
            if (self.var in expr):
                return True
        except AttributeError, KeyError:
            return False
        

class ConditionNotExist(ConditionExist):

    def match(self, glob, data):
        try:
            expr = eval(self.expr, glob, data)
            if not (self.var in expr):
                return True
        except AttributeError, KeyError:
            return True


class CommandIf(Command):

    def __init__(self, up, token, match, condition):
        Command.__init__(self)
        self.append(condition(up, token, match))

    def match(self, glob, data):
        for item in self:
            try:
                if item.match(glob, data):
                    return item
            except CommandError:
                raise
            except:
                raise CommandError(None, item.token, glob, data)

    def run(self, glob, data):
        match = self.match(glob, data)
        if match:
            return match.run(glob, data)

class CommandFor(Command):

    def run(self, glob, data):
        try:
            expr = eval(self.expr, glob, data)
            if not hasattr(expr, '__iter__'):
                expr = (expr,)
        except AttributeError, KeyError:
            return
        forset = set()
        for item in expr:
            data[self.var], result = item, list()
            for shot in Command.run(self, data):
                if type(shot) == str:
                    result.append(item)
                else:
                    yield shot
            forset.add("".join(result))
        yield "".join(sorted(forset))


class CommandSet(Command):
    """Comando "set"

    Ejecuta una asignacion.
    """

    def run(self, glob, data):
        assign = "%s = %s" % (self.var, self.expr)
        try:
            exec(assign, glob, data) 
            return Command.run(glob, data)
        except AttributeError, KeyError:
            pass


class CommandDefine(Command):
    """Comando "define"

    Asigna un nombre al bloque. Luego, el bloque puede invocarse por
    su nombre en cualquier otro punto del patron.
    """

    def __init__(self, up, token, match):
        Command.__init__(self, up, token)
        if hasattr(self, 'params'):
            self.params = tuple(x.strip() for x in self.params.split(","))
        else:
            self.params = tuple()
        self.fake_type = DataType(None)
        for item in self.params:
            if item != self.fake_type.add_field(item):
                raise SyntaxError(item)

    def invoke(self, glob, data, params):
        if len(params) != len(self.params):
            raise ValueError(params)
        vals = dict(zip(self.params, params))
        data = DataObject(self.fake_type, vals, data)
        Command.run(self, glob, data)

    def run(self, glob, data):
        data._blocks[self.blockname] = self.invoke

