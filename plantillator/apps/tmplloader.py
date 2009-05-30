#!/usr/bin/env python
# -*- vim: expandtab tabstop=4 shiftwidth=4 smarttab autoindent


from os.path import splitext
from gettext import gettext as _

import tmpl.tmpltokenizer
from engine.cmdtree import CommandTree


_UNKNOWN_ERROR = _("Error desconocido")

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
        ext = splitext(source.id)[-1].lower()
        if not ext in _TOKENSOURCES:
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
        self.source = tree.source
        for block in tree.run(glob, data):
            if type(block) == str:
                yield block
            elif block.opcode == "APPEND":
                self._append(block)
            elif block.opcode == "INCLUDE":
                self._include(block)
            else:
                yield block

    def _append(self, block):
        source = self.source.resolve(block.command.path)
        if not source.id in self:
            self.appended[source.id] = (source, block.glob, block.data)

    def _include(self, block):
        source = self.source.resolve(block.command.path)
        block.command.included = self.load(source)

    def templates(self, glob, data):
        self.appended = dict()
        for sourceid, cmdtree in self.copy().iteritems():
            yield (sourceid, cmdtree, glob, data)
        while self.appended:
            key, data = self.appended.popitem()
            yield (key, self.load(data[0]), data[1], data[2])

    def known(self, ext):
        return ext.lower() in _TOKENSOURCES

