#!/usr/bin/env python
# -*- vim: expandtab tabstop=4 shiftwidth=4 smarttab autoindent


from os.path import splitext

import csvread.datasource
from data.operations import Deferrer, Filter
from data.datatype import TypeTree
from data.dataobject import DataObject
from data.dataset import *


_DATASOURCES = {
    'csv': csvread.datasource.DataSource
}

_DEFAULT_EXT = 'csv'


class LoadError(Exception):

    def __init__(self, source, lineno, *args):
        Exception.__init__(self, *args)
        self.source = source
        self.lineno = lineno


class DataLoader(object):

    def __init__(self):
        self.tree = TypeTree()
        self.data = DataObject(self.tree.root)
        self.hist = set()
        self.glob = {
            "__builtins__": __builtins__,
            "LISTA": asList,
            "RANGO": asRange,
            "GRUPO": asSet,
            "cualquiera": Deferrer(),
            "ninguno": None,
            "ninguna": None,
            "X": Deferrer(),
            "x": Deferrer(),
            "donde": Filter
        }

    def load(self, source):
        sources = [source]
        while sources:
            source = sources.pop(0)
            if source.id not in self.hist:
                sources.extend(self._resolve(source))
                self.hist.add(source.id)

    def _resolve(self, source):
        ext = splitext(source.id)[-1].lower()
        if not ext in _DATASOURCES:
            ext = _DEFAULT_EXT
        ds = _DATASOURCES[ext](self.tree, self.data)
        try:
            return list(source.resolve(item) for item in ds.read(source))
        except (SyntaxError, ValueError) as details:
            raise LoadError(source, ds.lineno, details.message)

    def evaluate(self, ext):
        return eval(expr, self.glob, self.data)

    def known(self, ext):
        return ext.lower() in _DATASOURCES

