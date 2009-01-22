#!/usr/bin/env python
# -*- vim: expandtab tabstop=4 shiftwidth=4 smarttab autoindent


import operator
from myoperator import *
from scopelist import ScopeList


class ScopeType(object):

    """Definicion de tipo

    Los tipos que vamos a usar tienen una estructura muy permisiva.
    Tan solo se define una clave primaria y un conjunto de campos.

    La clave primaria no puede variar durante la vida del tipo, pero
    si que se pueden insertar nuevos campos en cualquier momento.

    Los campos solo sirven para bloquear el mecanismo de herencia de
    los ScopeDicts. Por defecto cualquier campo que se incluya en al tipo
    bloquea la herencia del atributo correspondiente en los ScopeDicts
    que pertenezcan a ese tipo.

    Si se quiere incluir un campo pero no bloquear la herencia, hay
    que marcar el nombre del campo con un "*" al final.
    """

    def __init__(self):
        self.pkey = None
        self.subtypes = dict()
        self.blockset = set()

    def _normfield(self, field):
        """Normaliza un nombre de campo.
        
        - A los nombres que terminen en "*", se les quita el "*"
        - Los nombres vacios se sustituyen por None
        - El resto de nombres se incluyen en la lista de bloqueo.
        """
        try:
            field = (field.strip() or None) if field else None
        except AttributeError:
            raise SyntaxError, "El nombre \"%s\" no es un nombre de columna valido" % str(field)
        if field:
            if field.endswith("*"):
                return field[:-1].strip() or None
            self.blockset.add(field)
        return field

    def _normcrit(self, key, val):
        """Normaliza un criterio

        - si "val" no es UnaryOperator, se convierte con "MyOperator() == val"
        - si "key" identifica una sublista, "val" se envuelve en un DeferredAny
        """
        if not isinstance(val, UnaryOperator):
            val = DeferredOperation("==", operator.eq, val)
        if key in self.subtypes:
            # si lo que se busca es un subtipo, hay que aplicar el
            # operador no al atributo (que sera una lista), sino a
            # cada uno de los elementos de la lista.
            val = DeferredAny(val)
        return (key, val)

    def fieldset(self, fields):
        """Construye un fieldset normalizando una lista de campos."""
        fieldset = tuple(self._normfield(f) for f in fields)
        if not self.pkey:
            self.pkey = fieldset[0]
        elif self.pkey != fieldset[0]:
            raise SyntaxError, "Cambio de clave primaria no permitido"
        return fieldset

    def addtype(self, name, subtype):
        """Registra un nuevo subtipo"""
        self.subtypes[name] = subtype
        self.blockset.add(name)

    def search_crit(self, arg, kw):
        """Normaliza criterios de busqueda

        Un criterio de busqueda es un conjunto de pares "atributo" =>
        "UnaryOperator". Un objeto cumple el criterio si todos los atributos
        existen y su valor cumple el criterio especificado por el
        UnaryOperator correspondiente.

        Para dar facilidades al usuario, las funciones __call__ aceptan
        argumentos que no son UnaryOperators, sino valores simples, listas,
        etc. Este metodo se encarga de adaptar esos parametros.

        - Permite especificar un argumento posicional, que se asocia a la
            clave primaria del tipo.
        - convierte los argumentos "nombrados" a UnaryOperators, si es
            necesario.
        """
        # si hay un argumento posicional, se asocia a la clave primaria
        kw = kw or dict()
        if arg:
            if not self.pkey or len(arg) > 1:
                raise KeyError, arg
            kw.update({self.pkey: arg[0]})
        # se convierten todos los argumentos en callable.
        return dict(self._normcrit(k, v) for k, v in kw.iteritems())

    def fallback(self, attrib, fallbacks):
        """Busca un atributo en los fallbacks"""
        if attrib not in self.blockset:
            for fallback in fallbacks:
                try:
                    return getattr(fallback, attrib)
                except KeyError:
                    pass
        return ScopeList(self.subtypes[attrib], self)

    def copy(self):
        """Devuelve una copia del ScopeType actual"""
        newtype = ScopeType()
        newtype.pkey = self.pkey
        newtype.subtypes = self.subtypes.copy()
        newtype.blockset = self.blockset.copy()
        return newtype

    def update(self, other):
        """Actualiza el ScopeType actual con los datos contenidos en otro

        - La clave primaria se conserva si es igual en los dos ScopeTypes,
            en otro caso se establece a None.
        - La lista de campos bloqueados se combina
        - La lista de subtipos se combina. Si hay subtipos con el mismo
            nombre, prevalecen los especificados en "other".

        Devuelve self.
        """
        if self.pkey != other.pkey:
            self.pkey = None
        self.subtypes.update(other.subtypes)
        self.blockset.update(other.blockset)
        return self

    def __repr__(self):
        """Esto se usa en los unittests"""
        return "ScopeType[pkey: %s, subtypes: %s, blocks: %s]" % (
                self.pkey,
                repr(sorted(self.subtypes.iteritems())),
                repr(sorted(self.blockset))
        )

