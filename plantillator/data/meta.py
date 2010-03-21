#!/usr/bin/env python
# -*- vim: expandtab tabstop=4 shiftwidth=4 smarttab autoindent

from itertools import chain
import operator

from .base import BaseSet, asIter
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

    Todos los objetos referencia deben tener un atributo "_domd" que
    identifique la clase de objeto que devuelven, o None si es un
    escalar.
    """

    def __init__(self, table, **kw):
        self.table = table
        self.kw = kw
        self._domd = table._domd

    def __call__(self, item):
        kw = dict((k, (v if not hasattr(v, '_resolve') else v._resolve(item)))
                         for (k, v) in self.kw.iteritems())
        return self.table(**kw)


class UpReference(object):

    """Referencia al objeto "up" en la jerarquia

    Todos los objetos referencia deben tener un atributo "_domd" que
    identifique la clase de objeto que devuelven, o None si es un
    escalar.
    """

    def __init__(self, domd):
        self._domd = domd

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

    def follow(self, table, **kw):
        """Agrega una nueva relacion externa"""
        self.refs[table._domd.name] = ForeignReference(table, **kw)

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

    def filterset(self, dataset, **kw):
        """Filtra un Dataset, devuelve el resultado"""
        d = Deferrer()
        crit = dict((k, (v if hasattr(v, '_verify') else (d == v)))
                    for k, v in kw.iteritems())
        return self.concat(x for x in dataset if x._matches(crit))

    def produceset(self, dataset, attr):
        """Genera la lista de objetos hijos de la lista actual.

        Si el atributo no existe, lanza un KeyError.
        """
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



class ChainedResolver(object):

    """Resolvedor encadenado

    Sirve como base para los resolvedores de atributos y filtrado,
    y permite que se encadenen unos con otros:

    x = ChainedResolver().attrib1.attrib2(*arg, **kw).attrib3
    y = x._resolve(item) ==> y = item.attrib1.attrib2(*arg, **kw).attrib3
    """

    def __init__(self, parent=None):
        self._parent = parent

    def __getattr__(self, attrib):
        if attrib.startswith("_"):
            raise AttributeError(attrib)
        return AttrResolver(self, attrib)

    def __call__(self, *arg, **kw):
        return FilterResolver(self, arg, kw)

    def __pos__(self):
        return PosResolver(self)

    def _resolve(self, item):
        return item if not self._parent else self._parent._resolve(item)


class AttrResolver(ChainedResolver):

    """Resolvedor de atributos

    Sirve para posponer el acceso a los atributos de un objeto. Por ejemplo,

    x = AttrResolver().attrib1.attrib2
    y = x._resolve(item) ==> y = item.attrib1.attrib2
    """

    def __init__(self, parent, attrib):
        super(AttrResolver, self).__init__(parent)
        self._attrib = attrib

    def _resolve(self, item):
        item = super(AttrResolver, self)._resolve(item)
        return item.get(self._attrib)


class FilterResolver(ChainedResolver):

    """Resolvedor de filtrados

    Sirve para posponer el filtrado de una lista. Por ejemplo,

    x = FilterResolver(*args, *kw)
    y = x._resolve(item) ==> y = item(*args, **kw)
    """

    def __init__(self, parent, *arg, **kw):
        super(FilterResolver, self).__init__(parent)
        self._arg = arg
        self._kw = kw

    def _resolve(self, item):
        item = super(FilterResolver, self)._resolve(item)
        return item(*self._arg, **self._kw)


class PosResolver(ChainedResolver):

    """Resolvedor del operador prefijo "+"

    Permite posponer la extraccion de un elemento de una lista.
    """

    def __init__(self, parent):
        super(PosResolver, self).__init__(parent)

    def _resolve(self, item):
        item = super(PosResolver, self)._resolve(item)
        return +item


class ListResolver(object):

    """Resolvedor de listas

    Resuelve una lista con referencias dinamicas a un objeto
    """

    def __init__(self, items):
        self.items = items

    def _resolve(self, item):
        return tuple(x if not hasattr(x, '_resolve') else x._resolve(item)
                       for x in self.items)


class StaticCrit(object):

    """Criterio estatico.

    Callable que comprueba si un par (atributo, objeto) cumple
    un cierto criterio.

    En este caso, el criterio es la comparacion del valor dado
    con un valor estatico.

    Si el atributo es una lista, lo que se compara es
    la longitud de esa lista. 
    """

    def __init__(self, operator, operand):
        self.operator = operator
        self.operand = operand

    def _verify(self, value, item=None):
        if hasattr(value, '__iter__'):
            value = len(value)
        return self.operator(value, self.operand)

    def _resolve(self, item):
        """Resuelve los parametros dinamicos y devuelve un criterio estatico"""
        return self


class DynamicCrit(StaticCrit):

    """Criterio dinamico

    Callable que comprueba si un par (atributo, objeto) cumple
    un cierto criterio.

    En este caso, el criterio es la comparacion del valor dado
    con un valor dinamico. El valor dinamico se calcula en funcion del
    propio objeto que se esta comparando.

    Si el atributo es una lista, lo que se compara es
    la longitud de esa lista. 
    """

    def __init__(self, operator, operand):
        super(DynamicCrit, self).__init__(operator, None)
        self.dynamic = operand

    def _verify(self, value, item):
        self.operand = self.dynamic._resolve(item)
        return super(DynamicCrit, self)._verify(value, item)

    def _resolve(self, item):
        """Resuelve los parametros dinamicos y devuelve un criterio estatico"""
        return StaticCrit(self.operator, self.dynamic._resolve(item))


class FilterCrit(StaticCrit):

    """Criterio estatico con prefiltro

    Callable que comprueba si un par (atributo, objeto) cumple
    un cierto criterio.

    En este caso, antes de comparar el valor, se le aplica un
    prefiltro.

    Si el atributo es una lista, lo que se compara es
    la longitud de esa lista. 
    """

    def __init__(self, operator, operand, prefilter):
        super(FilterCrit, self).__init__(operator, operand)
        self.prefilter = prefilter

    def _verify(self, value, item):
        return super(FilterCrit, self)._verify(self.prefilter(value), item)


class Deferrer(object):

    """Factoria de operadores

    Cuando se le aplica un operador de comparacion a un objeto de
    este tipo, el resultado es un version pospuesta de ese operador.

    Por ejemplo, (Deferrer() >= 5) devuelve un callable que, al ser
    invocado como <X>(item, attr) devuelve el resultado de
    "item.getattr(attr) >= 5".
    """

    def _dynlist(self, items):
        """Verifica si una lista tiene elementos dinamicos.

        Si no los tiene, devuelve la lista. Si los tiene, devuelve un
        callable que aplica el item a los elementos dinamicos de la lista.
        """
        # si "items" es un elemento dinamico, no lo convertimos a lista, sino
        # que confiamos en que el resultado de evaluarlo sera una lista.
        if hasattr(items, '_resolve'):
            return items
        # si no es un callable, nos aseguramos de que es iterable y
        # revisamos si tiene algun elemento dinamico.
        items = asIter(items)
        if not any(hasattr(x, '_resolve') for x in items):
            return items
        return ListResolver(items)

    def _defer(self, operator, operand):
        """Devuelve el criterio adecuado"""
        if not hasattr(operand, '_resolve'):
            return StaticCrit(operator, operand)
        return DynamicCrit(operator, operand)

    def _verify(self, value, item=None):
        return bool(value)

    def __eq__(self, other):
        return self._defer(operator.eq, other)

    def __ne__(self, other):
        return self._defer(operator.ne, other)

    def __lt__(self, other):
        return self._defer(operator.lt, other)

    def __le__(self, other):
        return self._defer(operator.le, other)

    def __gt__(self, other):
        return self._defer(operator.gt, other)

    def __ge__(self, other):
        return self._defer(operator.ge, other)

    def __mul__(self, arg):
        """Comprueba la coincidencia con una exp. regular"""
        return self._defer(lambda x, y: y.search(x) and True or False,
                          re.compile(arg))

    def __add__(self, arg):
        """Comprueba la pertenecia a una lista"""
        return self._defer(lambda x, y: x in y, self._dynlist(arg))

    def __sub__(self, arg):
        """Comprueba la no pertenencia a una lista"""
        return self._defer(lambda x, y: x not in y, self._dynlist(arg))

    def _resolve(self, item):
        return self


class Filter(Deferrer):

    """Factoria de operadores

    Cuando se le aplica un operador de comparacion a un objeto de
    este tipo, el resultado es un version pospuesta de ese operador.

    Por ejemplo, (Filter() >= 5) devuelve un operador
    pospuesto que, al ser aplicado sobre una variable X, devuelve
    el resultado de "len(<X(*arg, **kw)>)) >= 5".
    """

    def __init__(self, *arg, **kw):
        super(Filter, self).__init__()
        self.arg = arg
        self.kw = kw

    def _defer(self, operator, operand):
        """Devuelve una funcion f(x) == operator(len(x(*arg, **kw)), operand)
        Es decir, filtra x, y luego compara la longitud de la lista filtrada
        con el operand.
        """
        def prefilter(value):
            return len(value(*self.arg, **self.kw))
        return FilterCrit(operator, operand, prefilter)

    def _verify(self, value, item=None):
        return len(value(*self.arg, **self.kw)) == len(value)

