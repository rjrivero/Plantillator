#!/usr/bin/env python
# -*- vim: expandtab tabstop=4 shiftwidth=4 smarttab autoindent encoding=utf-8


import re
import traceback
import os.path
from collections import namedtuple
from sys import exc_info
from gettext import gettext as _
from itertools import chain

from ..data.base import normalize


DELIMITER = "?"
BLOCK_OPENER = '{{'
BLOCK_CLOSER = '}}'
LINE_COMMENT = '#'


DELIMITER_RE = re.compile(r'(\?)')
# nombres de variables permitidos
VARPATTERN = {
    'var': r'[a-zA-Z][\w\_]*',
    'en':  r'en(\s+(el|la|los|las))?',
    'de':  r'(en|de|del)(\s+(el|la|los|las))?'
}


_INVALID_LITERAL = _("Testo no terminado ('%s' desbalanceados)" % DELIMITER)
_LITERAL_TEXT = _("Texto (%(linenum)d lineas)" )


class Token(object):

    """Atomo de un fichero de patrones.

    Incluye toda la informacion necesaria para procesar una parte del patron:

    - self.lineno: numero de linea
    - self.head: si el patron era un comando, esta es la orden. Si no, es None.
    - self.body: si el patron no es un comando, este es el texto. Si lo es,
        esto es una lista de tokens anidados debajo del comando.
    """

    def __init__(self, lineno, head=None, body=None):
        self.lineno = lineno
        self.head = head
        self.body = body

    def __str__(self):
        return (self.head or self.body).strip()

    Atom = namedtuple('Atom', 'text, expr')

    def _consume(self, parts):
        """Consume un elemento de la lista de partes"""
        part = parts.pop(0)
        if part != DELIMITER:
            return part
        expr = parts.pop(0)
        if parts.pop(0) != DELIMITER:
            raise IndexError(0)
        return Token.Atom(expr, compile(expr, '<string>', 'eval'))
            
    def split(self):
        """Divide el token en trozos separados por el DELIMITADOR"""
        self.parts = list()
        try:
            parts = DELIMITER_RE.split(self.body)
            while parts:
                self.parts.append(self._consume(parts))
        except IndexError:
            raise ParseError(None, self, _INVALID_LITERAL)

    def evaluate(self, glob, data):
        "Evalua el contenido de un token previamente 'splitted'."""
        return (x if isinstance(x, str) else str(eval(x.expr, glob, data))
                for x in self.parts)

    def style(self, style):
        for x in self.parts:
            if isinstance(x, str):
                style.text(x)
            else:
                style.delimiter(DELIMITER)
                style.inline(x.text)
                style.delimiter(DELIMITER)
        return style


class ParseError(Exception):

    """Error de parseo. Incluye fichero, token y mensaje"""

    def __init__(self, source, token, errmsg):
        self.source = source
        self.token  = token
        self.errmsg = errmsg

    def __str__(self):
        error = [
            "%s, LINE %s" % (
                os.path.basename(self.source.id) if self.source else "<>",
                self.token.lineno),
            "Error interpretando %s" % str(self.token),
            self.errmsg
        ]
        #error.extend(traceback.format_exception(*self.exc_info))
        return "\n".join(error)


class CommandError(Exception):

    """Excepcion que se lanza al detectar un error procesando el template.

    Encapsula la excepcion original, y el bloque que la ha originado:

    - self.source:    origen de la excepcion.
    - self.token:     Token que levanto la excepcion.
    - self.data:      datos que se estaban evaluando.
    - self.exc_info:  datos de la excepcion original.
    """

    def __init__(self, source, token, glob, data):
        self.source = source
        self.token  = token
        self.glob   = glob
        self.data   = data
        self.exc_info = exc_info()

    def __str__(self):
        error = [
            "%s, LINE %s" % (
                os.path.basename(self.source.id) if self.source else "<>",
                self.token.lineno),
            "Error ejecutando %s" % str(self.token),
            "%s: %s" % (self.exc_info[0].__name__, str(self.exc_info[1]))
        ]
        error.extend(traceback.format_exception(*self.exc_info))
        return "\n".join(error)


class Command(list):

    """Comando de la plantilla"""

    def __init__(self, tree, token, match):
        list.__init__(self)
        for key, val in match.groupdict().iteritems():
            setattr(self, key, normalize(val) if val else None)
        self.token = token

    def run(self, glob, data):
        for item in self:
            try:
                for block in item.run(glob, data):
                    yield block
            except CommandError:
                raise
            except:
                raise CommandError(None, item.token, glob, data)

    def chainto(self, prev):
        pass

    def __str__(self):
        return "{{%s%s}}" % (str(self.token), " ... " if len(self) else "")

    def __repr__(self):
        return str(self)

    def style(self, style_type, indent=0):
        # creo un objeto para el comando
        style = style_type(indent)
        style.opener(BLOCK_OPENER)
        self._style(self, style)
        # Inserto los comandos en una lista
        style_set = [style]
        if not self.token.body:
            style.closer(BLOCK_CLOSER)
        else:
            ending = style_type(indent)
            ending.closer(BLOCK_CLOSER)
            indent = indent + 1
            for item in self.token.body:
                style_set.append(item.style(style_type, indent))
            style_set.append(ending)
        return style_set


class Literal(object):

    """Texto literal, con sustituciones"""

    def __init__(self):
        self.tokens = list()

    def run(self, glob, data):
        try:
            # intento hacer el replace y el yield de una sola vez,
            # con todas las lineas que haya en el literal
            yield "".join(chain(x.evaluate(glob, data) for x in self.tokens))
        except CommandError:
            raise
        except:
            # Hay un error en algun token, voy linea por linea para afinar.
            for token in self.tokens:
                try:
                    yield "".join(token.evaluate(glob, data))
                except:
                    raise CommandError(None, token, glob, data)

    def append(self, token):
        token.split()
        self.tokens.append(token)

    def __str__(self):
        return _LITERAL_TEXT % {'linenum': len(self.tokens)}

    def __repr__(self):
        return str(self)

    def __iter__(self):
        return self.tokens.__iter__()

    def __getitem__(self, index):
        return self.tokens[index]

    def style(self, style_type, indent=0):
        style_set = list()
        for item in self.tokens:
            style_set.append(item.style(style_type(indent)))
        return style_set
