#!/usr/bin/env python
# -*- vim: expandtab tabstop=4 shiftwidth=4 smarttab autoindent


from data.datatype import DataType
from data.dataset import DataSet


class DataObject(dict):

    """Objeto accesible por "scopes"

    Puede accederse a los atributos del  objeto como si fueran valores de
    un diccionario. Si se hace referencia a un atributo que no existe, se
    sube en la jerarquia buscandolo.
    """

    def __init__(self, mytype, data=None, fallback=None):
        """Inicializa el DataObject con los datos y fallback especificados"""
        dict.__init__(self, data or dict())
        self._type, self._up = mytype, fallback

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
            if self._up and item not in self._type.blocked:
                return self._up[item]
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

    def __call__(self, **kw):
        """Busca los elementos de la lista que cumplan los criterios dados"""
        crit = self._type.adapt(kw)
        return self if self._matches(crit) else DataSet(self._type)

