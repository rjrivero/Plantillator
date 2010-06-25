#!/usr/bin/env python
# -*- coding: cp1252 -*-
# -*- vim: expandtab tabstop=4 shiftwidth=4 smarttab autoindent


import copy

from .cmdtree import CommandTree
from .tokenizer import Tokenizer


class RunnableTree(object):

    def __init__(self, cmdtree, glob=None, data=None, outpath=None):
        self.cmdtree = cmdtree
        self.outpath = outpath
        self.glob = glob
        self.data = data

    def identity(self):
        return (self.cmdtree.source.id, self.outpath)


class Loader(object):

    def __init__(self, keep_comments=False):
        self.keep_comments = keep_comments
        self.trees = dict()
        self.sources = dict()

    def _load(self, source):
        """Encuentra o carga el árbol de comandos del fichero"""
        try:
            return self.trees[source.id]
        except KeyError:
            tree = CommandTree(source, Tokenizer(source, self.keep_comments))
            return self.trees.setdefault(source.id, tree)

    def load(self, source, glob, data, outpath=None):
        """Carga el fichero y lo marca para ejecucion"""
        runtree = RunnableTree(self._load(source), glob, data, outpath)
        self.sources[runtree.identity()] = runtree

    def run(self, runtree):
        cmdtree = runtree.cmdtree
        self.source = cmdtree.source
        for block in cmdtree.run(runtree.glob, runtree.data):
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
        glob = block.glob
        data = copy.copy(block.data)
        runtree = RunnableTree(self._load(source), glob, data, outpath)
        self.appended[runtree.identity()] = runtree

    def _include(self, block):
        source = self._cached_source(block)
        block.command.included = self._load(source)

    def __iter__(self):
        self.appended = dict()
        for runtree in self.sources.values():
            yield runtree
        while self.appended:
            # ordeno el diccionario antes de extraer, para que el resultado
            # de console -l sea repetible.
            index = sorted(self.appended.keys()).pop()
            yield self.appended.pop(index)
