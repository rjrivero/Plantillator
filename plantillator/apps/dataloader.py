#!/usr/bin/env python
# -*- vim: expandtab tabstop=4 shiftwidth=4 smarttab autoindent


from ..data import Resolver, SYMBOL_SELF, DataSet, password, secret


class DataLoader(object):

    def __init__(self, loader):
        self.loader = loader

    def load(self, path, shelf):
        data = self.loader(path, shelf)
        solv = Resolver(SYMBOL_SELF)
        data.update({
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
        })
        return data

