#!/usr/bin/env python
# -*- vim: expandtab tabstop=4 shiftwidth=4 smarttab autoindent

from inspect import getmembers
from itertools import chain
from operator import itemgetter
from gettext import gettext as _

from scopetype import ScopeType


class DataSignature(object):
    """Propiedades basicas de los objetos manipulables por las plantillas

    El motor de plantillas va a trabajar con objetos sobre los que se puede:
        * iterar
        * obtener atributos
        * filtrar
    """

    def __iter__(self):
        return tuple()

    def __getattr__(self, attrib):
        raise KeyError, attrib

    def __call__(self, *arg, **kw):
        raise KeyError, (arg, kw)

     
class ScopeDict(DataSignature):

    """Diccionario accesible por "scopes"

    Puede accederse a los valores del diccionario por clave, o como
    atributos del abjeto. Si se hace referencia a un atributo que no
    existe, lo busca en el diccionario.
    
    Es posible usar un diccionario de fallback que se utiliza en caso de
    no encontrar el atributo buscado en el diccionario actual.
    """

    _RESERVEDKW = _("\"%(kw)s\" es una palabra reservada")

    def __init__(self, mytype, data=None, fallback=None):
        """Inicializa el ScopeDict con los datos y fallback especificados

        Los datos se chequean contra la lista de palabras reservadas
        (ver _keywords()).
        """
        self.up = fallback
        self._data = data.copy() if data else dict()
        self._type = mytype
        self._check_kw()

    def __iter__(self):
        yield self

    def _check_kw(self):
        """Comprueba que ningun valor del diccionario es un keyword"""
        kw = set(self._data.keys()).intersection(self._keywords())
        if kw:
           raise ValueError, self._RESERVEDKW % { 'kw': kw }

    def _keywords(self):
        """Devuelve una lista de palabras reservadas"""
        return set(map(itemgetter(0), getmembers(self)))

    def _matches(self, kw):
        """Comprueba si el atributo indicado cumple el criterio.

        El "criterio" en este caso viene expresado por "kw",
        que es un diccionario con pares "clave": "UnaryOperator". Cada
        operador es evaluado con el valor del atributo indicado por
        "key", y debe devolver True si el campo cumple el criterio.

        Si el atributo indicado no existe, tambien se invoca al operador,
        pero con el valor None. Esto es para permitir operadores que
        comprueben que no existe un cierto atributo.
        """
        return all(crit(self.get(key, None)) for key, crit in kw.iteritems)

    def get(self, key, defval=None):
        try:
            return self[key]
        except KeyError:
            return defval

    def __getitem__(self, index):
        """Busca el atributo en el diccionario y los fallbacks

        Si el atributo no esta lanza un KeyError, excepto en el
        caso de que el atributo sea un subtipo. En ese caso, devuelve
        una DataSignature vacia
        """
        try:
            return self._data[index]
        except KeyError:
            if self.up and index not in self._type.blockset:
                return self.up[index]
            if index in self._type.subtypes:
                return DataSignature()
            raise KeyError, index

    __getattr__ = __getitem__

    def __setitem__(self, index, item):
        """Almacena un item en el diccionario"""
        self._data[index] = item

    def __call__(self, *arg, **kw):
        """Comprueba si el ScopeDict cumple el criterio dado por arg, kw

        En este caso, devuelve self si el ScopeDict cumple los criterios y
        lanza un KeyError si no los cumple.

        Los criterios que debe cumplir un objeto son:

        - argumentos posicionales (arg): puede haber como maximo 1, y se
            compara con la clave primaria del dict.
        - argumentos "nombrados"(kw): puede haber varios. Cada uno se refiere
            a un atributo / clave del dict, y se compara con el valor de
            dicha clave.

        Los argumentos pueden ser objetos simples (se compara la igualdad),
        o UnaryOperators (se aplican al valor del atributo / clave).
        """
        if self._matches(self._type.normcrit(arg, kw)):
            return self
        raise KeyError, (arg, kw)



