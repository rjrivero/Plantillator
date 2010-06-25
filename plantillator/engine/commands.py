#!/usr/bin/env python
# -*- vim: expandtab tabstop=4 shiftwidth=4 smarttab autoindent encoding=utf-8


import sys
import re
import itertools
import functools
from collections import namedtuple
from gettext import gettext as _
from operator import attrgetter

from ..data import asIter, Fallback, OrderedSet
from .base import *


# cadenas de error
_UNDEFINED_BLOCK = _("El bloque %(blockname)s no esta definido")
_NOT_SELECTED = _("No se ha seleccionado un(a) %(var)s")
_WRONG_PARAMS = _("La cadena %(params)s no es valida")
_ELSE_WITHOUT_IF = _("\"si no\" desemparejado")


YieldBlock = namedtuple("YieldBlock", "opcode, command, glob, data")


class Condition(Command):
    """Condicion.
    Concuerda si una expresion es verdadera.
    """

    def __init__(self, tree, token, match):
        Command.__init__(self, tree, token, match)
        self.backup_expr = self.expr
        if self.expr:
            self.expr = compile(self.expr, '<string>', 'eval')

    def match(self, glob, data):
        try:
            return bool(eval(self.expr, glob, data)) if self.expr else True
        except (AttributeError, KeyError, NameError):
            return False

    def run(self, glob, data):
        self.matched = self.match(glob, data)
        return Command.run(self, glob, data) if self.matched else tuple()

    def _style(self, style):
        style.keyword("si")
        style.expression(self.backup_expr)


class ConditionNot(Condition):
    """Condicion negada
    Concuerda si una expresion es falsa o si lanza un AttributeError
    o un KeyError (tipico de acceder a un objeto que no existe).
    """

    def match(self, glob, data):
        try:
            return not bool(eval(self.expr, glob, data)) if self.expr else True
        except (AttributeError, KeyError, NameError):
            return True

    def _style(self, style):
        style.keyword("si no")
        style.expression(self.backup_expr)


class ConditionExist(Condition):
    """Comprobacion de variable
    Concuerda si una variable esta definida en la lista que
    (se espera que) devuelva la evaluacion de una expresion.
    """

    def match(self, glob, data):
        try:
            expr = eval(self.expr, glob, data)
            if expr[self.var] is not None:
                return True
        except (AttributeError, KeyError, NameError):
            return False

    def _style(self, style):
        style.keyword("si hay")
        style.variable(self.var)
        style.keyword("en")
        style.expression(self.backup_expr)


class ConditionNotExist(ConditionExist):
    """Comprobacion de no existencia de variable
    Concuerda si una variable no esta en la lista que (se espera que)
    devuelva la evaluacion de una expresion, o si al intentar
    evaluar la expresion se lanza un AttributeError o un KeyError.
    """

    def match(self, glob, data):
        try:
            expr = eval(self.expr, glob, data)
            if expr[self.var] is None:
                return True
        except (AttributeError, KeyError, NameError):
            return True

    def _style(self, style):
        style.keyword("si no existe")
        style.expression(self.backup_expr)


class CommandPython(Command):
    """Comando "python"
    """

    def __init__(self, tree, token, match):
        Command.__init__(self, tree, token, match)
        self.backup_expr = self.expr
        self.expr = compile(self.expr, '<string>', 'exec')

    def run(self, glob, data):
        exec self.expr in glob, data
        return Command.run(self, glob, data)

    def _style(self, style):
        style.keyword("python")
        style.expr(self.backup_expr)


class CommandElse(Command):
    """Comando "else"
    Concuerda si el "if" previo no lo ha hecho.
    """

    def run(self, glob, data):
        if not self.prev.matched:
            return Command.run(self, glob, data)
        return tuple()

    def chainto(self, prev):
        if not isinstance(prev, Condition):
            raise ParseError(None, self.token, _ELSE_WITHOUT_IF)
        self.prev = prev

    def _style(self, style):
        style.keyword("si no")


class CommandFor(Command):
    """Iterador sobre una lista.
    Itera sobre los elementos de una lista interpretando los comandos
    del bloque. Agrupa los resultados y los inserta en un "set", de forma
    que si varias iteraciones prdocuen exactamente el mismo resultado,
    este se elimina.
    """

    def __init__(self, tree, token, match):
        Command.__init__(self, tree, token, match)
        try:
            self.sortby = attrgetter(match.group('sortby'))
        except IndexError:
            self.sortby = None
        self.backup_expr = self.expr
        self.expr = compile(self.expr, '<string>', 'eval')

    def run(self, glob, data):
        try:
            expr = asIter(eval(self.expr, glob, data))
            if self.sortby:
                expr = sorted(expr, key=self.sortby)
            else:
                expr = sorted(expr)
        except (AttributeError, KeyError):
            return
        forset = OrderedSet()
        for item in expr:
            data[self.var], result = item, list()
            for shot in Command.run(self, glob, data):
                if type(shot) == str:
                    result.append(shot)
                else:
                    yield shot
            forset.add("".join(result))
        yield "".join(forset)

    def _style(self, style):
        style.keyword("por cada")
        style.variable(self.var)
        style.keyword("de")
        style.expression(self.backup_expr)


class CommandSet(Command):
    """Comando "set"
    Ejecuta una asignacion.
    """

    def __init__(self, tree, token, match):
        Command.__init__(self, tree, token, match)
        self.assign = "%s = %s" % (self.var, self.expr)
        self.assign = compile(self.assign, '<string>', 'exec')

    def run(self, glob, data):
        exec self.assign in glob, data
        return Command.run(self, glob, data)

    def _style(self, style):
        style.variable(self.var)
        style.keyword("=")
        style.expression(self.expr)


class CommandSetIf(Command):
    """Comando "setif"
    Ejecuta una asignacion, si no genera error.
    """

    def __init__(self, tree, token, match):
        Command.__init__(self, tree, token, match)
        self.backup_expr = self.expr
        self.expr = compile(self.expr, '<string>', 'eval')

    def run(self, glob, data):
        try:
            data[self.var] = eval(self.expr, glob, data)
        except:
            data.setdefault(self.var, None)
        return Command.run(self, glob, data)

    def _style(self, style):
        style.variable(self.var)
        style.keyword("?=")
        style.expression(self.backup_expr)


class CommandDefine(Command):
    """Comando "define"

    Asigna un nombre al bloque. Luego, el bloque puede invocarse por
    su nombre en cualquier otro punto del patron.
    """

    VALID = re.compile(VARPATTERN['var']).match

    def __init__(self, tree, token, match):
        Command.__init__(self, tree, token, match)
        if self.params:
            self.params = tuple(x.strip() for x in self.params.split(","))
        else:
            self.params = tuple()
        for item in self.params:
            if not CommandDefine.VALID(item):
                raise ParseError(None, token,
                                 _WRONG_PARAMS % {'params': str(self.params)})
        tree.blocks[self.blockname] = self

    def invoke(self, glob, data, params):
        if len(params) != len(self.params):
            raise ValueError(params)
        vals = dict(zip(self.params, params))
        data = Fallback(data, vals, 2)
        return Command.run(self, glob, data)

    def run(self, glob, data):
        data.setdefault("_blocks", {})[self.blockname] = self
        return tuple()

    def _style(self, style):
        style.keyword("bloque")
        style.variable(self.blockname)
        if self.params:
            style.keyword("(")
            for param in self.params[:-1]:
                style.variable(param)
                style.keyword(',')
            style.variable(self.params[-1])
            style.keyword(")")


class CommandRecall(Command):
    """Invocacion de bloque
    Inserta un bloque previamente definido. Antes de insertarlo, ejecuta el
    cuerpo del bloque recall, para poder utilizarlo para definir variables
    y cosas asi.
    """

    def __init__(self, tree, token, match):
        Command.__init__(self, tree, token, match)
        # Me aseguro de que self.params evalua a una tupla.
        # si el cuerpo de la llamada tiene un solo argumento, evaluarlo
        # no devolveria una tupla y la ejecucion del comando fallaria.
        self.backup_params = self.params
        self.blocks = tree.blocks
        if self.params:
            self.params = self.params.strip()[1:-1].strip()
            self.params = "(%s,)" % self.params if self.params else None
            self.params = compile(self.params, '<string>', 'eval')

    def run(self, glob, data):
        """Busca el bloque en data._blocks o en el cmdtree.
        Ejecuta el cuerpo del primero que encuentre.
        """
        blockset, block = data.get("_blocks"), None
        if blockset:
            block = blockset.get(self.blockname)
        if not block:
            block = self.blocks.get(self.blockname)
        if not block:
            raise ValueError(_UNDEFINED_BLOCK % {'blockname': self.blockname})
        params = eval(self.params, glob, data) if self.params else tuple()
        return itertools.chain(Command.run(self, glob, data),
                               block.invoke(glob, data, params))

    def _style(self, style):
        style.keyword(self.blockname)
        style.expression(self.backup_params)


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

    def _style(self, style):
        style.keyword("incluir")
        style.expression(self.path)


class CommandSelect(Command):
    """Seleccion de variable
    Comprueba si <var> esta definida. si no lo esta,
    pide al usuario que seleccione un valor de la lista <expr>
    """

    def __init__(self, tree, token, match):
        Command.__init__(self, tree, token, match)
        self.backup_expr = self.expr
        if self.expr:
            self.expr = compile(self.expr, '<string>', 'eval')

    def run(self, glob, data):
        # Con este test comprobamos que el valor que seleccionamos
        # esta definido y no es una lista vacia.
        if data.get(self.var):
            return
        if not self.expr:
            raise ValueError, self.var
        # Antes de lanzar el yield, almacena en self.pick la lista
        # de objetos de la que se puede elegir la variable. De esta forma,
        # si evaluar la expresion provoca algun error, sera capturado y tratado
        # como un CommandError
        self.pick = list(asIter(eval(self.expr, glob, data)))
        yield YieldBlock("SELECT", self, glob, data)
        if data.get(self.var, None) is None:
            raise ValueError(_NOT_SELECTED % {'var': self.var})

    def _style(self, style):
        style.keyword("utiliza")
        if self.art:
            style.keyword(self.art)
        style.variable(self.var)
        style.keyword("de")
        style.expression(self.backup_expr)


class CommandAppend(Command):
    """comando "append"
    Coloca un fichero en la lista de proceso, para ser procesado
    despues del fichero actual.

    El path especificado en el comando puede indicar un nombre de fichero
    de salida usando la sintaxis

    path -> expresion

    La expresion se evalua y el resultado de ejecutar el patron se
    guarda en el fichero cuyo nombre resulte de la expresion, relativo
    al directorio de salida.
    """

    def __init__(self, tree, token, match):
        Command.__init__(self, tree, token, match)
        self.outpath_expr = None
        self.outpath_backup = None
        self.outpath = None
        path = self.path.split("->")
        self.path = path.pop(0).strip()
        if path:
            self.outpath_backup = path[0].strip()
            self.outpath_expr = compile(self.outpath_backup, '<string>', 'eval')

    def run(self, glob, data):
        self.outpath = None if not self.outpath_expr else eval(self.outpath_expr, glob, data)
        yield YieldBlock("APPEND", self, glob, data)
        # no sustituyo el run, para que el comando sea repetible.
        # self.run = lambda glob, data: tuple()

    def _style(self, style):
        style.keyword("procesar")
        style.variable(self.path)
        if self.outpath_expr:
            style.keyword("->")
            style.expression(self.outpath_backup)


class CommandSection(Command):
    """Comando "section"
    Etiqueta un bloque de codigo (una seccion) con un nombre que
    puede ser utilizado para acceder al bloque
    """

    def __init__(self, tree, token, match):
        Command.__init__(self, tree, token, match)
        tree.sections[self.label] = self

    def _style(self, style):
        style.keyword("seccion")
        style.variable(self.label)


class CommandDot(PostProcessor):
    """Comando "Dot"
    Genera un gráfico en formato dot (Graphviz).

    Bloque lanzado:
     * graph: texto del gráfico, en formato .dot
     * outfile: nombre del fichero a generar
     * program: programa (dot, neato. fdp, circle, twopi)
    """

    def __init__(self, tree, token, match):
        PostProcessor.__init__(self, tree, token, match)
        try:
            # Recupero el programa, por defecto "dot".
            self.program = self.program.lower()
        except AttributeError:
            self.program = 'dot'
        try:
            # Recupero la lista de formatos, por defecto ("png",)
            self.formats = set(x.strip() for x in self.formats.lower().split())
        except AttributeError:
            self.formats = set("png",)
        #
        # Dividimos la expresion en expresion propiamente dicha, y posible
        # destino para el cmapx
        #
        expr = self.expr.split("->")
        self.backup_expr = expr.pop(0).strip()
        self.expr = compile(self.backup_expr, '<string>', 'eval')
        cmapname = expr[0].strip() if expr else ""
        if cmapname.isalnum():
            self.formats.add("cmapx")
        self.cmapname = cmapname or None

    def postprocess(self, input, glob, data):
        self.outfile = eval(self.expr, glob, data)
        # Si el nombre de fichero me lo dan con una extension que coincida
        # con algun formato, se la quito.
        for f in self.formats:
            f = ".%s" % f
            if self.outfile.endswith(f):
                self.outfile = self.outfile[:-len(f)]
        self.graph = "".join(input)
        yield YieldBlock("DOT", self, glob, data)
        if self.cmapname:
            data[self.cmapname] = self.cmapx

    def _style(self, style):
        progname = "dot" if self.program == "dot" else "dot:%s" % self.program
        style.keyword(progname)
        for f in self.formats:
            style.keyword(f)
        style.expression(self.backup_expr)
