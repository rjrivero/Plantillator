#!/usr/bin/env python
# -*- vim: expandtab tabstop=4 shiftwidth=4 smarttab autoindent


from itertools import islice, chain, repeat

from .base import Deferrer, asIter
from .dataset import DataSet


class _Properties(dict):

    def __init__(self, cls, property_factory):
        dict.__init__(self)
        self.cls  = cls
        self.factory = property_factory

    def __getitem__(self, index):
        try:
            return dict.__getitem__(self, index)
        except KeyError:
            return self.setdefault(index, self.factory(self.cls, index))


class _DataObject(object):

    """Objeto cuyos atributos son accesibles como entradas de diccionario.

    Los DataObjects estan relacionados en forma de arbol. Cada nodo "hijo"
    tiene un nodo "padre", y un nodo "padre" puede tener varios nodos "hijo".
    Generalmente los nodos hijo de un mismo tipo se agrupan en un conjunto
    (DataSet).
    """

    def __init__(self, up=None, data=None):
        super(_DataObject, self).__init__()
        self._up = up
        if data:
            self.update(data)

    # "Meta-funciones" que permiten agregar atributos a la clase.

    @classmethod
    def _SubType(cls, attr, property_factory):
        """Crea un subtipo de este"""
        subtype = type(attr, (_DataObject,), {
            '_Parent': cls,
            '_Path': tuple(chain(cls._Path, (attr,)))
        })
        subtype._Properties = _Properties(subtype, property_factory)
        return subtype

    @classmethod
    def _NewSet(cls, *sets):
        sets = tuple(asIter(x) for x in sets)
        return DataSet(cls, chain(*sets))

    @property
    def _type(self):
        return self.__class__

    def __getattr__(self, attr):
        """Intenta crear el atributo solicitado usando _Properties
        Si no puede, lanza AttributeError
        """
        # Hay un problema porque, cuando el backend es una base de datos,
        # es posible que un atributo tenga el valor "None".
        # He probado a devolver "None" cuando un atributo no existe, por
        # consistencia,y da muchos problemas:
        # - muchas funciones internas empiezan a funcionar mal, porque
        #   obtienen valor None para '__iter__', '__str__', etc.
        # - Django tambien funciona mal, porque los campos ForeignKey
        #   buscan un atributo _X_cache, y al ser None no consultan a la bd.
        #
        # En consecuencia:
        # - Esta funcion lanzara AttributeError cuando se accede a un atributo
        #   inexistente.
        # - Para mantener consistencia con backend base de datos,
        #   - get(x, defval) devolvera defval si el valor es None.
        #   - los Fallbacks tomaran los valores None como inexistentes. Si no
        #     encuentran un valor valido, lanzaran AttributeError.
        #   - en el engine, "Si existe" / "Si no existe" tomara los valores
        #     None como no existentes.
        try:
            prop = self._type._Properties[attr]
        except (KeyError, ValueError, AttributeError) as details:
            raise AttributeError(attr)
        else:
            data = prop(self, attr)
            setattr(self, attr, data)
            return data

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
        """Busca el atributo, devuelve "defval" si no existe o es None"""
        try:
            retval = getattr(self, item)
        except AttributeError:
            return defval
        else:
            return retval if retval is not None else defval

    def setdefault(self, attrib, value):
        try:
            retval = getattr(self, attrib)
        except AttributeError:
            retval = None
        if retval is None:
            setattr(self, attrib, value)
            retval = value
        return retval

    def update(self, data):
        self.__dict__.update(data)

    def __contains__(self, attrib):
        """Comprueba que exista el atributo"""
        return (self.get(attrib) is not None)
        
    def iteritems(self):
        for (k, v) in self.__dict__.iteritems():
            if not k.startswith('_') and k not in ('up', 'fb'):
                yield (k, v)

    def __getitem__(self, item):
        return getattr(self, item)

    def __setitem__(self, name, value):
        setattr(self, name, value)

    # Herramientas para filtrado

    def _matches(self, kw):
        """Comprueba si el atributo indicado cumple el criterio."""
        return all(crit(self.get(key)) for key, crit in kw.iteritems())

    def __add__(self, other):
        if self._type != other._type:
            raise TypeError, other._type
        return self._type._NewSet(self, other)


def RootType(type_factory, name="DataObject"):
    """Crea un nuevo tipo raiz (_Parent == None) derivado de _DataObject

    type_factory es una factoria de propiedades para este tipo.
    Una factoria de propiedades es un callable que acepta una
    clase y un atributo, y devuelve una factoria de objetos.

    Una factoria de objetos es un callable que acepta un objeto
    y un atributo, y devuelve el valor del atributo solicitado.

    NOTA IMPORTANTE: para mantener la semantica y la compatibilidad,
    es importante que si una factoria de objetos devuelve ScopeSets,
    tenga una propiedad "_type" con el tipo de ScopeSet devuelto.
    """
    roottype = type(name, (_DataObject,), {'_Parent': None, '_Path': tuple()})
    roottype._Properties = _Properties(roottype, type_factory)
    return roottype


class GroupTree(dict):

    """Arbol de Grupos

    Factoria de propiedades que crea DataSets. Cada propiedad a la que se
    accede genera un nuevo DataSet del subtipo adecuado, en principio vacio,
    aunque se puede cambiar.
    """

    class DataFactory(object):
        def __init__(self, subtype):
            self._type = subtype
        def __call__(self, item, attr):
            return self._type._NewSet()
    
    def __init__(self, data=None):
        dict.__init__(self, data or dict())

    def __call__(self, cls, attr):
        """Devuelve una factoria de objetos que crea DataSets vacios"""
        return GroupTree.DataFactory(cls._SubType(attr, self[attr]))


class Fallback(_DataObject):

    """Realiza fallback en la jerarquia de objetos

    Objeto que implementa el mecanismo de fallback de los DataObjects.
    """

    def __init__(self, up, data=None, depth=None):
        _DataObject.__init__(self, up, data)
        self._depth = depth

    def __getattr__(self, attr):
        """Busca el atributo en este objeto y sus ancestros"""
        try:
            return _DataObject.__getattr__(self, attr)
        except AttributeError:
            for ancestor in islice(self._ancestors(), 0, self._depth):
                retval = ancestor.get(attr)
                if retval is not None:
                    return retval
            raise

    def _ancestors(self):
        while self._up:
            self = self._up
            yield self

