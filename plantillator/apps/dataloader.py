#!/usr/bin/env python
# -*- vim: expandtab tabstop=4 shiftwidth=4 smarttab autoindent


from ..data import Resolver, SYMBOL_SELF, DataSet, password, secret


class DataLoader(object):

    def __init__(self, loader):
        self.loader = loader
        solv = Resolver(SYMBOL_SELF)
        self.glob = {
            "CISCOPASSWORD": password,
            "CISCOSECRET": secret,
            "cualquiera": DataSet.ANY,
            "ninguno": DataSet.NONE,
            "ninguna": DataSet.NONE,
            "X": solv,
            "x": solv,
            "Y": solv,
            "y": solv,
            "Z": solv,
            "z": solv,
        }

    def load(self, path, shelf):
        self.data = self.loader(path, shelf)
        self.data.update(self.glob)
        return self.data
