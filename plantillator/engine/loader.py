#!/usr/bin/env python
# -*- vim: expandtab tabstop=4 shiftwidth=4 smarttab autoindent


from .cmdtree import CommandTree
from .tokenizer import Tokenizer


class Loader(object):

    def __init__(self):
        self.trees = dict()
        self.sources = set()

    def load(self, source):
        """Carga el fichero y lo marca para ejecucion"""
        self.sources.add(source.id)
        return self._load(source)

    def _load(self, source):
        try:
            return self.trees[source.id]
        except KeyError:
            tree = CommandTree(source, Tokenizer(source))
            return self.trees.setdefault(source.id, tree)

    def run(self, tree, glob, data):
        self.source = tree.source
        for block in tree.run(glob, data):
            if isinstance(block, str):
                yield block
            elif block.opcode == "APPEND":
                self._append(block)
            elif block.opcode == "INCLUDE":
                self._include(block)
            else:
                yield block

    def _append(self, block):
        try:
            source = block.command.source
        except AttributeError:
            source = self.source.resolve(block.command.path)
            block.command.source = source
        self.appended[source.id] = source

    def _include(self, block):
        source = self.source.resolve(block.command.path)
        block.command.included = self._load(source)

    def __iter__(self):
        self.appended = dict()
        for sourceid in self.sources:
            yield self.trees[sourceid]
        while self.appended:
            # ordeno el diccionario antes de extraer, para que el resultado
            # de console -l sea repetible.
            index = sorted(self.appended).pop()
            source = self.appended.pop(index)
            yield self._load(source)

