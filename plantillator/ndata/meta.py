#/usr/bin/env python


import bisect
import sys
import traceback
from itertools import chain

from resolver import Resolver


# Simbolos para el resolver
SYMBOL_SELF   = 1
SYMBOL_FOLLOW = 2


class DataException(Exception):

    """
    Encapsula las excepciones lanzadas durante el analisis de una fuente
    de datos.

    - self.source: identificador de la fuente de datos que se analiza.
    - self.index: indice (n. de linea, generalmente) del registro erroneo.
    - self.exc_info: tupla (tipo, excepcion, traceback)
    """

    def __init__(self, source, index, exc_info):
        super(DataException, self).__init__()
        self.source = source
        self.index = index
        self.exc_info = exc_info

    def __unicode__(self):
        return u"".join(chain(
            (u"DataException: Error en %s [%s]\n" % (unicode(self.source), unicode(self.index)),),
            traceback.format_exception(*(self.exc_info))
            ))

    def __str__(self):
        return str(unicode(self))

    def __repr__(self):
        return "DataException(%s[%s], %s)" % (repr(self.source), repr(self.index), repr(self.exc_info))


def matches(item, crit):
    """Comprueba si un objeto cumple un criterio.

    Si la evaluacion del criterio lanza una exception durante la
    resolucion, se considera que el criterio no se cumple.
    """
    try:
        return all(c._resolve({SYMBOL_SELF: item}) for c in crit)
    except (AttributeError, AssertionError):
        return False


class BaseSet(frozenset):
    # Tienen que ser todo clases globales, por pickle, y ademas
    # frozen, para que se puedan hashear.
    def __pos__(self):
        assert(len(self) == 1)
        return tuple(self)[0]
    def __call__(self, *arg):
        return BaseSet(x for x in self if matches(x, arg))
    def __add__(self, other):
        return BaseSet(chain(self, other))
    @property
    def PLAIN(self):
        return BaseSet(chain(*self))


class BaseList(tuple):
    # Tienen que ser todo clases globales, por pickle, y ademas
    # frozen, para que se puedan hashear
    def __pos__(self):
        assert(len(self) == 1)
        return self[0]
    def __call__(self, *arg):
        return BaseList(x for x in self if matches(x, arg))
    def __add__(self, other):
        return BaseList(chain(self, other))


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

    def convert(self, data):
        return data

    def dynamic(self, attr, item):
        raise AttributeError(attr)

    def collect(self, items):
        return BaseSet(items)


class Meta(object):

    """
    Encapsula los metadatos de un DataObject.

    Tiene los siguientes atributos:
        - up: Objeto Meta "padre" de este en la jerarquia.
        - path: ID completo del objeto Meta. Es una cadena separada por ".".
        - fields: diccionario { atributo: Field() }
        - subtypes: diccionario { atributo: Meta() }
        - summary: tupla de atributos para describir un dataobject
    """
    def __init__(self, path, parent=None, fields=None, subtypes=None):
        self.fields = fields if fields is not None else dict()
        self.subtypes = subtypes if subtypes is not None else dict()
        self.path = path
        self.up = parent
        self.summary = tuple()

    def child(self, name):
        """Devuelve un tipo hijo, creandolo si es necesario"""
        try:
            return self.subtypes[name]
        except KeyError:
            return self.subtypes.setdefault(name, Meta(".".join((self.path, name)), self))

    @property
    def valid(self):
        """Devuelve los nombres de todos los atributos validos"""
        return chain(self.fields.keys(), self.subtypes.keys())


class DataObject(object):

    """
    Objeto contenedor de atributos
    """

    def __init__(self, meta, parent=None):
        self._meta = meta
        self.up = parent

    def __getattr__(self, attr):
        """Obtiene o crea el atributo.

        - Si el atributo es dinamico, lo calcula.
        - Si es un DataSet, crea uno vacio al vuelo en caso de no existir.
        - En el resto de situaciones, lanza AttributeError.
        """
        if attr.startswith("_"):
            raise AttributeError(attr)
        subtype = self._meta.subtypes.get(attr, None)
        if not subtype:
            field = self._meta.fields.get(attr, None)
            if not field:
                raise AttributeError(attr)
            return field.dynamic(attr, self)
        return self.__dict__.setdefault(attr, DataSet(subtype))

    def get(self, attr, default=None):
        """Obtiene el atributo o lo genera si es dinamico o subtipo"""
        try:
            return getattr(self, attr)
        except AttributeError:
            return default

    def _get(self, attr, default=None):
        """Obtiene el atributo solo si es estatico y esta definido"""
        return self.__dict__.get(attr, default)

    class Tester(object):
        def __getattr__(self, attr):
            if attr.startswith("_"):
                raise AttributeError(attr)
            return self._data._get(attr) is not None
        def __init__(self, data, pos=True):
            self._data = data

    class TesterNot(object):
        def __getattr__(self, attr):
            if attr.startswith("_"):
                raise AttributeError(attr)
            return self._data._get(attr) is None
        def __init__(self, data, pos=True):
            self._data = data

    @property
    def HAS(self):
        return DataObject.Tester(self)

    @property
    def HASNOT(self):
        return DataObject.TesterNot(self)

    @property
    def fb(self):
        return Fallback(self)

    def __unicode__(self):
        summary = (self._get(x) for x in self._meta.summary)
        return u", ".join(unicode(x) for x in summary if x is not None)

    def __repr__(self):
        return u"<%s>" % unicode(self)

    def iteritems(self):
        """Itero sobre los elementos del objeto"""
        # Los campos los recupero con "get", para que calcule los dinamicos
        fields = ((k, self.get(k)) for k in self._meta.fields)
        # Los subtipos los recupero con "_get", para ir solo a los definidos
        stypes = ((k, self._get(k)) for k in self._meta.subtypes)
        # incluyo "up" si no es None
        valid = chain((("up", self.up),), fields, stypes)
        return (pack for pack in valid if pack[1] is not None)


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
        self.__dict__['_depth'] = depth

    def _get(self, attr, default=None):
        try:
            return self[attr]
        except KeyError:
            return default

    def get(self, attr, default=None):
        return self._get(attr, default)
    
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
            value = back.get(attr)
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

    def __unicode__(self):
        return unicode(self._back)


class Linear(object):

    """Realiza una busqueda lineal sobre un DataSet"""

    def __init__(self, items, attr):
        self._items = items
        self._attr = attr

    def __eq__(self, index):
        return tuple(x for x in self._items if x.get(self._attr) == index)

    def __ne__(self, index):
        return tuple(x for x in self._items if x.get(self._attr) != index)

    def _none(self):
        return tuple(x for x in self._items if x.get(self._attr) is None)

    def _any(self):
        return tuple(x for x in self._items if x.get(self._attr) is not None)

    def _sorted(self, asc=True):
        def key(item):
            return item.get(self._attr)
        return tuple(sorted(self._items, key=key, reverse=(not asc)))


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

    """Mantiene un indice sobre una columna dada del DataSet"""

    def __init__(self, items, attr):
        # Separo los objetos en dos grupos: los que tienen el
        # atributo, y los que no.
        values = tuple(x.get(attr) for x in items)
        self._empty = tuple(y for (x, y) in zip(values, items) if x is None)
        self._full  = tuple(sorted(IndexItem(x, y) for (x, y) in zip(values, items) if x is not None))

    def _margins(self, index):
        item  = IndexKey(index)
        first = bisect.bisect_left(self._full, item)
        last  = bisect.bisect_right(self._full, item, lo=first)
        return (first, last)

    def _eq(self, index):
        first, last = self._margins(index)
        return tuple(x.item for x in self._full[first:last])

    def _ne(self, index):
        first, last = self._margins(index)
        return tuple(x.item for x in chain(self._full[:first], self._full[last:]))

    def _none(self):
        return self._empty

    def _any(self):
        return tuple(x.item for x in self._full)

    def _sorted(self, asc=True):
        if asc:
            items = chain(self._empty, (x.item for x in self._full))
        else:
            items = chain((x.item for x in reversed(self._full)), self._empty)
        return tuple(items)


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
        self._children = set(children) if children is not None else set()
        self._indexes = dict()
        self._indexable = indexable

    def __getstate__(self):
        """No permito que se haga pickle de los indices"""
        return (self._meta, self._children)

    def __setstate__(self, state):
        """Restauro estado y borro indices"""
        self._meta = state[0]
        self._children = state[1]
        self._indexes = dict()
        self._indexable = True

    def __call__(self, *crit, **shortcut):
        # Mini-especializacion: es muy habitual buscar un objeto
        # en un dataset a partir de su indice, asi que especializo
        # el filtro: si el unico parametro es un keyword-arg, se
        # utiliza el indice para hacer la busqueda:
        # - Valor == DataSet.NONE: se devuelven elementos sin el atributo.
        # - Valor == DataSet.ANY: se devuelven elementos con el atributo.
        # - Valor == cualquier otra cosa: se busca el valor.
        if shortcut:
            # Solo admitimos un unico criterio, y ademas debe ser sobre
            # un campo indexable.
            key, val = shortcut.popitem()
            index = self._index(key)
            assert(index and not crit and not shortcut)
            # Tres posibles casos: NONE, ANY y un indice a buscar
            if val is DataSet.NONE:
                items = index._none()
            elif val is DataSet.ANY:
                items = index._any()
            else:
                items = index._eq(val)
        else:
            # Para los indices compuestos, vamos al caso general.
            items = tuple(x for x in self._children if matches(x, crit))
        if len(items) == len(self._children):
            # si el resultado del filtro es el dataset entero,
            # devuelvo el propio dataset para aprovechar los indices.
            return self
        return DataSet(self._meta, items, False)

    def __getattr__(self, attr):
        """Obtiene el atributo elegido, en funcion de su tipo:

        - up: devuelve un DataSet con todos los atributos "up"
              de todos los elementos del set.
        - subtipo: devuelve un DataSet con la concatenacion de
                   todas las sublistas de los elementos del set.
        - otro atributo: Devuelve un BaseSet con todos los
                        valores del atributo en todos los elementos
                        del set.
        """
        if attr.startswith("_"):
            raise AttributeError(attr)
        if attr == "up":
            # "up" lo pongo como un atributo dinamico y no como una
            # propiedad para que solo tenga que ser calculado una vez,
            # la primera vez que se utiliza (lyego se almacena como
            # atributo normal y no llega a llamarse a __getattr__)
            supertype = self._meta.up
            if supertype is None:
                value = None
            else:
                items = (up for up in (x.up for x in self._children) if up is not None)
                value = DataSet(supertype, items, self._indexable)
        else:
            subtype = self._meta.subtypes.get(attr, None)
            if subtype is not None:
                items = tuple(x for x in (y._get(attr) for y in self._children) if x is not None)
                # si el resultado es un unico DataSet, lo devuelvo
                # directamente, y asi puedo reutilizar el indice.
                # si son varios DataSets, lo que devuelvo es un agregado
                # efimero que solo tiene sentido indexar si este objeto
                # a su vez no es efimero.
                if len(items) == 1:
                    value = items[0]
                else:
                    value = DataSet(subtype, chain(*items), self._indexable)
            else:
                field = self._meta.fields.get(attr, None)
                if field is not None:
                    items = (x for x in (y.get(attr) for y in self._children) if x is not None)
                    value = field.collect(items)
                else:
                    raise AttributeError(attr)
        setattr(self, attr, value)
        return value

    def _index(self, attr):
        """Devuelve un indice sobre el campo indicado, si es indexable"""
        try:
            return self._indexes[attr]
        except KeyError:
            field = self._meta.fields.get(attr, None)
            if not field or not field.indexable:
                index = None
            else:
                indextype = Index if self._indexable else Linear
                index = indextype(self._children, attr)
            return self._indexes.setdefault(attr, index)

    class Indexer(object):
        def __init__(self, dataset):
            self._dataset = dataset
        def __getattr__(self, attr):
            return self.__dict__.setdefault(attr, self._dataset._index(attr))

    @property
    def INDEX(self):
        return DataSet.Indexer(self)

    def __add__(self, other):
        assert(self._meta == other._meta)
        if not hasattr(other, '__iter__'):
            other = (other,)
        return DataSet(self._meta, self._children.union(other))

    def __pos__(self):
        assert(len(self._children) == 1)
        return tuple(self._children)[0]

    def __iter__(self):
        return iter(self._children)

    def __len__(self):
        return len(self._children)

    def update(self, items):
        assert(not self._indexes)
        self._children.update(items)

    def add(self, item):
        assert(not self._indexes)
        self._children.add(item)

    def pop(self):
        assert(not self._indexes)
        item = self._children.pop()

    class Sorter(object):
        def __init__(self, dataset, asc=True):
            self._dataset = dataset
            self._asc = asc
        def __getattr__(self, attr):
            value = self._dataset._index(attr)._sorted(self._asc)
            return self.__dict__.setdefault(attr, value)

    @property
    def SORTBY(self):
        return DataSet.Sorter(self, True)
        
    @property
    def SORTASC(self):
        return DataSet.Sorter(self, True)
        
    @property
    def SORTDESC(self):
        return DataSet.Sorter(self, False)


class PeerSet(frozenset):

    """
    Conjunto de objetos DataObject sin metadatos comunes
    """

    def __call__(self, *crit, **shortcut):
        # Acepta la misma mini-especializacion que un DataSet, aunque
        # la generaliza.
        if shortcut:
            key, val = shortcut.popitem()
            assert(not crit and not shortcut)
            # Tres posibles casos: NONE, ANY y un indice a buscar
            crit = Resolver(SYMBOL_SELF)
            if val is DataSet.NONE:
                crit = getattr(crit, "HASNOT")
                crit = getattr(crit, key)
            elif val is DataSet.ANY:
                crit = getattr(crit, "HAS")
                crit = getattr(crit, key)
            else:
                crit = getattr(crit, key)
                crit = (crit == val)
            crit = (crit,)
        return PeerSet(x for x in self if matches(x, crit))

    def __getattr__(self, attr):
        """Obtiene el atributo elegido, en funcion de su tipo:

        - up: devuelve un DataSet con todos los atributos "up"
              de todos los elementos del set.
        - subtipo: devuelve un DataSet con la concatenacion de
                   todas las sublistas de los elementos del set.
        - otro atributo: Devuelve un BaseSet con todos los
                        valores del atributo en todos los elementos
                        del set.
        """
        # Esquivo los atributos "magicos" (empezando por "_") o aquellos
        # que pueden hacer que me confundan con un DataObject ("iteritems")
        if attr.startswith("_") or attr=="iteritems":
            raise AttributeError(attr)
        if attr == "up":
            # "up" lo pongo como un atributo dinamico y no como una
            # propiedad para que solo tenga que ser calculado una vez,
            # la primera vez que se utiliza (luego se almacena como
            # atributo normal y no llega a llamarse a __getattr__)
            value = PeerSet(up for up in (x.up for x in self) if up is not None)
        else:
            items = tuple(x for x in (y.get(attr) for y in self) if x is not None)
            if not items:
                # El resultado esta vacio, no podemos decidir que hacer
                # con el... lanzamos AttributeError
                raise AttributeError(attr)
            if isinstance(items[0], DataSet):
                # Asumo que todos los resultados son DataSets,
                # y los encadeno.
                value = PeerSet(chain(*(x for x in items if x)))
            elif isinstance(items[0], DataObject):
                # Asumo que todos los resultados son DataObjects,
                # y los encadeno.
                value = PeerSet(items)
            else:
                # En otro caso, los agrupo en un BaseSet.
                value = BaseSet(items)
        setattr(self, attr, value)
        return value

    def __add__(self, other):
        return PeerSet(chain(self, other))
    
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


if __name__ == "__main__":

    import unittest
    import resolver
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

        def testMetaPath(self):
            self.failUnless(self.m1.path == "data")
            self.failUnless(self.m2.path == "data.subfield")

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
            self.failUnless(self.d1._get("x") == -8)
            self.failUnless(self.d1._get("y", "testpassed") == "testpassed")
            self.failUnless(self.d1._get("subfield") is None)

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
            self.failUnless(self.d2._get("a") == -9)
            self.failUnless(self.d2._get("b") == -4)
            self.failUnless(self.d2._get("x", "testpassed") == "testpassed")
            self.failUnless(type(self.d2._get("subfield")) == DataSet)

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
            x = resolver.Resolver(SYMBOL_SELF)
            expected = {"ccdd":0, "eeff":0}
            for item in self.d1.subfield(x.a >= 4):
                if item.HAS.b:
                    self.failUnless(item.b in expected )
                    del(expected[item.b])

        def testEmptyFilter(self):
            x = resolver.Resolver(SYMBOL_SELF)
            items = self.d1.subfield(x.a < 0)
            self.failUnless(len(items) == 0)

        def testCombinedFilter(self):
            x = resolver.Resolver(SYMBOL_SELF)
            items = self.d1.subfield(x.a > 0, x.b.MATCH("bb"))
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
            x = resolver.Resolver(SYMBOL_SELF)
            first = +(self.d1.subfield(x.a==3))
            self.failUnless(first.b == "aabb")

        def testInvalidPos(self):
            x = resolver.Resolver(SYMBOL_SELF)
            self.assertRaises(AssertionError, operator.pos, self.d1.subfield(x.a>=3))
            self.assertRaises(AssertionError, operator.pos, self.d2.subfield(x.a<=3))

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
