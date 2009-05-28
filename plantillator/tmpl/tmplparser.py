#!/usr/bin/env python
# -*- vim: expandtab tabstop=4 shiftwidth=4 smarttab autoindent encoding=utf-8

import itertools
import re
from os.path import basename
from sys import exc_info
import traceback
from gettext import gettext as _

from data.pathfinder import PathFinder
from tmpl.tmpltokenizer import TmplTokenizer


# delimitadores de bloques de comandos
DELIMITERS = re.compile(r'({{|}})')
# marcadores de parametros a reemplazar
PLACEHOLDS = re.compile(r'\?(?P<expr>[^\?]+)\?')
# CARACTER DE COMENTARIO
TMPL_COMMENT = "#"


_RUNTIME_ERROR = _("Error ejecutando %(command)s")
_ERROR_LOCATION = _("Origen %(fname)s, linea $(lineno)d")


class CommandError(Exception):

    """Excepcion que se lanza al detectar un error procesando el template.

    Encapsula la excepcion original, y el bloque que la ha originado:

    - self.block:     bloque que levanto la excepcion
    - self.data:      datos que se estaban evaluando
    - self.offending: linea o comando que provoco la excepcion
    - self.exc_info:  datos de la excepcion original

    Estas excepciones son excepciones de tiempo de proceso. Las excepciones
    durante el parsing se indican con SyntaxErrors.
    """

    def __init__(self, block, data, offending):
        self.block = block
        self.data  = data
        self.offending = offending
        self.exc_info = exc_info()

    def __str__(self):
        block = self.block
        error = [
            _ERROR_LOCATION % {
                'fname': str(block.source), 'lineno': block.lineno},
            _RUNTIME_ERROR % {'command': str(self.offending)}
        ]
        error.extend(traceback.format_exception(*self.exc_info))
        return "\n".join(error)


class TmplList(list):
    """Lista de "atomos de patron"

    El patron de entrada se divide en bloques, delimitados por {{ y }}.
    Este objeto representa uno de esos bloques.

    Los elementos de esta lista pueden ser cadenas de texto, o nuevos bloques
    anidados que se representan a traves de otro objeto TmplList.
    """
    def __init__(self, command=None):
        list.__init__(self)
        self.command = command
        self.source  = None
        self.lineno  = None

    def render(self, data):
        """Iterador que genera el contenido del bloque.

        Recorre uno por uno todos los elementos de este bloque, y los
        procesa. Conforme los procesa, va lanzando objetos con el
        resultado de la evaluacion.

        La mayoria de las veces el resultado de la evaluacion sera una
        cadena de texto con los patrones reemplazados. Sin embargo, es
        posible ampliar el motor de patrones para que lance otro tipo de
        objetos.
        """
        def repfnc(match):
            try:
                return str(eval(match.group('expr'), data))
            except KeyError:
                return "/*EMPTY*/"
        try:
            for item in self:
                if type(item) == str:
                    yield PLACEHOLDS.sub(repfnc, item)
                else:
                    renderer, args = item.render, data
                    if item.command is not None:
                        renderer, args = item.command, (item, data)
                    for block in renderer(*args):
                        yield block
        except CommandError:
            raise
        except:
            raise CommandError(self, data, item)
    
    def read(self, tokenizer, tokens, engine):
        self.source = tokenizer.source
        self.lineno = tokenizer.lineno
        for token in tokens:
            if token == '}}': break
            if token == '{{':
                command = engine.check(tokenizer, tokens.next())
                token = TmplList(command).read(tokenizer, tokens, engine)
            self.append(token)
        return self


class TmplParser(TmplList):
    """
    Analiza un fichero de patrones, construye una lista de bloques

    Un fichero de patrones esta compuesto por texto y bloques de ordenes.
    Los bloques de ordenes estan delimitados por "{{" y "}}", y cada
    uno de ellos contiene una orden ("if", "for", "set", etc)
    junto a la llave de apertura.

    Dentro del texto hay "placeholders" o cadenas de caracteres
    a ser sustituidas por el valor de alguna variable del fichero de datos.
    Los placeholders son cualquier nombre que vaya encerrado entre "??".

    Por ejemplo, si el diccionario de datos define una variable
        nombre = "Luis"

    el patron "Hola ?nombre?", al ser procesado, dara como resultado
    "Hola Luis"
    """
    def __init__(self, engine):
        TmplList.__init__(self)
        self.engine = engine

    def read(self, source):
        tokenizer = TmplTokenizer(source, DELIMITERS, TMPL_COMMENT)
        tokens = tokenizer.tokens()
        TmplList.read(self, tokenizer, tokens, self.engine)
        try:
            tokens.next()
            tokenizer.error("Cierre de bloque (}}) antes de EOF")
        except StopIteration: pass
        return self


if __name__ == "__main__":
    import sys
    import pprint
    from mycommands import CommandEngine
    p = TmplParser(CommandEngine())
    for f in sys.argv[1:]:
        p.read(PathFinder([]).find(f))
    pprint.pprint(p)

