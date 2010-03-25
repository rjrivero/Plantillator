#!/usr/bin/env python
# -*- vim: expandtab tabstop=4 shiftwidth=4 smarttab autoindent


from itertools import chain, islice

from ..data import DataObject, DataSet, MetaData
from .source import DataSource


class SubReference(object):

    """Referencia a una subtabla.

    Todos los objetos referencia deben tener un atributo "_domd" que
    identifique la clase de objeto que devuelven, o None si es un
    escalar.
    """

    def __init__(self, domd):
        self._domd = domd
        self._mutable = False

    def __call__(self, item):
        return self._domd.parser(item, self._domd.name)


class CSVRefs(dict):

    """Resolvedor de referencias para datos cargados de un CSV.

    Resuelve las referencias a tablas hijas hechas desde un DataObject.
    """

    def __init__(self, loader, parent):
        super(CSVRefs, self).__init__()
        self._loader = loader
        self._parent = parent

    def __missing__(self, name):
        """Crea el objeto MetaData derivado y el resolvedor

        Si el nombre dado no corresponde a un subtipo, lanza error.
        """
        ref = SubReference(CSVMetaData(self._loader, name, self._parent))
        self[name] = ref
        return ref


class CSVMetaData(MetaData):

    """Metadatos correspondientes a un DataObject leido de CSV"""

    def __init__(self, loader, name, parent=None):
        """Inicia el objeto.
        loader: TableLoader que se usa para resolver referencias a atributos
        name: label de la clase.
        parent: clase padre de cls en la jerarquia
        """
        super(CSVMetaData, self).__init__(type(name, (DataObject,), {}), name, parent)
        if not parent:
            # objeto raiz. No tiene path.
            self.path = None
        elif not parent.path:
            # objeto de primer nivel. El parent no tiene path.
            self.path = name
        else:
            # resto de casos
            self.path = ".".join((parent.path, name))
        # me asigno directamente el parser que va a leer mis datos.
        # si no existe el atributo, se lanza un KeyError. Util para
        # evitar que se creen subtipos que no se pueden leer.
        self.parser = None if not self.path else loader[self.path]
        # Variables "implicitas" de los metadatos
        self._initvars(attribs={}, refs=CSVRefs(loader, self))

    def subtype(self, attr):
        """Crea el subtipo seleccionado"""
        submeta = self.refmeta(attr)
        # me aseguro de que es un subtipo y no una referencia o algo similar.
        if submeta.parent != self:
            raise KeyError(attr)
        return submeta._type


def RootType(loader):
    """Crea un nuevo tipo raiz (parent == None) derivado de DataObject"""
    return CSVMetaData(loader, 'RootType')._type

