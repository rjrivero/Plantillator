#!/usr/bin/env python
# -*- vim: expandtab tabstop=4 shiftwidth=4 smarttab autoindent


import re
from contextlib import contextmanager
from gettext import gettext as _

from .base import *


_UNEXPECTED_EOF = _("No se esperaba el fin del fichero")
_UNBALANCED = _("No se esperaba el fin de bloque")
_PARSE_ERROR = _("Fichero %(file)s [%(lineno)d]: %(msg)s")


class Tokenizer(object):
    """Tokenizer para ficheros de patrones

    Divide cada linea en tokens. Usa "delimiters" como una RegExp para partir
    las lineas.

    Si una linea comienza por "comment", la considera un comentario.
    """
    def __init__(self, source, keep_comments=False, opener=None, closer=None, comment=None):
        self.source = source
        self.opener = opener or BLOCK_OPENER
        self.closer = closer or BLOCK_CLOSER
        self.comment = comment or LINE_COMMENT
        self.keep_comments = keep_comments
        self.lineno = 0
        self.delimiter = re.compile("(%s|%s)" % (self.opener, self.closer))

    def _tokenize(self, lineno, line):
        if line.strip().startswith(self.comment):
            return (Comment(lineno, line),) if self.keep_comments else tuple()
        if line.isspace():
            return (Token(lineno, None, line),)
        return (Token(lineno, None, t) for t in self.delimiter.split(line)
                if t and not t.isspace())

    def _tokens(self):
        """Iterador que genera un flujo de tokens"""
        for self.lineno, line in enumerate(self.source.readlines()):
            for token in self._tokenize(self.lineno+1, line):
                yield token

    def _group(self, tokens):
        command, body = tokens.next(), list()
        while(True):
            token = tokens.next()
            if token.body == self.closer:
                return Token(command.lineno, command.body, body)
            elif token.body == self.opener:
                body.append(self._group(tokens))
            else:
                body.append(token)

    def __iter__(self):
        try:
            tokens = self._tokens()
            for token in tokens:
                if token.body == self.closer:
                    raise ParseError(self.source, token, _UNBALANCED)
                elif token.body == self.opener:
                    yield self._group(tokens)
                else:
                    yield token
        except StopIteration:
            eof = Token(self.lineno, "<EOF>")
            raise ParseError(self.source, eof, _UNEXPECTED_EOF)
