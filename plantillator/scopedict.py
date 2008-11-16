#!/usr/bin/env python
# -*- vim: expandtab tabstop=4 shiftwidth=4 smarttab autoindent

from inspect import getmembers
from itertools import chain
from operator import itemgetter

from scopetype import ScopeType


class ScopeDict(object):

    """Diccionario accesible por "scopes"

    Puede accederse a los valores del diccionario por clave, o como
    atributos del abjeto. Si se hace referencia a un atributo que no
    existe, lo busca en el diccionario.
    
    Es posible usar un diccionario de fallback que se utiliza en caso de
    no encontrar el atributo buscado en el diccionario actual.
    """

    def __init__(self, mytype, data=None, fallback=None):
        """Inicializa el ScopeDict con los datos y fallback especificados

        Los datos se chequean contra la lista de palabras reservadas
        (ver _keywords()).
        """
        self.up = fallback
        self._data = data.copy() if data else {}
        self._type = mytype
        self._check_kw()

    def _check_kw(self):
        """Comprueba que ningun valor del diccionario es un keyword"""
        kw = set(self._data.keys()).intersection(self._keywords())
        if kw:
           raise ValueError, "Palabras Reservadas: %s" % kw

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
        comprueben que no exisrte un cierto atributo.
        """
        for key, crit in kw.iteritems():
            try:
                item = getattr(self, key)
            except KeyError:
                item = None
            if not crit(item):
                return False
        return True

    def get(self, key, defval=None):
        try:
            return self[key]
        except KeyError:
            return defval

    def __getattr__(self, attrib):
        """Busca el atributo en el diccionario y los fallbacks"""
        try:
            return self._data[attrib]
        except KeyError:
            return self._type.fallback(self, attrib)

    __getitem__ = __getattr__

    def __setitem__(self, index, item):
        """Almacena un item en el diccionario"""
        self._data[index] = item

    def __call__(self, *arg, **kw):
        """Busca un ScopeDict que cumpla el criterio especificado por arg, kw

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
        if not arg and not kw:
            return self
        if self._matches(self._type.normcrit(arg, kw)):
            return self
        raise KeyError, (arg, kw)

