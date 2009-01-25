#!/usr/bin/env python
# -*- vim: expandtab tabstop=4 shiftwidth=4 smarttab autoindent


from gettext import gettext as _

from myoperator import UnaryOperator, MyOperator, DeferredAny


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

    _BADCOLUMNNAME = _("\"%(field)s\" no es un nombre de columna valido")
    _MISSINGPKEY = _("No se ha especificado clave primaria")
    _PKEYCHANGEFORBIDDEN = _("No se permite cambiar la clave primaria")
    _UNDEFINEDKEY = _("No se ha definido una clave primaria")
    _ONLYONEARG = _("Solo se admite un argumento posicional")

    def __init__(self, parent=None):
        self.pkey = None
        self.blockset = set()
        self.subtypes = dict()
        self.up = parent

    def _normfield(self, field):
        """Normaliza un nombre de campo.
        
        - A los nombres que terminen en "*", se les quita el "*"
        - Los nombres vacios se sustituyen por None
        - El resto de nombres se incluyen en la lista de bloqueo.
        """
        if not isinstance(field, str):
            raise SyntaxError, self._BADCOLUMNNAME % {'field': str(field)}
        field = (field.strip() or None) if field else None
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
            val = (MyOperator() == val)
        if key in self.subtypes:
            # si lo que se busca es un subtipo, hay que aplicar el
            # operador no al atributo (que sera una lista), sino a
            # cada uno de los elementos de la lista.
            val = DeferredAny(val)
        return (key, val)

    def fieldset(self, fields):
        """Construye un fieldset normalizando una lista de campos."""
        fieldset = tuple(self._normfield(f) for f in fields)
        self.pkey = self.pkey or fieldset[0]
        if not self.pkey:
           raise ValueError, self._MISSINGPKEY
        if self.pkey != fieldset[0]:
           raise SyntaxError, self._PKEYCHANGEFORBIDDEN
        return fieldset

    def normcrit(self, arg, kw):
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
            if not self.pkey:
                raise KeyError, self._UNDEFINEDPKEY
            if len(arg) > 1:
                raise ValueError, self._ONLYONEARG
            kw[self.pkey] = arg[0]
        # se convierten todos los argumentos en callable.
        return dict(self._normcrit(k, v) for k, v in kw.iteritems())

    def subtype(self, name):
        """Devuelve el suvbtipo indicado, o crea uno nuevo si no existia"""
        subtype = self.subtypes.get(name, None)
        if not subtype:
            subtype = ScopeType(self)
            self.subtypes[name] = subtype
            self.blockset.add(name)
        return subtype


