#!/usr/bin/env python
# -*- coding: cp1252 -*-
# -*- vim: expandtab tabstop=4 shiftwidth=4 smarttab autoindent


from .cmdtree import CommandTree
from .tokenizer import Tokenizer


class Loader(object):

    def __init__(self, keep_comments=False):
        self.keep_comments = keep_comments
        self.trees = dict()
        self.sources = set()

    def _load(self, source):
        """Encuentra o carga el árbol de comandos del fichero"""
        try:
            return self.trees[source.id]
        except KeyError:
            tree = CommandTree(source, Tokenizer(source, self.keep_comments))
            return self.trees.setdefault(source.id, tree)

    def load(self, source, outpath=None):
        """Carga el fichero y lo marca para ejecucion"""
        self.sources.add((source.id, outpath))
        self._load(source)

    def run(self, tree, glob, data):
        self.source = tree.source
        for block in tree.run(glob, data):
            if isinstance(block, basestring):
                yield block
            elif block.opcode == "APPEND":
                self._append(block)
            elif block.opcode == "INCLUDE":
                self._include(block)
            else:
                yield block

    def _cached_source(self, block):
        try:
            return block.command.source
        except AttributeError:
            source = self.source.resolve(block.command.path)
            block.command.source = source
            return source

    def _append(self, block):
        source  = self._cached_source(block)
        outpath = block.command.outpath
        self.appended[(source.id, outpath)] = (source, outpath)

    def _include(self, block):
        source = self._cached_source(block)
        block.command.included = self._load(source)

    def __iter__(self):
        self.appended = dict()
        for (sourceid, outpath) in self.sources:
            yield (self.trees[sourceid], outpath)
        while self.appended:
            # ordeno el diccionario antes de extraer, para que el resultado
            # de console -l sea repetible.
            index = sorted(self.appended).pop()
            source, outpath = self.appended.pop(index)
            yield (self._load(source), outpath)
