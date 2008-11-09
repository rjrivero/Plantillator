#!/usr/bin/env python
# -*- vim: expandtab tabstop=4 shiftwidth=4 smarttab autoindent

from inspect import getmembers
from itertools import chain
from operator import itemgetter

from scopetype import ScopeType


class ScopeDict(dict):

    """Diccionario accesible por "scopes"

    Puede accederse a los valores del diccionario por clave, o como
    atributos del abjeto. Si se hace referencia a un atributo que no
    existe, lo busca en el diccionario.
    
    Es posible usar un diccionario de fallback que se utiliza en caso de
    no encontrar el atributo buscado en el diccionario actual.
    """

    def __init__(self, mytype, data=None, *fallback):
        """Inicializa el ScopeDict con los datos y fallback especificados

        Los datos se chequean contra la lista de palabras reservadas
        (ver _keywords()).
        """
        dict.__init__(self, data or {})
        self._type = mytype
        self._fallback = fallback
        self._check_kw()

    def _check_kw(self):
        """Comprueba que ningun valor del diccionario es un keyword"""
        kw = set(self.keys()).intersection(self._keywords())
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

    def copy(self):
        """Copia el ScopeDict y usa el actual como fallback del nuevo"""
        return ScopeDict(self._type, self, self)

    def get(self, key, defval=None):
        try:
            return getattr(self, key)
        except KeyError:
            return defval

    def __getattr__(self, attrib):
        """Busca el atributo en el diccionario y los fallbacks"""
        try:
            return self[attrib]
        except KeyError:
            return self._type.fallback(attrib, self._fallback)

    def __add__(self, added):
        """Une dos ScopeDicts y usa los originales como fallback
        
        El primer elemento de la suma tiene preferencia, es decir,
        en caso de que un campo se repita en los dos ScopeDicts, el valor
        que queda es el que estuviera en el primero.
        
        En el caso de los fallbacks, los fallbacks del primero tambien
        tienen preferencia sobre los del segundo.
        """
        newtype = added._type.copy().update(self._type)
        newdict = ScopeDict(newtype, added, self, added)
        newdict.update(self)
        return newdict

    def __eq__(self, other):
        """Compara por identidad, no por valor"""
        return self is other

    def __call__(self, *arg, **kw):
        """Busca un ScopeDict que cumpla el criterio especificado por arg, kw

        En este caso, devuelve self si el ScopeDict cumple los criterios y
        lanza un KeyError si no los cumple.

        Los criterios que debe cumplir un objeto son:

        - argumentos posicionales (arg): puede haber como maximo 1, y se
            compara con la clave primaria del dict.
        - argumentos "nombrados (kw): puede haber varios. Cada uno se refiere
            a un atributo / clave del dict, y se compara con el valor de
            dicha clave.

        Los argumentos pueden ser objetos simples (se compara la igualdad),
        o UnaryOperators (se aplican al valor del atributo / clave).
        """
        if not arg and not kw:
            return self
        if self._matches(self._type.search_crit(arg, kw)):
            return self
        raise KeyError, (arg, kw)
 
    def __repr__(self):
        # muestro los elementos del diccionario ordenados, para que la
        # representacion sea estable y pueda usarse en los unittests 
        inners = sorted(self.iteritems(), key=itemgetter(0))
        status = chain((repr(self._type),), (repr(x) for x in inners))
        return "\n".join(status)

