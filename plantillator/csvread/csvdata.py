#!/usr/bin/env python
# -*- vim: expandtab tabstop=4 shiftwidth=4 smarttab autoindent


from itertools import chain

from ..data.dataobject import DataType, MetaData
from .source import DataSource


class CSVMetaData(MetaData):

    """Metadatos correspondientes a un DataObject leido de CSV"""

    Source = DataSource()

    def __init__(self, cls, name, parent=None):
        MetaData.__init__(self, cls, name, parent)
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
        self.parser = None
        if self.path:
            # si no existe el path, se lanza un KeyError. Util para
            # evitar que se creen subtipos que no se pueden leer.
            self.parser = CSVMetaData.Source[self.path]

    def subtype(self, attr):
        """Crea un subtipo de este"""
        try:
            return self.children(attr)
        except KeyError:
            stype = type(attr, (CSVObject,), dict())
            setattr(stype, '_DOMD', CSVMetaData(subt, attr, self._type)
            return self.children.setdefault(attr, stype)

    def new_set(self, cls, *sets):
        sets = tuple(asIter(x) for x in sets)
        return DataSet(self._type, chain(*sets))


class CSVObject(DataType(object)):

    """Objeto cuyos atributos son accesibles como entradas de diccionario.

    Los DataObjects estan relacionados en forma de arbol. Cada nodo "hijo"
    tiene un nodo "padre", y un nodo "padre" puede tener varios nodos "hijo".
    Generalmente los nodos hijo de un mismo tipo se agrupan en un conjunto
    (DataSet).
    """

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


def RootType():
    """Crea un nuevo tipo raiz (_Parent == None) derivado de CSVObject"""
    root = type("RootType", (CSVObject,), dict())
    setattr(root, '_DOMD', CSVMetaData(root))
    return root
