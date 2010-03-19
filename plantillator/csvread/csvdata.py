#!/usr/bin/env python
# -*- vim: expandtab tabstop=4 shiftwidth=4 smarttab autoindent


from itertools import chain, islice

from ..data.base import asIter
from ..data.dataobject import DataType, MetaData
from .csvset import CSVSet
from .source import DataSource


class CSVMetaData(MetaData):

    """Metadatos correspondientes a un DataObject leido de CSV"""

    def __init__(self, loader, name='RootType', parent=None):
        """Inicia el objeto.
        loader: TableLoader que se usa para resolver referencias a atributos
        name: label de la clase.
        parent: clase padre de cls en la jerarquia
        """
        MetaData.__init__(self, type(name, (CSVObject,), {}), name, parent)
        if not parent:
            # objeto raiz. No tiene path.
            self.path = None
        elif not parent._DOMD.path:
            # objeto de primer nivel. El parent no tiene path.
            self.path = name
        else:
            # resto de casos
            self.path = ".".join((parent._DOMD.path, name))
        # me asigno directamente el parser que va a leer mis datos.
        self.loader = loader
        self.parser = None
        if self.path:
            # si no existe el atributo, se lanza un KeyError. Util para
            # evitar que se creen subtipos que no se pueden leer.
            self.parser = loader[self.path]
        # Variables "implicitas" de los metadatos
        self.children = dict()
        self.attribs = dict()
        self._summary = None

    @property
    def summary(self):
        """Construye el sumario con los tres primeros atributos"""
        if not self._summary:
            # self.attribs contiene un diccionario nombre del atributo =>
            # orden de insercion. Le doy la vuelta para encontrar los
            # primeros atributos insertados.
            reverse = sorted((n, x) for (x, n) in self.attribs.iteritems())
            self._summary = tuple(i[1] for i in islice(reverse, 0, 3))
        return self._summary

    def subtype(self, attr):
        """Crea un subtipo de este"""
        try:
            return self.children[attr]
        except KeyError:
            meta = CSVMetaData(self.loader, attr, self._type)
            return self.children.setdefault(attr, meta._type)

    def new_set(self, *sets):
        sets = tuple(asIter(x) for x in sets)
        return CSVSet(self._type, chain(*sets))


class CSVObject(DataType(object)):

    """Objeto cuyos atributos son accesibles como entradas de diccionario.

    Los DataObjects estan relacionados en forma de arbol. Cada nodo "hijo"
    tiene un nodo "padre", y un nodo "padre" puede tener varios nodos "hijo".
    Generalmente los nodos hijo de un mismo tipo se agrupan en un conjunto
    (DataSet).
    """

    def __init__(self, up=None, data=None):
        super(CSVObject, self).__init__()
        self._up = up
        if data:
            self.update(data)

    def __getattr__(self, attr):
        """Intenta crear el atributo solicitado"""
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
        # - Esta funcion lanzara AttributeError cuando se acceda a un atributo
        #   inexistente.
        # - Para mantener consistencia con backend base de datos,
        #   - get(x, defval) devolvera defval si el valor es None.
        #   - los Fallbacks tomaran los valores None como inexistentes. Si no
        #     encuentran un valor valido, lanzaran AttributeError.
        #   - en el engine, "Si existe" / "Si no existe" tomara los valores
        #     None como no existentes.
        try:
            parser = self._DOMD.subtype(attr)._DOMD.parser
        except KeyError:
            raise AttributeError(attr)
        else:
            data = parser(self, attr)
            setattr(self, attr, data)
            return data

    def __add__(self, other):
        """Concatena dos DataSets"""
        if self._type != other._type:
            raise TypeError(other._type)
        return self._DOMD.new_set(self, other)

    def __str__(self):
        fields = (self.get(k) for k in self._type._DOMD.summary)
        return ", ".join(str(f) for f in fields if f is not None)

    def __repr__(self):
        # No es una representacion completa, es solo para no meter
        # mucha morralla en la shell
        return "DataObject<%s> (%s,...)" % (self._type._DOMD.path, str(self))


def RootType(loader):
    """Crea un nuevo tipo raiz (parent == None) derivado de CSVObject"""
    return CSVMetaData(loader)._type

