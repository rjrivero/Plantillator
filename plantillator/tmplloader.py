#!/usr/bin/env python
# -*- vim: expandtab tabstop=4 shiftwidth=4 smarttab autoindent

import tmpl.tmpltokenizer
from engine.cmdtree import CommandTree

_TOKENSOURCES = {
    'txt': tmpl.tmpltokenizer.TmplTokenizer
}

_DEFAULT_EXT = 'txt'



class TmplLoader(dict):

    def load(self, source):
        try:
            return self[source.id]
        except KeyError:
            return self.setdefault(source.id, self._read(source))

    def _read(self, source):
        ext = source.id.split(".").pop().strip().lower()
        if not ext in _DATASOURCES:
            ext = _DEFAULT_EXT
        try:
            tree = _TOKENSOURCES[ext](source).tree()
            return CommandTree(source, tree)
        except ParseError as details:
            details.source = source
            raise details
        except:
            raise ParseError(source, Token(0, None, None), _UNKNOWN_ERROR)

    def run(self, tree, glob, data):
        appended = set()
        for block in tree.run(glob, data):
            if type(block) == str:
                yield block
            elif block[0] == "APPEND":
                appended.append(source.resolve(block))
            elif block[0] == "INCLUDE":
                self.include(block)
