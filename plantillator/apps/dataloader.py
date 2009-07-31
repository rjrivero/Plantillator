#!/usr/bin/env python
# -*- vim: expandtab tabstop=4 shiftwidth=4 smarttab autoindent


from os.path import splitext

from ..data.base import *
from ..csvread.csvdata import RootType
from ..csvread.parser import DataError


class DataLoader(object):

    def __init__(self, loader):
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
        self.loader = loader
        self.root = RootType(self.loader)
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
            deps = self.loader.read(source, self.data)
            return list(source.resolve(item) for item in deps)
        except (SyntaxError, ValueError) as details:
            raise DataError(source, "N/A", details.message)

    def evaluate(self, expr):
        return eval(expr, self.glob, self.data)

