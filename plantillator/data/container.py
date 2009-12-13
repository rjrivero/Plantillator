#!/usr/bin/env python
# -*- vim: expandtab tabstop=4 shiftwidth=4 smarttab autoindent


from inspect import getmembers

from .base import asList, asRange, asSet
from .ip import IPAddress
from .ciscopw import password, secret


class RestrictedBuiltins(dict):

    """Restringe el acceso a propiedades built-in de python"""

    RESTRICTED = ('__class__', '__import__', '__package__', 'compile',
                  'eval', 'execfile', 'exit', 'file', 'input', 'open',
                  'quit', 'raw_input', 'reload')

    def __init__(self):
        """Filtra los builtins accesibles"""
        if hasattr(__builtins__, 'iteritems'):
            # dentro de la shell de django, __builtins__ es un dict
            iteritems = __builtins__.iteritems()
        else:
            # en python normal, __builtins__ es un objeto simple
            iteritems = getmembers(__builtins__)
        dict.__init__(self, dict((x, y) for (x, y) in iteritems
                                 if x not in RestrictedBuiltins.RESTRICTED))


class DataContainer(object):

    """Contenedor para los objetos root, data y glob"""

    def __init__(self, root_type, deferrer_type, filter_type):
        """Construye e inicializa el contenedor.
        root_type: tipo raiz del contenedor.
        deferrer_type: tipo que se usa como deferrer.
        filter_type: tipo que se usa como filtro.
        """
        self.glob = {
            "__builtins__": RestrictedBuiltins(),
            "LISTA": asList,
            "RANGO": asRange,
            "GRUPO": asSet,
            "IP": IPAddress,
            "CISCOPASSWORD": password,
            "CISCOSECRET": secret,
            "cualquiera": deferrer_type(),
            "ninguno": None,
            "ninguna": None,
            "X": deferrer_type(),
            "x": deferrer_type(),
            "donde": filter_type
        }
        self.root = root_type
        self.data = self.root()

    def evaluate(self, expr):
        return eval(expr, self.glob, self.data)

