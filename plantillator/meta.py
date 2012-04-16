#/usr/bin/env python


import bisect
import sys
import os.path
import re

from traceback import format_exception_only
from itertools import chain
from .oset import OrderedSet


class DataError(Exception):

    """
    Encapsula las excepciones lanzadas durante el analisis de una fuente
    de datos.

    - self.source: identificador de la fuente de datos que se analiza.
    - self.index: indice (n. de linea, generalmente) del registro erroneo.
    - self.exc_info: Si aplica, tupla (tipo, excepcion, traceback)
    - self.warnings: Si aplica, lista de pares (n. de linea, lista de errores)
    """

    def __init__(self, source, index, warnings=None, stack=True):
        super(DataError, self).__init__()
        self.source   = source
        self.index    = index
        self.warnings = warnings
        self.exc_info = sys.exc_info() if stack else None

    def __str__(self):
        diag = list((
            "***",
            "Error en fichero de datos %s [primer error en linea %s]" % (os.path.basename(self.source), self.index),
            "***"))
        if self.warnings:
            diag.extend(("linea %d:\n  %s" % (w[0], "\n  ".join(w[1])) for w in self.warnings))
        if self.exc_info:
            diag.append("".join(format_exception_only(*(self.exc_info[:2]))))
        return "\n".join(diag)


def kw_as_crit(key, val):
    """Convierte un criterio expresado como clave=valor en un callable"""
    if val is DataSet.NONE:
        # Esto me vale para campos de tipo lista o set que esten vacios.
        # (por lo menos, hasta que alguien los instancie con "__getattr__"...)
    	return lambda x: x.get(key, None) is None
    if val is DataSet.ANY:
        # Esto me vale para campos de tipo lista o set que no esten vacios.
        # (por lo menos, hasta que alguien los instancie con "__getattr__"...)
        return lambda x: x.get(key, None) is not None
    return lambda x: x.get(key, None) == val


def search_crit(items, args, kw=None):
    """Filtra una lista con los criterios dados, sin usar indices"""
    if kw:
        kw   = (kw_as_crit(k, v) for (k, v) in kw.iteritems())
        args = tuple(chain(args, kw))
    try:
        # Intentamos el match en bloque. Si sale, nos ahorramos una
        # llamada a funcion y un try - except en cada elemento...
        return tuple(x for x in items if all(c(x) for c in args))
    except (AttributeError, AssertionError):
        # Si no sale, no queda mas remedio que ir uno por uno.
        return tuple(x for x in items if matches(x, args))


def matches(item, crit):
    """Comprueba si un objeto cumple un criterio.

    Si la evaluacion del criterio lanza una exception durante la
    resolucion, se considera que el criterio no se cumple.
    """
    try:
        return all(c(item) for c in crit)
    except (AttributeError, AssertionError):
        return False


class BaseSet(frozenset):
    
    # Tienen que ser todo clases globales, por pickle, y ademas
    # frozen, para que se puedan hashear.

    def __pos__(self):
        assert(len(self) == 1)
        return tuple(self)[0]

    def __call__(self, *arg):
        return BaseSet(search_crit(self, arg))

    def __add__(self, other):
        return BaseSet(chain(self, other))

    @property
    def PLAIN(self):
        return BaseSet(chain(*self))

    class Tester(object):
        def __init__(self, data):
            self._data = data
        def __getattr__(self, attr):
            if attr.startswith("_"):
                raise AttributeError(attr)
            return attr in self._data
        def __call__(self, item):
            return item in self._data

    class TesterNot(object):
        def __init__(self, data):
            self._data = data
        def __getattr__(self, attr):
            if attr.startswith("_"):
                raise AttributeError(attr)
            return attr not in self._data
        def __call__(self, item):
            return item not in self._data

    @property
    def HAS(self):
        return BaseSet.Tester(self)

    @property
    def HASNOT(self):
        return BaseSet.TesterNot(self)

    def __cmp__(self, other):
        """Si lo comparo con un entero, el criterio es la longitud"""
        if isinstance(other, int):
            return cmp(len(self), other)
        return cmp(id(self), id(other))


class BaseList(tuple):

    # Tienen que ser todo clases globales, por pickle, y ademas
    # frozen, para que se puedan hashear

    def __pos__(self):
        assert(len(self) == 1)
        return self[0]

    def __call__(self, *arg):
        return BaseList(search_crit(self, arg))

    def __add__(self, other):
        return BaseList(chain(self, other))

    @property
    def HAS(self):
        return BaseSet.Tester(self)

    @property
    def HASNOT(self):
        return BaseSet.TesterNot(self)

    def __cmp__(self, other):
        """Si lo comparo con un entero, el criterio es la longitud"""
        if isinstance(other, int):
            return cmp(len(self), other)
        return cmp(id(self), id(other))


class Field(object):

    """
    Describe uno de los campos de un DataObject.

    Tiene los siguientes metodos:
        - collect: Agrupa una secuencia de objetos en una coleccion.
        - convert: Un Callable que lee el campo de un string.
        - dynamic: Un Callable que calcula el valor del campo.

    "dynamic" solo esta definido para los campos dinamicos. Se invoca
    pasandole como parametro el objeto, y devuelve el valor del campo.
    """

    def __init__(self, indexable=True):
        self.indexable = indexable

    def convert(self, data, notify):
        """Recibe un callback al que notificar las excepciones"""
        notify("Not Implemented")

    def dynamic(self, item, attr):
        raise AttributeError(attr)

    def collect(self, dset, attr):
        items = (item.get(attr) for item in dset._children)
        return BaseSet((x for x in items if x is not None))


class ObjectField(Field):

    """Campo que contiene un objeto"""

    def __init__(self, meta=None):
        super(ObjectField, self).__init__(indexable=False)
        self.meta = meta

    def _new(self, items=None, indexable=False):
        if self.meta:
            return DataSet(self.meta, items, indexable)
        return PeerSet(items)
        
    def collect(self, dset, attr):
        items = (item.get(attr) for item in dset._children)
        items = (item for item in items if item is not None)
        return self._new(items)


class DataSetField(Field):

    """Campo que contiene un DataSet"""

    def __init__(self, meta):
        super(DataSetField, self).__init__(indexable=False)
        self.meta = meta

    def _new(self, items=None, indexable=True):
        """Crea un DataSet nuevo"""
        if self.meta:
            return DataSet(self.meta, items, indexable)
        return PeerSet(items)

    def dynamic(self, item, attr):
        return self._new()

    def collect(self, dset, attr):
        items = (item.get(attr) for item in dset._children)
        items = tuple(item for item in items if item is not None)
        if len(items) == 1:
            # Devuelvo el propio DataSet, para aprovechar indices
            return items[0]
        return self._new(chain(*items), dset._indexable)


class Meta(object):

    """
    Encapsula los metadatos de un DataObject.

    Tiene los siguientes atributos:
        - up: Objeto Meta "padre" de este en la jerarquia.
        - fields: diccionario { atributo: Field() }
        - summary: tupla de atributos para describir un dataobject
    """
    def __init__(self, parent=None):
        # Creo "up", aunque el parent sea None, para permitir que "up"
        # funcione tambien en los PeerSets que se crean al definir enlaces,
        # que no tienen parent en cuanto al set, pero si individualmente.
        self.fields = { "up": ObjectField(parent) }
        self.up = parent
        self.summary = tuple()
        self._alias = dict()

    def create_alias(self, name, field):
        """Agrega un alias al campo seleccionado"""
        self._alias[name] = field

    def resolve_alias(self, alias):
        """Resuelve el nombre canonico de un alias"""
        canonical = self._alias.get(alias, None)
        if canonical is not None:
            return canonical
        # tambien aceptamos cualquier secuencia de letras que esten en
        # el mismo orden dentro del nombre del campo, y que sirvan para
        # identificarlo univocamente.
        regexp    = re.compile(".*".join(letter for letter in alias))
        matches   = tuple(x for x in self.fields.iterkeys() if regexp.match(x))
        canonical = matches[0] if len(matches) > 0 else alias
        return self._alias.setdefault(alias, canonical)

    def resolve_get(self, item, alias):
        """Resuelve el valor de un atributo"""
        canonical = self.resolve_alias(alias)
        if canonical != alias:
            return getattr(item, canonical)
        return self.fields[canonical].dynamic(item, canonical)

    def resolve_collect(self, items, alias):
        """Resuelve el valor de un atributo"""
        canonical = self.resolve_alias(alias)
        return self.fields[canonical].collect(items, canonical)


class DataObject(object):

    """
    Objeto contenedor de atributos
    """

    def __init__(self, meta, parent=None):
        self._meta = meta
        self.up = parent

    def __getattr__(self, attr):
        """Obtiene o crea el atributo.

        - Si el atributo es un alias, lo copia.
        - Si el atributo es dinamico, lo calcula.
        - Si es un DataSet, crea uno vacio al vuelo en caso de no existir.
        - En el resto de situaciones, lanza AttributeError.
        """
        if attr.startswith("_"):
            raise AttributeError(attr)
        try:
            value = self._meta.resolve_get(self, attr)
            return self.__dict__.setdefault(attr, value)
        except KeyError:
            raise AttributeError(attr)

    def get(self, attr, default=None):
        """Obtiene el atributo solo si es estatico y esta definido"""
        return self.__dict__.get(attr, default)

    class Tester(object):
        def __getattr__(self, attr):
            if attr.startswith("_"):
                raise AttributeError(attr)
            return attr in self._data
        def __call__(self, item):
            return attr in self._data
        def __init__(self, data, pos=True):
            self._data = data.__dict__

    class TesterNot(object):
        def __getattr__(self, attr):
            if attr.startswith("_"):
                raise AttributeError(attr)
            return attr not in self._data
        def __call__(self, item):
            return attr not in self._data
        def __init__(self, data, pos=True):
            self._data = data.__dict__

    @property
    def HAS(self):
        return DataObject.Tester(self)

    @property
    def HASNOT(self):
        return DataObject.TesterNot(self)

    @property
    def fb(self):
        return Fallback(self)

    def __str__(self):
        summary = (self.get(x) for x in self._meta.summary)
        return ", ".join(str(x) for x in summary if x is not None)

    def __repr__(self):
        return "<%s>" % str(self)

    def iteritems(self):
        """Itero sobre los elementos del objeto"""
        return (x for x in self.__dict__.iteritems()
            if x[1] is not None and not x[0].startswith("_"))

    def copy(self, new_meta=None, new_parent=None):
        """Para poder clonar objetos, hacer PEERs, etc"""
        new_meta   = new_meta or self._meta
        new_parent = new_parent or self.up
        obj = DataObject(new_meta)
        # cuidado con el update, que machaca tambien _meta y up
        obj.__dict__.update(self.__dict__)
        obj._meta, obj.up = new_meta, new_parent
        return obj

    def __len__(self):
        # Para que funcionen los operadores ANY, NONE
        return 1


class Fallback(dict):

    """
    Objeto Fallback.
    """

    def __init__(self, back, depth=sys.maxint):
        super(Fallback, self).__init__()
        # Para que "back" sea accesible desde los templates
        self['back'] = back
        # Utilizo self.__dict__ en lugar de poner el atributo directamente,
        # para no disparar setattr.
        self.__dict__['_back'] = back
        # Averiguo la profundidad real de la pila de objetos, para evitar que
        # luego me pueda dar un AttributeError o un IndexError volviendo
        # atras en la lista.
        maxdepth = 1
        try:
            while back.up:
                back = back.up
                maxdepth += 1
        except AttributeError:
            back.up = None
        self.__dict__['_depth'] = min(depth, maxdepth)

    def _get(self, attr, default=None):
        try:
            return self[attr]
        except KeyError:
            return default

    def get(self, attr, default=None):
        return self.get(attr, default)
    
    def __setattr__(self, attr, val):
        self[attr] = val

    def __getattr__(self, attr):
        if attr.startswith("_"):
            raise AttributeError(attr)
        try:
            return self[attr]
        except KeyError:
            raise AttributeError(attr)

    def __missing__(self, attr):
        back, depth = self._back, self._depth
        while back and depth:
            value = back.get(attr, None)
            if value is not None:
                return self.setdefault(attr, value)
            depth -= 1
            back = back.up
        raise KeyError(attr)

    @property
    def HAS(self):
        return DataObject.Tester(self)

    @property
    def HASNOT(self):
        return DataObject.TesterNot(self)

    def __str__(self):
        return str(self._back)


class Linear(object):

    """Realiza una busqueda lineal sobre un DataSet.

    Utilizo la funcion _get de los DataObjects porque se supone que
    ningun campo dinamico sera indexable.
    """

    def __init__(self, items, attr):
        self._items = items
        self._attr = attr

    def _eq(self, index):
        return tuple(x for x in self._items if x.get(self._attr) == index)

    def _ne(self, index):
        return tuple(x for x in self._items if x.get(self._attr) != index)

    def _none(self):
        return tuple(x for x in self._items if x.get(self._attr) is None)

    def _any(self):
        return tuple(x for x in self._items if x.get(self._attr) is not None)

    def _sorted(self, asc=True):
        def key(item):
            return item.get(self._attr)
        return tuple(sorted(self._items, key=key, reverse=(not asc)))

    def __len__(self):
        """La longitud del indice representa su granularidad.
        
        En este caso la longitud 0 porque es una busqueda lineal,
        sin ninguna granularidad. No particiona el DataSet en trozos.
        """
        return 0


class IndexItem(object):
    # Cosa curiosa... antes IndexItem era una clase derivada de
    # namedtuple, pero lo he tenido que cambiar porque no se estaba
    # llamando a __cmp__
    __slots__ = ("key", "item")
    def __init__(self, key, item):
        self.key = key
        self.item = item
    def __cmp__(self, other):
        return cmp(self.key, other.key)


class IndexKey(object):
    # Para poder comparar IndexItems con una clave solo, sin valor.
    __slots__ = ("key",)
    def __init__(self, key):
        self.key = key
    def __cmp__(self, other):
        return cmp(self.key, other.key)


class Index(object):

    """Mantiene un indice sobre una columna dada del DataSet.

    Utiliza la funcion _get porque se supone que ningun atributo dinamico
    sera indexable.
    """

    def __init__(self, items, attr):
        # Separo los objetos en dos grupos: los que tienen el
        # atributo, y los que no.
        values = tuple(x.get(attr) for x in items)
        self._empty = tuple(y for (x, y) in zip(values, items) if x is None)
        self._full  = tuple(sorted(IndexItem(x, y) for (x, y) in zip(values, items) if x is not None))
        self._cache = dict()

    def _margins(self, index):
        item  = IndexKey(index)
        first = bisect.bisect_left(self._full, item)
        last  = bisect.bisect_right(self._full, item, lo=first)
        return (first, last)

    def _eq(self, index):
        try:
            return self._cache[index]
        except KeyError:
            first, last = self._margins(index)
            result = tuple(x.item for x in self._full[first:last])
            return self._cache.setdefault(index, result)

    def _ne(self, index):
        first, last = self._margins(index)
        return tuple(x.item for x in chain(self._full[:first], self._full[last:]))

    def _none(self):
        return self._empty

    def _any(self):
        return tuple(x.item for x in self._full)

    def _sorted(self, asc=True):
        items = chain(self._empty, (x.item for x in self._full))
        if not asc:
            items = reversed(items)
        return tuple(items)

    def __len__(self):
        """La longitud del indice se usa para indicar su granularidad.

        En este caso, devolvemos la longitud del array "full", que indica
        en cuantos trozos particiona este indice al DataSet.
        """
        return len(self._full)


class DataSet(object):

    """
    Conjunto de objetos DataObject con un _meta comun.
    """

    class NONE(object):
        pass

    class ANY(object):
        pass

    # Increible... No se por que estupida razon, si heredo "DataSet" de
    # "set" o de "BaseSet", luego pickle no funciona: Ni siquiera llama
    # a "__getstate__" / "__setstate__" aunque lo defina.
    #
    # Por eso, he tenido que hacer esta CHAPUZA, que consiste en que
    # DataSet no deriva de un tipo "set", sino que lo encapsula. El
    # atributo "_children" contiene la lista de elementos del dataset,
    # y el objeto expone los metodos necesarios.

    def __init__(self, meta, children=None, indexable=True):
        self._meta = meta
        self._children = OrderedSet(children) if children is not None else OrderedSet()
        self._indexable = indexable

    def __getstate__(self):
        """No permito que se haga pickle de los indices"""
        return (self._meta, self._children)

    def __setstate__(self, state):
        """Restauro estado y borro indices"""
        self._meta = state[0]
        self._children = state[1]
        self._indexable = True

    def _new(self, meta, items=None, indexable=False):
        if meta:
            return DataSet(meta, items, indexable)
        return PeerSet(items)

    def __call__(self, *crit, **shortcut):
        # Mini-especializacion: es muy habitual buscar un objeto
        # en un dataset a partir de su indice, asi que especializo
        # el filtro: si hay parametros keyword-arg, se utiliza el indice
        # para hacer la busqueda:
        # - Valor == DataSet.NONE: se devuelven elementos sin el atributo.
        # - Valor == DataSet.ANY: se devuelven elementos con el atributo.
        # - Valor == cualquier otra cosa: se busca el valor.
        items = self._children
        if shortcut:
            aresolve = self._meta.resolve_alias
            shortcut = dict((aresolve(k), v) for (k, v) in shortcut.iteritems())
            key, index = self._best_index(frozenset(shortcut))
            if index:
                val = shortcut.pop(key)
                # Tres posibles casos: NONE, ANY y un indice a buscar
                if val is DataSet.NONE:
                    items = index._none()
                elif val is DataSet.ANY:
                    items = index._any()
                else:
                    items = index._eq(val)
        if crit or shortcut:
            items = search_crit(items, crit, shortcut)
        if len(items) == len(self._children):
            # si el resultado del filtro es el dataset entero,
            # devuelvo el propio dataset para aprovechar los indices.
            return self
        return self._new(self._meta, items, False)

    def __getattr__(self, attr):
        """Obtiene el atributo elegido, en funcion de su tipo"""
        if attr.startswith("_"):
            raise AttributeError(attr)
        try:
            value = self._meta.resolve_collect(self, attr)
            return self.__dict__.setdefault(attr, value)
        except KeyError:
            raise AttributeError(attr)

    def get(self, attr, defval=None):
        try:
            return getattr(self, attr)
        except AttributeError:
            return defval
        
    def _best_index(self, keys, dummy=tuple()):
        """Devuelve el atributo con el indice mas granular"""
        try:
            bestidx = self._bestidx[keys]
            index   = self._indexes[bestidx] if bestidx else None
            return (bestidx, index)
        except AttributeError:
            self._indexes = dict()
            self._bestidx = dict()
        except KeyError:
            pass
        def key(item, dummy=tuple()):
            """Los atributos se compararan por la longitud del indice"""
            return -len(self._indexes.get(item, dummy))
        valid   = (k for (k, v) in self._meta.fields.iteritems()
                     if v.indexable)
        bestidx = sorted(keys.intersection(valid), key=key) or None
        index   = None
        # Si alguno de los indices es valido, lo recupero.
        if bestidx:
            bestidx = bestidx[0]
            # Obtengo el indice antes de cachear la decision, porque
            # _index puede borrar el diccionario _bestidx si el indice
            # no existia.
            index = self._index(bestidx)
        # y cacheo la decision.
        self._bestidx[keys] = bestidx
        return (bestidx, index)

    def _index(self, attr):
        """Devuelve un indice sobre el campo indicado, si es indexable"""
        try:
            return self._indexes[attr]
        except AttributeError:
            self._indexes = dict()
            self._bestidx = dict()
        except KeyError:
            pass
        field = self._meta.fields[attr]
        if not field.indexable:
            # El field puede ser un DataSet o un BaseSet, que no se
            # pueden comparar con las funciones _eq y _ne de los indices
            # porque no se va a comparar igualdad, sino longitud.
            index = None
        else:
            if self._indexable:
                # Borro bestidx para que se vuelva a recalcular, ahora que
                # hay indices nuevos.
                self._bestidx = dict()
                indextype = Index
            else:
                indextype = Linear
            index = indextype(self._children, attr)
        return self._indexes.setdefault(attr, index)

    def __add__(self, other):
        # assert(self._meta == other._meta)
        # Si uno de los dos datasets esta vacio, devolvemos
        # el otro (en lugar de la suma) para poder aprovechar
        # los indices.
        if not other:
            return self
        if not self:
            return other
        # Si los dos tiene datos, devolvemos un dataset no indexable.
        meta = self._meta
        if meta != other.__dict__.get('_meta', None):
            meta = None
        return self._new(meta, self._children.union(other), False)

    def __pos__(self):
        assert(len(self._children) == 1)
        return tuple(self._children)[0]

    def __iter__(self):
        return iter(self._children)

    def __len__(self):
        return len(self._children)

    class Sorter(object):
        def __init__(self, dataset, asc=True):
            self._dataset = dataset
            self._asc = asc
        def __getattr__(self, attr):
            items = self._dataset._index(attr)._sorted(self._asc)
            value = DataSet(self._dataset._meta, items, False)
            return self.__dict__.setdefault(attr, value)
        def __call__(self, *fields, **kw):
            asc = kw.get("asc", True)
            def key(item):
                return tuple(item.get(f) for f in fields)
            items = tuple(sorted(self._dataset._children, key=key, reverse=(not asc)))
            return DataSet(self._dataset._meta, items, False)

    @property
    def SORTBY(self):
        return DataSet.Sorter(self, True)
        
    @property
    def SORTASC(self):
        return DataSet.Sorter(self, True)
        
    @property
    def SORTDESC(self):
        return DataSet.Sorter(self, False)

    def __cmp__(self, other):
        """Si lo comparo con un entero, el criterio es la longitud"""
        if isinstance(other, int):
            return cmp(len(self), other)
        return cmp(id(self), id(other))


class PeerSet(frozenset):

    """
    Conjunto de objetos DataObject sin metadatos comunes
    """

    def __call__(self, *arg, **kw):
        # Aqui no hay indices que valgan, se busca a pelo.
        return self._promote(search_crit(self, arg, kw))

    def __getattr__(self, attr):
        """Obtiene el atributo elegido, en funcion de su tipo"""
        # Esquivo los atributos "magicos" (empezando por "_") o aquellos
        # que pueden hacer que me confundan con un DataObject ("iteritems")
        if attr.startswith("_") or attr=="iteritems":
            raise AttributeError(attr)
        items = tuple(x for x in (y.get(attr) for y in self) if x is not None)
        if not items:
            # Si el resultado esta vacio no podemos decidir que hacer
            # con el... asumimos que se esperaba un DataSet o DataObject, que
            # sera lo mas habitual, y devolvemos un PeerSet.
            value = self._promote(items)
        elif isinstance(items[0], DataObject):
            # Asumo que todos los resultados son DataObjects,
            # y los encadeno.
            value = self._promote(items)
        elif isinstance(items[0], DataSet):
            # Asumo que todos los resultados son DataSets,
            # y los encadeno.
            value = self._promote(tuple(chain(*(x for x in items if x))))
        elif hasattr(items[0], '__iter__'):
            # Si son iterables, los encadeno.
            value = BaseSet(tuple(chain(*(x for x in items if x))))
        else:
            # En otro caso, los agrupo en un BaseSet.
            value = BaseSet(items)
        return self.__dict__.setdefault(attr, value)

    def _new(self, meta, items, indexable=False):
        if meta:
            return DataSet(meta, items, indexable)
        return PeerSet(items)

    def _promote(self, items):
        """Devuelve un PeerSet o un DataSet, en funcion de 'items'."""
        meta = set(x._meta for x in items)
        meta = meta.pop() if len(meta) == 1 else None
        return self._new(meta, items, False)

    def __add__(self, other):
        return self._promote(tuple(chain(self, other)))
    
    def __pos__(self):
        assert(len(self) == 1)
        return tuple(self)[0]

    def _index(self, attr):
        """Siempre devuelve un indice lineal, lo pongo para poder ordenar"""
        return Linear(self, attr)

    @property
    def SORTBY(self):
        return DataSet.Sorter(self, True)
        
    @property
    def SORTASC(self):
        return DataSet.Sorter(self, True)
        
    @property
    def SORTDESC(self):
        return DataSet.Sorter(self, False)

    def __cmp__(self, other):
        """Si lo comparo con un entero, el criterio es la longitud"""
        if isinstance(other, int):
            return cmp(len(self), other)
        return cmp(id(self), id(other))


if __name__ == "__main__":

    import unittest
    import operator
    import sys
    try:
        import cPickle as pickle
    except ImportError:
        import pickle

    class TestData(unittest.TestCase):

        def setUp(self):
            self.m1 = Meta("data")
            self.m1.fields = {
                    'x': Field(),
                    'y': Field(),
                }
            self.m2 = self.m1.child("subfield")
            self.m2.fields = {
                    'a': Field(),
                    'b': Field(),
                }

            self.d1 = DataObject(self.m1, None)
            self.d2 = DataObject(self.m2, self.d1)

        #def testMetaPath(self):
        #    self.failUnless(self.m1.path == "data")
        #    self.failUnless(self.m2.path == "data.subfield")

        def testMetaUp(self):
            self.failUnless(self.m1.up is None)
            self.failUnless(self.m2.up is self.m1)

        def testDataAttrib(self):
            """Acceso a una variable valida"""
            self.assertRaises(AttributeError, getattr, self.d1, "x")
            self.failUnless(type(self.d1.subfield) is DataSet)
            self.failUnless(len(self.d1.subfield) == 0)

        def testDataDynamic(self):
            """Acceso a una variable valida"""
            class Decrementor(Field):
                def dynamic(self, attr, item):
                    return item.x - 1
            self.m1.fields['y'] = Decrementor()
            self.d1.x = 10
            self.failUnless(self.d1.y == 9)

        def testDataUp(self):
            """Acceso al atributo up"""
            self.failUnless(self.d1.up is None)
            self.failUnless(self.d2.up is self.d1)

        def testDataHas(self):
            """Propiedad 'has'."""
            self.d1.x = 10
            self.failUnless(self.d1.HAS.x)
            self.failIf(self.d1.HAS.y)
            
        def testDataHasNot(self):
            """Propiedad 'hasnot'."""
            self.d1.x = 10
            self.failUnless(self.d1.HASNOT.y)
            self.failIf(self.d1.HASNOT.x)
            
        def testDataGet(self):
            """Funcion get"""
            self.d1.x = -5
            self.failUnless(self.d1.get("x") == -5)
            self.failUnless(self.d1.get("y", "testpassed") == "testpassed")
            self.failUnless(type(self.d1.get("subfield")) == DataSet)
    
        def testData_Get(self):
            """Funcion _get"""
            self.d1.x = -8
            self.failUnless(self.d1.get("x") == -8)
            self.failUnless(self.d1.get("y", "testpassed") == "testpassed")
            self.failUnless(self.d1.get("subfield") is None)

    class TestPickledData(TestData):

        def setUp(self):
            super(TestPickledData, self).setUp()
            self.d2 = pickle.loads(pickle.dumps(self.d2))
            self.d1 = self.d2.up
            self.m2 = self.d2._meta
            self.m1 = self.m2.up

    class TestFallback(unittest.TestCase):

        def setUp(self):
            self.m1 = Meta("data")
            self.m1.fields = {
                    'a': Field(),
                    'b': Field(),
                    'c': Field(),
                }
            self.m2 = self.m1.child("subfield")
            self.m2.fields = {
                    'a': Field(),
                    'b': Field(),
                    'd': Field(),
                }

            self.d1 = DataObject(self.m1, None)
            self.d2 = DataObject(self.m2, self.d1).fb

        def testDataAttrib(self):
            """Acceso a una variable valida"""
            self.assertRaises(AttributeError, getattr, self.d2, "a")
            self.d1.b = 5
            self.failUnless(self.d2.b == 5)

        def testDataDynamic(self):
            """Acceso a una variable valida"""
            class Decrementor(Field):
                def dynamic(self, attr, item):
                    return item.a - 1
            self.m1.fields['b'] = Decrementor()
            self.d1.a = 10
            self.failUnless(self.d2.b == 9)

        def testDataUp(self):
            """Acceso al atributo up"""
            self.failUnless(self.d2.up is self.d1)

        def testDataHas(self):
            """Propiedad 'has'."""
            self.d2.a = 10
            self.d1.b = 12
            self.failUnless(self.d2.HAS.a)
            self.failUnless(self.d2.HAS.b)
            self.failIf(self.d2.HAS.y)

        def testDataHasNot(self):
            """Propiedad 'hasnot'."""
            self.d2.a = 10
            self.d1.b = 12
            self.failIf(self.d2.HASNOT.a)
            self.failIf(self.d2.HASNOT.b)
            self.failUnless(self.d2.HASNOT.x)

        def testDataGet(self):
            """Funcion get"""
            self.d1.a = -10
            self.d2.b = -5
            self.failUnless(self.d2.get("a") == -10)
            self.failUnless(self.d2.get("b") == -5)
            self.failUnless(self.d2.get("x", "testpassed") == "testpassed")
            self.failUnless(type(self.d2.get("subfield")) == DataSet)

        def testData_Get(self):
            """Funcion _get"""
            self.d1.a = -9
            self.d2.b = -4
            self.failUnless(self.d2.get("a") == -9)
            self.failUnless(self.d2.get("b") == -4)
            self.failUnless(self.d2.get("x", "testpassed") == "testpassed")
            self.failUnless(type(self.d2.get("subfield")) == DataSet)

    class TestDataSet(unittest.TestCase):

        def setUp(self):
            self.m1 = Meta("data")
            self.m1.fields = {
                    'x': Field(),
                    'y': Field(),
                    'z': Field(),
                }
            self.m2 = self.m1.child("subfield")
            self.m2.fields = {
                    'a': Field(),
                    'b': Field(),
                    'c': Field(indexable=False),
                }

            self.d1 = DataObject(self.m1, None)
            self.d2 = DataObject(self.m1, None)
            d3 = DataObject(self.m2, self.d1)
            d4 = DataObject(self.m2, self.d1)
            d5 = DataObject(self.m2, self.d1)
            d6 = DataObject(self.m2, self.d2)
            d7 = DataObject(self.m2, self.d2)
            d8 = DataObject(self.m2, self.d2)
            empty1 = DataObject(self.m2, self.d1) 
            empty2 = DataObject(self.m2, self.d1) 
            self.d1.subfield = DataSet(self.m2, (d3, d4, d5, empty1, empty2))
            self.d2.subfield = DataSet(self.m2, (d6, d7, d8))
            self.all = DataSet(self.m1, (self.d1, self.d2))
            d3.a, d4.a, d5.a = 3, 4, 5
            d3.b, d4.b, d5.b = "aabb", "ccdd", "eeff"
            empty1.a = 6
            empty2.b = "gghh"
            d3.c, d4.c, d5.c = BaseSet((1,2)), BaseSet((2,3)), BaseSet((3,4))
            d6.a, d7.a, d8.a = 6, 7, 8
            d6.b, d7.b, d8.b = "gghh", "iijj", "kkll"

        def testIndexable(self):
            self.failIf(self.d1.subfield.INDEX.a is None)
            self.failIf(self.d1.subfield.INDEX.b is None)
            self.failUnless(self.d1.subfield.INDEX.c is None)

        def testIndexMissing(self):
            indexA = self.d1.subfield.INDEX.a
            indexB = self.d1.subfield.INDEX.b
            self.failUnless(len(indexA._eq(-100)) == 0)
            self.failUnless(len(indexB._eq("ghij")) == 0)

        def testIndexEq(self):
            indexA = self.d1.subfield.INDEX.a
            indexB = self.d1.subfield.INDEX.b
            self.failUnless(indexA._eq(4)[0].a == 4)
            self.failUnless(indexB._eq("eeff")[0].b == "eeff")

        def testIndexNe(self):
            indexA = self.d1.subfield.INDEX.a
            indexB = self.d1.subfield.INDEX.b
            self.failUnless(set(x.a for x in indexA._ne(4)) == set((3,5,6)))
            self.failUnless(set(x.b for x in indexB._ne("eeff")) == set(("aabb", "ccdd", "gghh")))

        def testIndexNone(self):
            indexA = self.d1.subfield.INDEX.a
            indexB = self.d1.subfield.INDEX.b
            self.failUnless(indexA._none()[0].b == "gghh")
            self.failUnless(indexB._none()[0].a == 6)

        def testIndexAny(self):
            indexA = self.d1.subfield.INDEX.a
            indexB = self.d1.subfield.INDEX.b
            self.failUnless(set(x.a for x in indexA._any()) == set((3,4,5,6)))
            self.failUnless(set(x.b for x in indexB._any()) == set(("aabb", "ccdd", "eeff", "gghh")))
            
        def testFilter(self):
            expected = {"ccdd":0, "eeff":0}
            for item in self.d1.subfield(lambda x: x.a >= 4):
                if item.HAS.b:
                    self.failUnless(item.b in expected )
                    del(expected[item.b])

        def testEmptyFilter(self):
            items = self.d1.subfield(lambda x: x.a < 0)
            self.failUnless(len(items) == 0)

        def testCombinedFilter(self):
            items = self.d1.subfield(lambda x: (x.a > 0) and ("bb" in x.b))
            self.failUnless(len(items) == 1)
            self.failUnless(+(items.a) == 3)

        def testAttrib(self):
            items = self.d1.subfield.a
            self.failUnless(items == set((3, 4, 5, 6)))

        def testSubtypeAttrib(self):
            items = self.all.subfield
            self.failUnless(len(items) == 8)

        def testUp(self):
            first = self.d1.subfield.up
            self.failUnless(len(first) == 1)
            self.failUnless(+first is self.d1)

        def testBothUp(self):
            both = self.all.subfield.up
            self.failUnless(len(both) == 2)
            self.failUnless(self.d1 in both)
            self.failUnless(self.d2 in both)

        def testPos(self):
            first = +(self.d1.subfield(lambda x: x.a==3))
            self.failUnless(first.b == "aabb")

        def testInvalidPos(self):
            self.assertRaises(AssertionError, operator.pos, self.d1.subfield(lambda x: x.a>=3))
            self.assertRaises(AssertionError, operator.pos, self.d2.subfield(lambda x: x.a<=3))

        def testSortBy(self):
            result = tuple(x.b for x in self.d1.subfield.SORTBY.b if x.HAS.b)
            self.failUnless(result == ("aabb", "ccdd", "eeff", "gghh"))

        def testSortAsc(self):
            result = tuple(x.b for x in self.d1.subfield.SORTASC.b if x.HAS.b)
            self.failUnless(result == ("aabb", "ccdd", "eeff", "gghh"))

        def testSortDesc(self):
            result = reversed(tuple(x.b for x in self.d1.subfield.SORTDESC.b if x.HAS.b))
            self.failUnless(tuple(result) == ("aabb", "ccdd", "eeff", "gghh"))

        def testBaseSetPlain(self):
            """Me aseguro de que los BaseSets se 'picklean' bien"""
            plain = frozenset(self.d1.subfield.c.PLAIN)
            self.failUnless(plain == frozenset((1, 2, 3, 4)))

    class TestPickledDataSet(TestDataSet):

        def setUp(self):
            super(TestPickledDataSet, self).setUp()
            # Me aseguro de que los indices no se picklean
            matchesA = self.d1.subfield.INDEX.a
            self.failUnless(self.d1.subfield._indexes)
            pickled = pickle.loads(pickle.dumps({'all': self.all, 'd1': self.d1, 'd2': self.d2}))
            self.all = pickled['all']
            self.d1 = pickled['d1']
            self.d2 = pickled['d2']
            self.m1 = self.d1._meta
            self.m2 = self.d2._meta
            self.failIf(self.d1.subfield._indexes)

        def testPickledBaseSet(self):
            """Me aseguro de que los BaseSets se 'picklean' bien"""
            sets = frozenset(frozenset(x) for x in self.d1.subfield.c)
            self.failUnless(len(sets) == 3)
            self.failUnless(all(len(x) == 2 for x in sets))
            self.failUnless(frozenset((1, 2)) in sets)
            self.failUnless(frozenset((2, 3)) in sets)
            self.failUnless(frozenset((3, 4)) in sets)

    unittest.main()
