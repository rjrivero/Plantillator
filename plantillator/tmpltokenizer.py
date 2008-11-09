#!/usr/bin/env python
# -*- vim: expandtab tabstop=4 shiftwidth=4 smarttab autoindent

import re

from mytokenizer import Tokenizer


class TmplTokenizer(Tokenizer):
    """Tokenizer para ficheros de patrones

    Divide cada linea en tokens. Usa "delimiters" como una RegExp para partir
    las lineas.

    Si una linea comienza por "comment", la considera un comentario.
    """
    def __init__(self, source, delimiter, comment):
        Tokenizer.__init__(self, source)
        self._delimiter = re.compile(delimiter)
        self._comment = comment

    def _tokenize(self, line):
        if line.strip().startswith(self._comment):
            return tuple()
        if line.isspace():
            return (line,)
        return (t for t in self._delimiter.split(line) if not t.isspace())

