#!/usr/bin/env python
# -*- vim: expandtab tabstop=4 shiftwidth=4 smarttab autoindent


import itertools

from data.datatype import DataType
from data.dataset import DataSet


# Todos los DataObjects que alguna vez tengan que ser identificados por un nombre
# (dentro de un select, por ejemplo, o en una lista mostrada por una GUI), deben
# tener al menos uno de estos atributos.
NAMING_ATTRIBS = ("nombre", "descripcion", "detalles")


class DataObject(dict):

    """Objeto accesible por "scopes"

    Puede accederse a los atributos del  objeto como si fueran valores de
    un diccionario. Si se hace referencia a un atributo que no existe, se
    sube en la jerarquia buscandolo.
    """

    def __init__(self, mytype, data=None, fallback=None):
        """Inicializa el DataObject con los datos y fallback especificados"""
        dict.__init__(self, data or dict())
        self._type = mytype
        # hago "up" accesible a lo que se ejecute dentro de mi entorno
        self['up'] = fallback

    @property
    def up(self):
        """up siempre esta definido, evito el fallback"""
        return dict.__getitem__(self, "up")

    def __hash__(self):
        return hash(id(self))

    def __eq__(self, other):
        return self is other

    def __cmp__(self, other):
        return cmp(id(self), id(other))

    def __iter__(self):
        yield self

    def __getitem__(self, item):
        try:
            return dict.__getitem__(self, item)
        except KeyError:
            if self.up and item not in self._type.blocked:
                return self.up[item]
            return self.setdefault(item, DataSet(self._type.subtypes[item]))

    def __getattr__(self, attrib):
        try:
            return self[attrib]
        except KeyError:
            raise AttributeError, attrib

    def __setattr__(self, key, val):
        """Da valor al atributo"""
        try:
            self[key] = val
        except KeyError:
            raise AttributeError, key

    def _matches(self, kw):
        """Comprueba si el atributo indicado cumple el criterio."""
        return all(crit(self.get(key)) for key, crit in kw.iteritems())

    def get(self, item, defval=None):
        """Busca el atributo, devuelve "defval" si no lo encuentra"""
        try:
            return self[item]
        except KeyError:
            return defval

    def __call__(self, *arg, **kw):
        """Busca los elementos de la lista que cumplan los criterios dados"""
        crit = self._type.adapt(arg, kw)
        return self if self._matches(crit) else DataSet(self._type)

    def replace(self, match):
        """evalua match.group("expr") usandose a si mismo como locals"""
        return str(eval(match.group('expr'), self))

    def __str__(self):
        """Identifica al objeto por su nombre o sus primeros atributos"""
        tag = itertools.chain(
                    (self.get(x, None) for x in NAMING_ATTRIBS),
                    (self.get(x, None) for x in self._type.blocked))
        tag = (str(item) for item in tag if item is not None)
        return ", ".join(itertools.islice(tag, 0, 3))
 
