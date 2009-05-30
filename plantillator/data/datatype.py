#!/usr/bin/env python
# -*- vim: expandtab tabstop=4 shiftwidth=4 smarttab autoindent


import itertools
import re
from gettext import gettext as _

from data.operations import Deferrer


_FIELD_RE = re.compile(r"^[a-zA-Z][\w\d]*$")
_INVALIDFIELD = _("\"%(field)s\" no es un nombre de campo valido")
_EMPTYNAME = _("Debe dar un nombre al subtipo")
_INVALIDPATH = _("La ruta %(path)s no es valida")


class DataType(object):

    """Definicion de tipo

    Los tipos que vamos a usar tienen una estructura muy permisiva.
    Tan solo se define un conjunto de campos que se usan simplemente
    para bloquear el mecanismo de herencia de los DataObjects.

    Por defecto cualquier campo que se incluya en al tipo 
    bloquea la herencia del atributo correspondiente en los DataObjects
    que pertenezcan a ese tipo.
    """

    def __init__(self, parent=None):
        # self.blocked antes era un set, pero lo he convertido en una
        # list para preservar el orden de los campos, que puede ser significativo
        # para algunas aplicaciones. Por ejemplo, esto permite que los filtros
        # acepten argumentos posicionales (*arg) y no solo claves (**kw)
        self.up, self.blocked, self.subtypes = parent, list(), dict()

    def as_callable(self, key, val):
        """Normaliza un criterio

        - si "val" no es callable, se pasa a "MyOperator() == val"
        - si "key" identifica una lista, "val" se envuelve en un DeferredAny
        """
        if not hasattr(val, '__call__'):
            val = (Deferrer() == val)
        return (key, val)

    def adapt(self, arg, kw):
        """Normaliza criterios de busqueda

        Un criterio de busqueda es un conjunto de pares "atributo" =>
        "UnaryOperator". Un objeto cumple el criterio si todos los atributos
        existen y su valor cumple el criterio especificado por el
        UnaryOperator correspondiente.

        Para dar facilidades al usuario, las funciones __call__ aceptan
        argumentos que no son UnaryOperators, sino valores simples, listas,
        etc. Este metodo se encarga de adaptar esos parametros.
        """
        params = itertools.chain(zip(self.blocked, arg), kw.iteritems())
        return dict(self.as_callable(k, v) for k, v in params)

    def add_field(self, field, block=True):
        """Incluye un campo, opcionalmente bloqueando la herencia"""
        field = field.strip() or None if field else None
        if field:
            if not _FIELD_RE.match(field):
                raise SyntaxError(_INVALIDFIELD % { 'field': field })
            if block and field not in self.blocked:
                self.blocked.append(field)
        return field

    def add_subtype(self, name):
        """Recupera o crea un subtipo"""
        name = self.add_field(name, True)
        if name is None:
            raise SyntaxError(_EMPTYNAME)
        return (name, self.subtypes.setdefault(name, DataType(self)))


class TypeTree(object):

    """Arbol de tipos

    Define una jerarquia de tipos, donde unos tipos son sub-tipos de otros.
    """

    def __init__(self):
        """Inicializa el arbol"""
        self.root = DataType(None)

    def get_types(self, datapath):
        """Obtiene la secuencia de tipos identificada por la ruta dada

        La ruta es una cadena de texto con el formato
        "tipo.subtipo.subsubtipo..."

        Genera una secuencia de pares (nombre de tipo, tipo)
        """
        base = self.root
        try:
            for step in datapath.split("."):
                name, base = base.add_subtype(step)
                yield (name, base)
        except SyntaxError:
            raise SyntaxError(_INVALID_PATH % {'path': datapath})
