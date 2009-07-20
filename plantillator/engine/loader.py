#!/usr/bin/env python
# -*- vim: expandtab tabstop=4 shiftwidth=4 smarttab autoindent


from .cmdtree import CommandTree
from .tokenizer import Tokenizer


class Loader(object):

    def __init__(self):
        self.trees = dict()

    def load(self, source):
        try:
            return self.trees[source.id]
        except KeyError:
            tree = CommandTree(source, Tokenizer(source))
            return self.trees.setdefault(source.id, tree)

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
        if not source.id in self.trees:
            self.appended[source.id] = source

    def _include(self, block):
        source = self.source.resolve(block.command.path)
        block.command.included = self.load(source)

    def __iter__(self):
        self.appended = dict()
        for tree in self.trees.copy().values():
            yield tree
        while self.appended:
            index, source = self.appended.popitem()
            yield self.load(source)

