#!/usr/bin/env python
# -*- vim: expandtab tabstop=4 shiftwidth=4 smarttab autoindent encoding=utf-8


import re
import itertools
import functools
from gettext import gettext as _

from data.namedtuple import NamedTuple
from data.datatype import DataType
from data.dataobject import DataObject
from engine.base import *


# cadenas de error
_UNDEFINED_BLOCK = _("El bloque %(blockname)s no esta definido")
_NOT_SELECTED = _("No se ha seleccionado un(a) %(var)s")
_WRONG_PARAMS = _("La cadena %(params)s no es valida")


def as_iterator(item):
    """Se asegura de que un objeto es iterable"""
    return item if hasattr(item, '__iter__') else (item,)


YieldBlock = NamedTuple("YieldBlock",
    """Bloque que es lanzado por un comando para indicar que necesita
    informacion o procesamiento adicional para traducir un patron
    """,
    opcode=0, command=1, glob=2, data=3)


class Condition(Command):
    """Condicion.
    Concuerda si una expresion es verdadera.
    """

    def match(self, glob, data):
        try:
            return bool(eval(self.expr, glob, data)) if self.expr else True
        except (AttributeError, KeyError):
            return False

    def run(self, glob, data):
        if self.match(glob, data):
            return Command.run(self, glob, data)
        return tuple()


class ConditionNot(Condition):
    """Condicion negada
    Concuerda si una expresion es falsa o si lanza un AttributeError
    o un KeyError (tipico de acceder a un objeto que no existe).
    """

    def match(self, glob, data):
        try:
            return not bool(eval(self.expr, glob, data)) if self.expr else True
        except (AttributeError, KeyError):
            return True


class ConditionExist(Condition):
    """Comprobacion de variable
    Concuerda si una variable esta definida en la lista que
    (se espera que) devuelva la evaluzacion de una expresion.
    """

    def match(self, glob, data):
        try:
            expr = eval(self.expr, glob, data)
            if (self.var in expr):
                return True
        except (AttributeError, KeyError):
            return False
        

class ConditionNotExist(ConditionExist):
    """Comprobacion de no existencia de variable
    Concuerda si una variable no esta en la lista que (se espera que)
    devuelva la evaluacion de una expresion, o si al intentar
    evaluar la expresion se lanza un AttributeError o un KeyError.
    """

    def match(self, glob, data):
        try:
            expr = eval(self.expr, glob, data)
            if not (self.var in expr):
                return True
        except (AttributeError, KeyError):
            return True


class CommandFor(Command):
    """Iterador sobre una lista.
    Itera sobre los elementos de una lista interpretando los comandos
    del bloque. Agrupa los resultados y los inserta en un "set", de forma
    que si varias iteraciones prdocuen exactamente el mismo resultado,
    este se elimina.
    """

    def run(self, glob, data):
        try:
            expr = as_iterator(eval(self.expr, glob, data))
        except (AttributeError, KeyError):
            return
        forset = set()
        for item in expr:
            data[self.var], result = item, list()
            for shot in Command.run(self, glob, data):
                if type(shot) == str:
                    result.append(shot)
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
        except (AttributeError, KeyError):
            pass


class CommandDefine(Command):
    """Comando "define"

    Asigna un nombre al bloque. Luego, el bloque puede invocarse por
    su nombre en cualquier otro punto del patron.
    """

    def __init__(self, token, match):
        Command.__init__(self, token, match)
        if self.params:
            self.params = tuple(x.strip() for x in self.params.split(","))
        else:
            self.params = tuple()
        self.fake_type = DataType(None)
        for item in self.params:
            if item != self.fake_type.add_field(item):
                raise ParseError(None, token,
                                 _WRONG_PARAMS % {'params': str(self.params)})

    def invoke(self, glob, data, params):
        if len(params) != len(self.params):
            raise ValueError(params)
        vals = dict(zip(self.params, params))
        data = DataObject(self.fake_type, vals, data)
        return Command.run(self, glob, data)

    def run(self, glob, data):
        self.run = lambda self, glob, data: tuple()
        data.setdefault("_blocks", {})[self.blockname] = self
        return tuple()


class CommandRecall(Command):
    """Invocacion de bloque
    Inserta un bloque previamente definido. Antes de insertarlo, ejecuta el
    cuerpo del bloque recall, para poder utilizarlo para definir variables
    y cosas asi.
    """

    def run(self, glob, data):
        try:
            block = data._blocks[self.blockname]
        except (AttributeError, KeyError):
            raise ValueError(_UNDEFINED_BLOCK % {'blockname': self.blockname})
        params = eval(self.params, glob, data) if self.params else tuple()
        return itertools.chain(Command.run(self, glob, data),
                               block.invoke(glob, data, params))


class CommandInclude(Command):
    """Inserta un fichero "en-linea"
    Sustituye el bloque por un fichero externo.
    """

    def run(self, glob, data):
        yield YieldBlock("INCLUDE", self, glob, data)
        # despues del yield, espera que alguien le haya puesto en
        # "included" el fichero que tiene que ejecutar.
        for block in self.included.run(glob, data):
            yield block
        # En la proxima ejecucion no hace falta volver a pasar por este tramite.
        self.run = self.included.run

class CommandSelect(Command):
    """Seleccion de variable
    Comprueba si <var> esta definida. si no lo esta,
    pide al usuario que seleccione un valor de la lista <expr>
    """

    def run(self, glob, data):
        if self.var in data:
            return
        elif not self.expr:
            raise ValueError, self.var
        # Antes de lanzar el yield, almacena en self.pick la lista
        # de objetos de la que se puede elegir la variable. De esta forma,
        # si evaluar la expresion provoca algun error, sera capturado y tratado
        # como un CommandError
        self.pick = list(as_iterator(eval(self.expr, glob, data)))
        yield YieldBlock("SELECT", self, glob, data)
        if not self.var in data:
            raise ValueError(_NOT_SELECTED % {'var': var})


class CommandAppend(Command):
    """comando "append"
    Coloca un fichero en la lista de proceso, para ser procesado
    despues del fichero actual.
    """

    def run(self, glob, data):
        yield YieldBlock("APPEND", self, glob, data)
        self.run = lambda glob, data: tuple()

