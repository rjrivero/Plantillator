#!/usr/bin/env python
# -*- vim: expandtab tabstop=4 shiftwidth=4 smarttab autoindent encoding=utf-8

import itertools
import re
import operator
import functools
from os.path import basename, dirname

from mytokenizer import FileSource, Tokenizer
from tmplparser import TmplParser, CommandError
from dataparser import DataParser


# nombres de variables permitidos
VARPATTERN = {
    'varflat': r'[a-zA-Z][\w\_]*',
}


class CommandWrapper(object):

    """Ejecuta el comando asociado a un bloque"""

    def __init__(self, command, processor, match):
        self.command = command
        self.processor = processor
        self.match = match

    def __call__(self, block, data):
        try:
            return self.processor(self.match, block, data)
        except CommandError:
            # el CommandError original pasa inalterado
            raise
        except:
            # el resto, pasa encapsulado en un CommandError
            raise CommandError(block, data, self)

    def __str__(self):
        return self.command


def as_iterator(func):
    """Decorador que se asegura de que la funcion devuelva algo iterable"""
    @functools.wraps(func)
    def wrap(self, match, block, data):
        result = func(self, match, block, data)
        return result or tuple()
    return wrap


class CommandEngine(object):

    """Motor que interpreta todos los comandos del lenguaje del patron"""

    COMMANDS = [(re.compile(exp), cmd) for (exp, cmd) in (
        # comando SET
        # p.e. "var = var1 (+ var2)*
        (r'(?P<var>%(varflat)s)\s+(=|es\s)\s*(?P<expr>.*)' % VARPATTERN, 'set'),
        # comando FOR
        # p.e. "for var in path.to(list)"
        (r'(for|(por cada))\s+(?P<var>%(varflat)s)\s+(in|en|de|del)\s+((el|la|los|las)\s+)?(?P<expr>.*)' % VARPATTERN, 'for'),
        # comando IF NOT EXIST
        # p.e. "if not key in expr"
        (r'si no (hay|existe) (?P<var>%(varflat)s) en\s+((el|la|los|las)\s+)?(?P<expr>.*)' % VARPATTERN, 'notexist'),
        (r'si (?P<var>%(varflat)s) no esta en\s+((el|la|los|las)\s+)?(?P<expr>.*)' % VARPATTERN, 'notexist'),
        # comando IF EXIST
        # p.e. "if key in expr"
        (r'si (hay|existe) (?P<var>%(varflat)s) en\s+((el|la|los|las)\s+)?(?P<expr>.*)' % VARPATTERN, 'exist'),
        (r'si (?P<var>%(varflat)s) esta en\s+((el|la|los|las)\s+)?(?P<expr>.*)' % VARPATTERN, 'exist'),
        # Comando IF NOT
        # p.e. "if not expr"
        (r'((if not)|(si no))\s+(?P<expr>.*)', 'ifnot'),
        # Comando IF
        # p.e. "if expr"
        (r'(if|si)\s+(?P<expr>.*)', 'if'),
        # Comando INCLUDE
        # p.e. "include file"
        (r'(include|incluir|insertar)\s+(?P<path>.*)', 'include'),
        # Comando APPEND
        # p.e. "append file"
        (r'(append|procesar)\s+(?P<path>.*)', 'append'),
        # Comando SELECT
        # p.ej. "select <var> FROM <expr>"
        (r'(necesito|necesita|utilizo|utiliza)\s+(?P<art>un|una)\s+(?P<var>%(varflat)s)\s+(de|del)(\s+(la|las|los)\s+(lista\s+)?)?(?P<expr>.*)' % VARPATTERN, 'select'),
        # Comando DEFINE
        # p.ej. "define <blockname>"
        (r'(define|definir|bloque|funcion)\s+(?P<blockname>%(varflat)s)\s*' % VARPATTERN, 'define'),
        # Comando RECALL
        # ESTE COMANDO DEBE SER EL ULTIMO!
        (r'(?P<blockname>%(varflat)s)\s*' % VARPATTERN, 'recall'),
    )]

    MACROS = [
        ("cualquiera de",    "_cualquiera_de =="),
        ("cualquiera entre", "_cualquiera_de =="),
        ("cualquiera menos", "_cualquiera_de !="),
        ("ninguno de",       "_cualquiera_de !="),
        ("ninguna de",       "_cualquiera_de !="),
    ]

    def __init__(self):
        self._templates = []
        self._included  = set()
        self._blocks = dict()
        self._commands = CommandEngine.COMMANDS[:]
        self._macros = CommandEngine.MACROS[:]

    def register_command(self, regexp, processor):
        """Incluye un nuevo comando en la lista de ordenes reconocidas

        @regexp: la expresion regular que identifica el comando.
        @processor: un Callable que ejecuta el comando. Debe aceptar
            tres argumentos:
                - match: el match obtenido al utilizar la regexp
                    sobre el texto del patron
                - block: el bloque de patron (TmplList) que se ejecuta.
                - data: los datos.
        """
        self._commands.append((re.compile(regexp), processor))

    def register_macro(self, macro, replacement):
        """Incluye una macro en la lista de macros reconocidas.
 
        Una macro es una simple sustitucion de texto, macro => replacement.
        """
        self._macros.append((macro, replacement))

    def check(self, tokenizer, command):
        """Genera el CommandWrapper correspondiente al comando dado"""
        for macro, replacement in self._macros:
            command = command.replace(macro, replacement)
        command = command.strip()
        for regexp, processor in self._commands:
            match = regexp.match(command)
            if match:
                processor = getattr(self, "command_%s" % processor)
                return CommandWrapper(command, processor, match)
        tokenizer.error("Unknown command %s" % command)

    def templates(self):
        """Itera sobre la lista de patrones cargados.

        Por cada patron, devuelve una tupla (TmplParser, data)
        """
        while self._templates:
            self.source, data = self._templates.pop(0)
            if not self.source.id in self._included:
                self._included.add(self.source.id)
                yield (TmplParser(self).read(self.source), data)

    def read(self, data, source):
        """Lee un patron.

        Los patrones leidos pueden incluir otros patrones, asi que se esta
        funcion no devuelve el resultado directamente. En su lugar, una vez
        cargada la lista de patrones, hay que iterar sobre self.templates.
        """
        self._templates.append((source, data))
    
    @as_iterator
    def command_if(self, match, block, data):
        """comando "if"
        if expr
        Ejecuta el bloque si la expresion es verdadera y no lanza excepcion"""
        try:
            expr = eval(match.group('expr'), data)
            if expr:
                return block.render(data)
        except (NameError, KeyError):
            pass

    @as_iterator
    def command_ifnot(self, match, block, data):
        """comando "if not"
        if not expr
        Ejecuta el bloque si la expresion es falsa o lanza excepcion"""
        try:
            expr = eval(match.group('expr'), data)
            if not expr:
                return block.render(data)
        except (NameError, KeyError):
            return block.render(data)

    @as_iterator
    def command_exist(self, match, block, data):
        """comando "if exist"
        if var in expr
        Evalua la expresion y ejecuta el bloque si la expresion devuelve un
        diccionario y data existe entre sus claves y tiene un valor.
        """
        try:
            var = match.group('var')
            expr = eval(match.group('expr'), data)
            if (var in expr) and expr[var]:
                return block.render(data)
        except (NameError, KeyError):
            pass

    @as_iterator
    def command_notexist(self, match, block, data):
        """comando "if not exist"
        if not var in data
        Evalua la expresion y ejecuta el bloque si la expresion devuelve un
        diccionario y data no existe entre sus claves o no tiene un valor.
        """
        try:
            var  = match.group('var')
            expr = eval(match.group('expr'), data)
            if (not var in expr) or not expr[var]:
                return block.render(data)
        except (NameError, KeyError):
            return block.render(data)

    def command_set(self, match, block, data):
        """comando "set"
        set var = item [+ item]*
        Evalua al bloque, metiendo en "var" la combinacion de los valores
        de todos los items dados.
        Las variables de los items definidos primero tiene "prioridad", 
        sobreescriben a las de los bloques posteriores.
        Si el bloque esta vacio, mete en data el valor de ese item
        para el resto del template.
        """
        if len(block):
            data = data.copy()
        data[match.group('var')] = eval(match.group('expr'), data)
        return block.render(data)

    @as_iterator
    def command_define(self, match, block, data):
        """comando "define"
        define blockname
        Asigna un nombre al bloque. Luego, el bloque puede invocarse por
        su nombre en cualquier otro punto del patron.
        """
        block.command.processor = lambda a, b, c: tuple()
        self._blocks[match.group('blockname')] = block

    def command_recall(self, match, block, data):
        """comando "recall"
        blockname
        Inserta un bloque previamente definido. Antes de insertarlo, ejecuta el
        cuerpo del bloque recall, para poder utilizarlo para definir variables
        y cosas asi.
        """
        def do_recall(recalled, block, data):
            return itertools.chain(block.render(data), recalled.render(data))
        blockname = match.group('blockname')
        try:
            block.command.match = self._blocks[blockname]
            block.command.processor = do_recall
        except KeyError:
            raise SyntaxError, "Bloque %s no definido" % blockname
        return do_recall(block.command.match, block, data)

    def command_include(self, match, block, data):
        """comando "include"
        include <path>
        Sustituye el bloque por un fichero externo.
        """
        def replace(parser, block, data):
            return parser.render(data)
        fname = match.group('path').strip()
        block.command.match = TmplParser(self).read(self.source.resolve(fname))
        block.command.processor = replace
        return replace(block.command.match, block, data)

    def command_select(self, match, block, data):
        """comando "select"
        select <var> from <expr>
        Comprueba si <var> esta definida. si no lo esta,
        pide al usuario que seleccione un valor de la lista <expr>
        """
        var = match.group("var")
        art = match.group("art")
        exp = list(self._asseq(eval(match.group("expr"), data)))
        if not var in data:
            yield ("select", var, art, exp, data)
        if not var in data:
            raise ValueError, "No se ha seleccionado %s" % var

    @as_iterator
    def command_append(self, match, block, data):
        """comando "append"
        append <path>
        Coloca un fichero en la lista de proceso, para ser procesado
        despues del fichero actual
        """
        block.command.processor = lambda a, b, c: tuple()
        fname = match.group('path').strip()
        self.read(data, self.source.resolve(fname))
        
    def _asseq(self, expr):
        if type(expr) == str:
            expr = DataParser._aslist(expr)
        elif operator.isMappingType(expr):
            expr = (expr,)
        return expr

    def command_for(self, match, block, data):
        """comando "for"
        for var in expr
        Evalua la expresion y repite el bloque por cada elemento del
        resultado. La forma en que ejecuta el bucle depende del tipo de
        resultado a que se evalue la expresion:

            - Si se evalua a una cadena de texto, se convierte en una
              lista con DataDict._aslist()
            - Si se evalua a un diccionario o algo derivado, el bucle se
              ejecuta una sola vez, con el diccionario entero.
            - En el resto de los casos, se itera sobre el resultado de
              la expresion.

        Si la expresion lanza KeyError, no se ejecuta.
        """
        try:
            var  = match.group('var')
            expr = eval(match.group('expr'), data)
        except KeyError:
            return
        copied, forset = data.copy(), set()
        for item in self._asseq(expr):
            copied[var], result = item, list()
            for item in block.render(copied):
                if type(item) == str:
                    result.append(item)
                else:
                    yield item
            forset.add("".join(result))
        yield "".join(sorted(forset))

