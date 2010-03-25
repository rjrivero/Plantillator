#!/usr/bin/env python
# -*- vim: expandtab tabstop=4 shiftwidth=4 smarttab autoindent

from itertools import chain

from .resolver import asIter
from .base import BaseSet, SYMBOL_SELF, SYMBOL_FOLLOW
from .filter import Deferrer
from .dataobject import DataSet


def not_none(filter_me):
    """Devuelve los objetos de la lista que no son None"""
    return (x for x in filter_me if x is not None)


def not_empty(filter_me):
    """Devuelve los objetos de la lista que no son listas vacias"""
    return (x for x in filter_me if len(x))


class ForeignReference(object):

    """Referencia externa

    Objeto callable que, dado un item, devuelve todos los elementos
    de otra tabla referenciados por el item.

    Los criterios de filtrado se especifican con argumentos nombrados.
    Todos los objetos referencia deben tener:

    - Un atributo "_domd" que identifique la clase de objeto que
      devuelven, o None si es un escalar.
    - Un atributo "_mutable" que indique si el campo es dinamico.
    """

    def __init__(self, dataset, crit):
        """Crea la referencia.
        dataset: Dataset al que apunta la referencia.
        crit:    lista de criterios (pares clave, crit) que se usan para
                 filtrar la tabla.
        """
        self.dataset = dataset
        self.crit = crit
        self._domd = dataset._domd
        self._mutable = True

    def __call__(self, item):
        return self._domd.filterset({SYMBOL_FOLLOW: item}, self.dataset, self.crit)


class UpReference(object):

    """Referencia al objeto "up" en la jerarquia

    Todos los objetos referencia deben tener un atributo "_domd" que
    identifique la clase de objeto que devuelven, o None si es un
    escalar.
    """

    def __init__(self, domd):
        self._domd = domd
        self._mutable = False

    def __call__(self, item):
        return item._up


class MetaData(object):

    """MetaDatos relacionados con una clase de DataObject

    Variables del constructor

    name:    Label de la clase (string).
    parent:  Clase padre en la jerarquia (MetaData)

    Atributos basicos

    attribs: Conjunto de atributos (dict(string, orden))
    summary: Lista ordenada de atributos que puede usarse como
             "sumario" o descripcion abreviada de un objeto

    Atributo avanzado:

    refs:    Diccionario que resuelve las referencias a atributos
             dinamicos. La clave debe ser un nombre de atributo,
             y el valor debe ser un ForeignReference (u otro
             callable con la misma signatura)
    mutables: Lista de atributos que se calculan dinamicamente, y
             que se pueden invalidar tras un cambio.

    Por convencion, las clases derivadas de DataObject(...) deben tener un
    atributo _domd (DataObject MetaData) de este tipo.
    """

    def __init__(self, cls, name, parent=None):
        # Nos encargamos de poner el atributo aqui
        setattr(cls, "_domd", self)
        # por convencion, el tipo siempre se llama _type.
        self._type = cls
        self.parent = parent
        self.name = name

    def _initvars(self, attribs={}, refs={}, upref=None):
        """Inicializa las variables del objeto"""
        self.refs = refs
        self.refs["up"] = upref or UpReference(self.parent)
        self.attribs = attribs
        self.update_summary()

    def update_summary(self):
        """Actualiza el summary, si se han agregado atributos"""
        sortattrs = sorted((n, x) for (x, n) in self.attribs.iteritems())
        self.summary = tuple(x[1] for x in sortattrs[:3])

    def follow(self, table, crit):
        """Agrega una nueva relacion externa"""
        self.refs[table._domd.name] = ForeignReference(table, crit)

    def refmeta(self, attr):
        """Devuelve la MetaData de una referencia."""
        producer = self.refs[attr]
        if not hasattr(producer, '_domd'):
            raise KeyError(attr)
        return producer._domd

    def produce(self, item, attr):
        """Genera la lista de objetos hijos del item actual.

        Si el atributo no existe, devuelve None.
        """
        return self.refs[attr](item)

    def _matches(self, symbols, dataset, crit):
        """Devuelve los elementos del dataset que cumplen el criterio"""
        for item in dataset:
            symbols[SYMBOL_SELF] = item
            if all(v._verify(symbols, item.get(k)) for (k, v) in crit):
                yield item

    def crit(self, kw):
        """Convierte un diccionario de pares atributo => valor en criterio"""
        d = Deferrer()
        return tuple((k, v if hasattr(v, '_verify') else (d == v))
                           for k, v in kw.iteritems())

    def filterset(self, symbols, dataset, crit):
        """Filtra un Dataset, devuelve el resultado"""
        return self.concat(self._matches(symbols, dataset, crit))

    def produceset(self, dataset, attr):
        """Genera la lista de objetos hijos de la lista actual.

        Si el atributo no existe, lanza un KeyError.
        """
        if attr.startswith("_"):
            raise KeyError(attr)
        try:
            submeta = self.refmeta(attr)
        except KeyError:
            # Importante comprobar que no es un atributo "magico" (__XXX__)!
            # De lo contrario, __getitem__ devolvera listas vacias cuando
            # se acceda a sus atributos magicos, lo que puede causar errores.
            if attr not in self.attribs:
                raise KeyError(attr)
            return BaseSet(not_none(x.get(attr) for x in dataset))
        else:
            return submeta.concat(*tuple(not_empty(x.get(attr) for x in dataset)))

    def concat(self, *sets):
        """Concatena varios DataObjets o DataSets del mismo tipo"""
        sets = tuple(asIter(x) for x in sets)
        return DataSet(self, chain(*sets))

    @property
    def mutables(self):
        for key, ref in self.refs.iteritems():
            if ref._mutable:
                yield key

    def invalidate(self, dataset, attribs=None):
        attribs = attribs or self.mutables
        for item in dataset:
            item.invalidate(attribs)

