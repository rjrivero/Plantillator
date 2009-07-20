#!/usr/bin/env python
# -*- vim: expandtab tabstop=4 shiftwidth=4 smarttab autoindent encoding=utf-8


import re
from gettext import gettext as _

from .base import *
from .commands import *


_RUNTIME_ERROR = _("Error ejecutando %(command)s")
_ERROR_LOCATION = _("Origen %(fname)s, linea $(lineno)d")
_UNKNOWN_CMD = _("Comando %(command)s desconocido")

# nombres de variables permitidos
VARPATTERN = {
    'var': r'[a-zA-Z][\w\_]*',
    'en':  r'en(\s+(el|la|los|las))?',
    'de':  r'(en|de|del)(\s+(el|la|los|las))?'
}


class CommandTree(list):

    """Convierte un arbol de tokens en un arbol de comandos"""

    _COMMANDS = [(re.compile(exp), cmd) for (exp, cmd) in (
        # comando FOR
        # p.e. "por cada var de path.to(list)"
        (r'^por cada\s+(?P<var>%(var)s)\s+%(de)s\s+(?P<expr>.*)$' % VARPATTERN,
             CommandFor),
        # comando IF NOT EXIST
        # p.e. "si no hay key en expr"
        (r'^si no (hay|existe)\s+(?P<var>%(var)s)\s+%(en)s\s+(?P<expr>.*)$' % VARPATTERN,
             ConditionNotExist),
        (r'^si\s+(?P<var>%(var)s)\s+no esta\s+%(en)s\s+(?P<expr>.*)$' % VARPATTERN,
             ConditionNotExist),
        # comando IF EXIST
        # p.e. "si hay key en expr"
        (r'^si (hay|existe) (?P<var>%(var)s)\s+%(en)s\s+(?P<expr>.*)$' % VARPATTERN,
             ConditionExist),
        (r'^si (?P<var>%(var)s) esta\s+%(en)s\s+(?P<expr>.*)$' % VARPATTERN,
             ConditionExist),
        # Comando ELSE
        # p.e. "si no"
        (r'^si\s*no\s*$', CommandElse),
        # Comando IF NOT
        # p.e. "si no"
        (r'^si no\s+(?P<expr>.*)$', ConditionNot),
        # Comando IF
        # p.e. "if expr"
        (r'^si\s+(?P<expr>.*)$', Condition),
        # Comando INCLUDE
        # p.e. "incluir file"
        (r'^(include|incluir|insertar)\s+(?P<path>.*)$', CommandInclude),
        # Comando APPEND
        # p.e. "procesar file"
        (r'^procesar\s+(?P<path>.*)$', CommandAppend),
        # Comando SELECT
        # p.ej. "utiliza un <var> de la lista <expr>"
        (r'^(necesito|necesita|utilizo|utiliza)\s+(?P<art>un|una)\s+(?P<var>%(var)s)\s+(de|del)(\s+(la|las|los)\s+(lista\s+)?)?(?P<expr>.*)$' % VARPATTERN,
             CommandSelect),
        # Comando DEFINE
        # p.ej. "definir <blockname>"
        (r'^(define|definir|bloque|funcion)\s+(?P<blockname>%(var)s)\s*(\((?P<params>%(var)s(\s*,\s*%(var)s)*)?\))?\s*$' % VARPATTERN,
             CommandDefine),
        # Comando RECALL
        (r'^(?P<blockname>%(var)s)\s*(?P<params>\(.*\))?\s*$' % VARPATTERN,
             CommandRecall),
        # comando SET
        # ESTE COMANDO DEBE SER EL ULTIMO!
        # p.e. "var = var1 (+ var2)*
        (r'^(?P<var>[^=]+)\s*=\s*(?P<expr>.+)$' % VARPATTERN, CommandSet),
    )]

    _MACROS = [
        ('cualquiera de', 'cualquiera +'),
        ('cualquiera entre', 'cualquiera +'),
        ('cualquiera menos', 'cualquiera -'),
        ('cualquiera como', 'cualquiera *')
    ]

    def __init__(self, source, tokens):
        list.__init__(self)
        self.source = source
        last = None
        for token in tokens:
            last = self.build(self, token, last)

    def _check(self, token):
        line = token.head
        for pre, post in self._MACROS:
            line = line.replace(pre, post)
        for expr, cls in self._COMMANDS:
            match = expr.match(line)
            if match:
                return cls(token, match)
        raise ParseError(self.source, token, _UNKNOWN_CMD % {
            'command': token.head})

    def build(self, base, token, last):
        if not token.head:
            return self._chain(base, token, last)
        cmd, inner = self._check(token), None
        for nested in token.body:
            inner = self.build(cmd, nested, inner)
        cmd.chainto(last)
        base.append(cmd)
        return cmd

    def _chain(self, base, token, last):
        if not isinstance(last, Literal):
            last = Literal()
            base.append(last)
        last.append(token)
        return last

    def run(self, glob, data):
        for item in self:
            try:
                for block in item.run(glob, data):
                    yield block
            except CommandError as details:
                # en el caso de un CommandInclude, se puede levantar un
                # CommandError con una fuente distinta a la de este cmdtree.
                # Por eso, solo machaco el campo source si no esta definido.
                details.source = details.source or self.source
                raise details
            except:
                raise CommandError(self.source, item.token, glob, data)

