#!/usr/bin/env python
# -*- vim: expandtab tabstop=4 shiftwidth=4 smarttab autoindent encoding=utf-8


import re
import traceback
import os.path
from sys import exc_info
from gettext import gettext as _

from ..data.base import normalize


# marcadores de parametros a reemplazar
PLACEHOLD = re.compile(r'\?(?P<expr>[^\?]+)\?')
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

    def __init__(self, token, match):
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


class Literal(list):

    """Texto literal, con sustituciones"""

    def run(self, glob, data):
        def replacefn(match):
            return str(eval(match.group('expr'), glob, data))
        try:
            # intento hacer el replace y el yield de una sola vez,
            # con todas las lineas que haya en el literal
            yield PLACEHOLD.sub(replacefn, "".join(item.body for item in self))
        except CommandError:
            raise
        except:
            # hay una excepcion. Para afinar, vamos linea por linea
            # hasta encontrar la que falla.
            for item in self:
                try:
                    yield PLACEHOLD.sub(replacefn, item.body)
                except:
                    raise CommandError(None, item, glob, data)

    def __str__(self):
        return _LITERAL_TEXT % {'linenum': len(self)}

    def __repr__(self):
        return str(self)

