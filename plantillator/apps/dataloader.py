#!/usr/bin/env python
# -*- vim: expandtab tabstop=4 shiftwidth=4 smarttab autoindent


from os.path import splitext

from data.operations import Deferrer, Filter
from data.base import *
from data.dataobject import RootType
from csvread.datasource import DataSource
from csvread.tableparser import DataError


class PropertyFactory(dict):

    def __init__(self, data=None):
        dict.__init__(self, data or {})
        self._active = None

    def select(self, ext):
        self._active = self[ext.lower()]
        return self._active

    def __call__(self, cls, attr):
        return self._active(cls, attr)


DATA_SOURCES = PropertyFactory({
    'csv': DataSource()
    })


class DataLoader(object):

    def __init__(self):
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
        self.root = RootType(DATA_SOURCES)
        self.data = self.root()

    def load(self, source):
        sources = [source]
        while sources:
            source = sources.pop(0)
            if source.id not in self.hist:
                sources.extend(self._resolve(source))
                self.hist.add(source.id)

    def _resolve(self, source):
        try:
            parser = DATA_SOURCES.select(splitext(source.id)[-1][1:])
            deps = parser.read(source, self.data)
            return list(source.resolve(item) for item in deps)
        except (SyntaxError, ValueError) as details:
            raise DataError(source, "N/A", details.message)

    def evaluate(self, expr):
        return eval(expr, self.glob, self.data)

    def known(self, ext):
        return ext.lower() in DATA_SOURCES
