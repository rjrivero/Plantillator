#!/usr/bin/env python
# -*- vim: expandtab tabstop=4 shiftwidth=4 smarttab autoindent


from itertools import islice

from data.operations import Deferrer
from data.dataset import DataSet


def newDataSet(item, attrib):
    return DataSet(item.__class__._Children[attrib])

 
class _DataObject(object):

    """Objeto cuyos atributos son accesibles como entradas de diccionario.

    Los DataObjects estan relacionados en forma de arbol. Cada nodo "hijo"
    tiene un nodo "padre", y un nodo "padre" puede tener varios nodos "hijo",
    agrupados en un set (DataSet). Todos los "hijos" agrupados en un set
    deben ser del mismo tipo.
    """

    def __init__(self, up=None, data=None):
        self._up = up
        if data:
            self.update(data)

    # "Meta-funciones" que permiten agregar atributos a la clase.

    @classmethod
    def _SubType(cls, attr):
        """Crea un subtipo de este, pero sin enlazar en la jerarquia"""
        return type(attr, (_DataObject,), {'_Parent': cls, '_Children': {}})

    @classmethod
    def _GetChild(cls, attr, lazy=newDataSet):
        """Obtiene una subclase enlazada, y agrega el atributo.

        Si no existe ninguna subclase, crea una nueva enlazada a esta por
        los atributos de clase "_Parent" y "_Children". Ademas, agrega a
        todos los objetos de la clase un atributo que, al ser accedido
        por primera vez, devuelve un DataSet vacio de la clase hija.

        Opcionalmente, es posible hacer que el atributo devuelva otro
        valor utilizando la funcion "lazy". Si lazy !=None, la primera
        vez que se acceda al atributo se invocara a la funcion lazy
        pasandole como parametros:

            - El objeto a cuyo atributo se esta intentando acceder.
            - El nombre del atributo.

        "lazy" debe devolver el valor del atributo solicitado. IMPORTANTE!:
        la funcion "lazy" solo se usa al crear el atributo por primera vez,
        si despues se vuelve a llamar a _GetChild con otra funcion, no se
        sobreescribe.
        """
        try:
            return cls._Children[attr]
        except KeyError:
            def prop(self):
                lazyprop = lazy(self, attr)
                setattr(cls, attr, lazyprop)
                return lazyprop
            setattr(cls, attr, property(prop))
            return cls._Children.setdefault(attr, cls._SubType(attr))

    # Atributos basicos del DataObject: "up" y "fb"

    @property
    def up(self):
        """Ancestro de este objeto en la jerarquia de objetos"""
        return self._up

    @property
    def fb(self, data=None, depth=None):
        """Devuelve un "proxy" para la busqueda de atributos.

        Cualquier atributo al que se acceda sera buscado en el objeto que
        ha generado el fallback y sus ancestros
        """
        return Fallback(self, data, depth)

    # Funciones que proporcionan la dualidad objeto / diccionario.

    def get(self, item, defval=None):
        """Busca el atributo, devuelve "defval" si no lo encuentra"""
        try:
            return getattr(self, item)
        except AttributeError:
            return defval

    def setdefault(self, attrib, value):
        try:
            return getattr(self, attrib)
        except AttributeError:
            setattr(self, attrib, value)
            return value

    def update(self, data):
        self.__dict__.update(data)

    def __getitem__(self, item):
        try:
            return getattr(self, item)
        except AttributeError as details:
            raise KeyError, details

    def __setitem__(self, name, value):
        setattr(self, name, value)

    # Herramientas para filtrado

    @classmethod
    def _adapt(cls, kw):
        """Normaliza criterios de busqueda

        Un criterio de busqueda es un conjunto de pares "atributo" =>
        "UnaryOperator". Un objeto cumple el criterio si todos los atributos
        existen y su valor cumple el criterio especificado por el
        UnaryOperator correspondiente.

        Para dar facilidades al usuario, las funciones __call__ aceptan
        argumentos que no son UnaryOperators, sino valores simples, listas,
        etc. Este metodo se encarga de adaptar esos parametros.
        """
        d = Deferrer()
        return dict((k, v if hasattr(v, '__call__') else (d == v))
                    for k, v in kw.iteritems())

    def _matches(self, kw):
        """Comprueba si el atributo indicado cumple el criterio."""
        return all(crit(self.get(key)) for key, crit in kw.iteritems())

    # Funciones que "mimetizan" el comportamiento de un DataSet de
    # longitud unitaria.

    @property
    def _type(self):
        return self.__class__

    __add__ = DataSet.__add__

    def __iter__(self):
        """Se devuelve a si mismo"""
        yield self

    def __len__(self):
        """Devuelve longitud 1"""
        return 1

    def __call__(self, **kw):
        return self if self._matches(self._adapt(kw)) else DataSet(self._type)


def RootType(name="DataObject"):
    """Crea un nuevo tipo raiz (parent == None) derivado de _DataObject"""
    return type(name, (_DataObject,), {'_Parent': None,'_Children': dict()})

DataObject = RootType()


class Fallback(_DataObject):

    """Realiza fallback en la jerarquia de objetos

    Implementa un mecanismo de fallback en la jerarquia de objetosObjeto que implementa el mecanismo de fallback de los DataObjects."""

    def __init__(self, up, data=None, depth=None):
        _DataObject.__init__(self, up, data)
        self._depth = depth

    def _ancestors(self):
        while self._up:
            self = self._up
            yield self

    def __getattr__(self, attr):
        """Busca el atributo en este objeto y sus ancestros"""
        try:
            return _DataObject.__getattr__(self, attr)
        except AttributeError:
            for ancestor in islice(self._ancestors(), 0, self._depth):
                try:
                    return getattr(ancestor, attr)
                except AttributeError:
                    pass
            raise
