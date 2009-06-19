#!/usr/bin/env python
# -*- vim: expandtab tabstop=4 shiftwidth=4 smarttab autoindent


import re
from gettext import gettext as _

from data.namedtuple import NamedTuple
from engine.base import *


_UNEXPECTED_EOF = _("No se esperaba el fin del fichero")
_UNBALANCED = _("No se esperaba el fin de bloque")
_PARSE_ERROR = _("Fichero %(file)s [%(lineno)d]: %(msg)s")


class TmplTokenizer(object):
    """Tokenizer para ficheros de patrones

    Divide cada linea en tokens. Usa "delimiters" como una RegExp para partir
    las lineas.

    Si una linea comienza por "comment", la considera un comentario.
    """
    def __init__(self, source, opener='{{', closer='}}', comment='#'):
        self.source = source
        self.opener = opener
        self.closer = closer
        self.lineno = 0
        self.delimiter = re.compile("(%s|%s)" % (opener, closer))
        self.comment = comment

    def tokens(self):
        """Iterador que genera un flujo de tokens"""
        for self.lineno, line in enumerate(self.source.readlines()):
            for token in self.tokenize(line):
                yield Token(self.lineno+1, None, token)

    def tokenize(self, line):
        if line.strip().startswith(self.comment):
            return tuple()
        if line.isspace():
            return (line,)
        return (t for t in self.delimiter.split(line) if t and not t.isspace())

    def _tree(self, tokens):
        while tokens:
            item = tokens.pop(0)
            if item.body == self.opener:
                command = tokens.pop(0)
                cmdbody = list(self._tree(tokens))
                yield Token(command.lineno, command.body, cmdbody)
            elif item.body == self.closer:
                break
            else:
                yield item

    def tree(self):
        tokens = list(self.tokens())
        try:
            for item in self._tree(tokens):
                yield item
        except IndexError:
            eof = Token(self.lineno, "<EOF>")
            raise ParseError(self.source, eof, _UNEXPECTED_EOF)
        if tokens:
            raise ParseError(self.source, tokens.pop(0), _UNBALANCED)