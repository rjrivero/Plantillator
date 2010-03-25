#!/usr/bin/env python
# -*- vim: expandtab tabstop=4 shiftwidth=4 smarttab autoindent


from os.path import splitext

from ..data import DataError, DataContainer, Deferrer, Filter
from ..data import RootResolver, SYMBOL_SELF, SYMBOL_FOLLOW
from ..csvread import RootType


class DataLoader(DataContainer):

    def __init__(self, loader):
        self.loader = loader
        self.hist = set()
        symbols = {
            'self':   RootResolver(SYMBOL_SELF),
            'orig': RootResolver(SYMBOL_FOLLOW),
        }
        DataContainer.__init__(self, RootType(self.loader), Deferrer, Filter, symbols)

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
