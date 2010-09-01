#/usr/bin/env python


import bisect
from itertools import chain


class Field(object):

    """
    Describe uno de los campos de un DataObject.

    Tiene los siguientes atributos:
        - defindex: Si el campo es indexable, es el valor por defecto
            que hay que darle al indice si un objeto no tiene el campo.
            Si el campo no es indexable, es None.
            Solo se pueden indexar campos que no sean dinamicos.

    Y los siguientes metodos
        - convert: Un Callable que lee el campo de un string.
        - dynamic: Un Callable que calcula el valor del campo.

    "dynamic" solo esta definido para los campos dinamicos. Se invoca
    pasandole como parametro el objeto, y devuelve el valor del campo.
    """
    
    def __init__(self, defindex=None):
        self.defindex = defindex

    def convert(self, data):
        return data

    def dynamic(self, attr, item):
        raise AttributeError(attr)


class Meta(object):

    """
    Encapsula los metadatos de un DataObject.

    Tiene los siguientes atributos:
        - up: Objeto Meta "padre" de ste en la jerarquia.
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


class DataObject(object):

    """
    Objeto contenedor de atributos
    """

    def __init__(self, meta, parent=None):
        self._meta = meta
        self.up = parent

    def __contains__(self, attr):
        return attr in self.__dict__

    def __getattr__(self, attr):
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
        try:
            return getattr(self, attr)
        except AttributeError:
            return default

    def _get(self, attr, default = None):
        try:
            return self.__dict__[attr]
        except KeyError:
            return default

    class Tester(object):
        def __init__(self, data):
            self._data = data
        def __getattr__(self, attr):
            if attr.startswith("_"):
                raise AttributeError(attr)
            return attr in self._data

    @property
    def HAS(self):
        return DataObject.Tester(self)

    def __unicode__(self):
        summary = (self._get(x) for x in self._meta.summary)
        return u", ".join(unicode(x) for x in summary if x is not None)


def _matches(item, crit):
    """Comprueba si un objeto cumple un criterio.

    Si la evaluacion del criterio lanza una exception durante la
    resolucion, se considera que el criterio no se cumple.
    """
    try:
        return all(c._resolve({'self': item}) for c in crit)
    except (AttributeError, AssertionError):
        return False


class BaseSet(frozenset):
    # Tienen que ser todo clases globales, por pickle, y ademas
    # frozen, para que se puedan hashear.
    def __pos__(self):
        assert(len(self) == 1)
        return tuple(self)[0]
    def __call__(self, *arg):
        return BaseSet(x for x in self if _matches(x, arg))
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
        return BaseList(x for x in self if _matches(x, arg))
    def __add__(self, other):
        return BaseList(chain(self, other))


class IndexItem(object):
    # Cosa curiosa... antes IndexItem era una clase derivada de
    # namedtuple, pero lo he tenido que cambiar porque no se estaba
    # llamando a __cmp__
    __slots__ = ("key", "item")
    def __init__(self, item, attr, defindex):
        self.key = item._get(attr, defindex)
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

    def __init__(self, meta, attr, defindex, items=None):
        self.meta = meta
        self.items = list(sorted(IndexItem(x, attr, defindex) for x in items)) if items else list()
        self.attr = attr
        self.defindex = defindex

    def _margins(self, index):
        item  = IndexKey(index)
        first = bisect.bisect_left(self.items, item)
        last  = bisect.bisect_right(self.items, item)
        return (first, last)

    def pop(self, item):
        index = item._get(self.attr, self.defindex)
        first, last = self._margins(index)
        while first < last:
            if self.items[first].item is item:
                del(self.items[first])
                return
            first += 1

    def append(self, item):
        bisect.insort(self.items, IndexItem(item, self.attr, self.defindex))

    def extend(self, items):
        for item in items:
            self.append(item)

    def __eq__(self, index):
        first, last = self._margins(index)
        return DataSet(self.meta, (x.item for x in self.items[first:last]))

    def __ne__(self, index):
        first, last = self._margins(index)
        return DataSet(self.meta, (x.item for x in chain(self.items[:first], self.items[last:])))

    def __lt__(self, index):
        first = bisect.bisect_left(self.items, IndexKey(index))
        return DataSet(self.meta, (x.item for x in self.items[:first]))

    def __le__(self, index):
        last = bisect.bisect_right(self.items, IndexKey(index))
        return DataSet(self.meta, (x.item for x in self.items[:last]))

    def __ge__(self, index):
        first = bisect.bisect_left(self.items, IndexKey(index))
        return DataSet(self.meta, (x.item for x in self.items[first:]))

    def __gt__(self, index):
        last = bisect.bisect_right(self.items, IndexKey(index))
        return DataSet(self.meta, (x.item for x in self.items[last:]))


class DataSet(object):

    """
    Conjunto de objetos DataObject con un _meta comun.
    """

    # Increible... No se por que estupida razon, si heredo "DataSet" de
    # "set" o de "BaseSet", luego pickle no funciona: Ni siquiera llama
    # a "__getstate__" / "__setstate__" aunque lo defina.
    #
    # Por eso, he tenido que hacer esta CHAPUZA, que consiste en que
    # DataSet no deriva de un tipo "set", sino que lo encapsula. El
    # atributo "_children" contiene la lista de elementos del dataset,
    # y el objeto expone los metodos necesarios.

    def __init__(self, meta, children=None):
        self._meta = meta
        self._children = set(children) if children is not None else set()
        self._indexes = dict()

    def __getstate__(self):
        """No permito que se haga pickle de los indices"""
        return (self._meta, self._children)

    def __setstate__(self, state):
        """Restauro estado y borro indices"""
        self._meta = state[0]
        self._children = state[1]
        self._indexes = dict()

    def __call__(self, *crit):
        return DataSet(self._meta, (x for x in self._children if _matches(x, crit)))

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
            supertype = self._meta.up
            value = None if supertype is None else DataSet(supertype, (up for up in (x.up for x in self._children) if up is not None))
        else:
            subtype = self._meta.subtypes.get(attr, None)
            if subtype is not None:
                items = (x for x in (y._get(attr) for y in self._children) if x is not None)
                value = DataSet(subtype, chain(*items))
            else:
                field = self._meta.fields.get(attr, None)
                if field is not None:
                    items = (x for x in (y.get(attr) for y in self._children) if x is not None)
                    value = BaseSet(items)
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
            if not field or field.defindex is None:
                index = None
            else:
                index = Index(self._meta, attr, field.defindex, self._children)
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
        difference = set(items).difference(self._children)
        if difference:
            self._children.update(difference)
            for index in self._indexes.values():
                index.extend(difference)

    def add(self, item):
        if item not in self._children:
            self._children.add(item)
            for index in self._indexes.values():
                index.append(item)

    def pop(self):
        item = self._children.pop()
        for index in self._indexes.values():
            index.pop(item)
        return item

    def _sort(self, attr, asc=True):
        def key(item):
            return item.get(attr)
        return tuple(sorted(self._children, key=key, reverse=(not asc)))
        
    class Sorter(object):
        def __init__(self, dataset, asc=True):
            self._dataset = dataset
            self._asc = asc
        def __getattr__(self, attr):
            value = self._dataset._sort(attr, self._asc)
            setattr(self, attr, value)
            return value

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

        def testDataContains(self):
            """Funcion __contains__"""
            self.d1.x = 5
            self.failUnless("x" in self.d1)
            self.failIf("y" in self.d1)

        def testDataHas(self):
            """Propiedad 'has'."""
            self.d1.x = 10
            self.failUnless(self.d1.HAS.x)
            self.failIf(self.d1.HAS.y)
            
        def testDataGet(self):
            """Funcion get"""
            self.d1.x = -5
            self.failUnless(self.d1.get("x") == -5)
            self.failUnless(self.d1.get("y", "testpassed") == "testpassed")
            self.failUnless(type(self.d1.get("subfield")) == DataSet)
    
        def testData_Get(self):
            """Funcion get"""
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
                    'a': Field(defindex=-sys.maxint),
                    'b': Field(defindex=""),
                    'c': Field(),
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
            empty2 = DataObject(self.m2, self.d2) 
            self.d1.subfield = DataSet(self.m2, (d3, d4, d5, empty1))
            self.d2.subfield = DataSet(self.m2, (d6, d7, d8, empty2))
            self.all = DataSet(self.m1, (self.d1, self.d2))
            d3.a, d4.a, d5.a = 3, 4, 5
            d3.b, d4.b, d5.b = "aabb", "ccdd", "eeff"
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
            self.failUnless(len(indexA == -100) == 0)
            self.failUnless(len(indexB == "ghij") == 0)
            
        def testIndexEq(self):
            indexA = self.d1.subfield.INDEX.a
            indexB = self.d1.subfield.INDEX.b
            self.failUnless(+(indexA == 4).a == 4)
            self.failUnless(+(indexB == "eeff").b == "eeff")

        def testIndexNe(self):
            indexA = self.d1.subfield.INDEX.a
            indexB = self.d1.subfield.INDEX.b
            self.failUnless(set((indexA != 4).a) == set((3,5)))
            self.failUnless(set((indexB != "eeff").b) == set(("aabb", "ccdd")))

        def testIndexGt(self):
            indexA = self.d1.subfield.INDEX.a
            indexB = self.d1.subfield.INDEX.b
            self.failUnless(set((indexA > 4).a) == set((5,)))
            self.failUnless(set((indexB > "aabb").b) == set(("eeff", "ccdd")))

        def testIndexGe(self):
            indexA = self.d1.subfield.INDEX.a
            indexB = self.d1.subfield.INDEX.b
            self.failUnless(set((indexA >= 4).a) == set((4,5)))
            self.failUnless(set((indexB >= "aabb").b) == set(("aabb", "ccdd", "eeff")))

        def testIndexLt(self):
            indexA = self.d1.subfield.INDEX.a
            indexB = self.d1.subfield.INDEX.b
            self.failUnless(set((indexA < 5).a) == set((3,4)))
            self.failUnless(set((indexB < "ccdd").b) == set(("aabb",)))

        def testIndexLe(self):
            indexA = self.d1.subfield.INDEX.a
            indexB = self.d1.subfield.INDEX.b
            self.failUnless(set((indexA <= 5).a) == set((3,4,5)))
            self.failUnless(set((indexB <= "ccdd").b) == set(("aabb", "ccdd")))

        def testIndexPop(self):
            indexA = self.d1.subfield.INDEX.a
            self.d1.subfield.pop()
            remaining = self.d1.subfield.a
            self.failUnless(set((indexA <= 1000).a) == remaining)
            
        def testIndexAdd(self):
            anew = DataObject(self.m2, self.d2)
            anew.a = 10
            self.d1.subfield.add(anew)
            indexA = self.d1.subfield.INDEX.a
            self.failUnless(+(indexA == 10).a == 10)
            
        def testIndexUpdate(self):
            anew1 = DataObject(self.m2, self.d2)
            anew2 = DataObject(self.m2, self.d2)
            anew1.a, anew2.a = 10, 11
            self.d1.subfield.update((anew1, anew2))
            indexA = self.d1.subfield.INDEX.a
            self.failUnless(set((indexA >= 10).a) == set((10,11)))
            
        def testFilter(self):
            x = resolver.Resolver("self")
            expected = {"ccdd":0, "eeff":0}
            for item in self.d1.subfield(x.a >= 4):
                self.failUnless(item.b in expected)
                del(expected[item.b])

        def testEmptyFilter(self):
            x = resolver.Resolver("self")
            items = self.d1.subfield(x.a < 0)
            self.failUnless(len(items) == 0)

        def testCombinedFilter(self):
            x = resolver.Resolver("self")
            items = self.d1.subfield(x.a > 0, x.b._match("bb"))
            self.failUnless(len(items) == 1)
            self.failUnless(items.pop().a == 3)

        def testAttrib(self):
            items = self.d1.subfield.a
            self.failUnless(items == set((3, 4, 5)))

        def testSubtypeAttrib(self):
            items = self.all.subfield
            self.failUnless(len(items) == 8)

        def testUp(self):
            first = self.d1.subfield.up
            self.failUnless(len(first) == 1)
            self.failUnless(first.pop() is self.d1)

        def testBothUp(self):
            both = self.all.subfield.up
            self.failUnless(len(both) == 2)
            self.failUnless(self.d1 in both)
            self.failUnless(self.d2 in both)

        def testPos(self):
            x = resolver.Resolver("self")
            first = +(self.d1.subfield(x.a==3))
            self.failUnless(first.b == "aabb")

        def testInvalidPos(self):
            x = resolver.Resolver("self")
            self.assertRaises(AssertionError, operator.pos, self.d1.subfield(x.a>=3))
            self.assertRaises(AssertionError, operator.pos, self.d2.subfield(x.a<=3))

        def testSortBy(self):
            result = tuple(x.b for x in self.d1.subfield.SORTBY.b if x.HAS.b)
            self.failUnless(result == ("aabb", "ccdd", "eeff"))

        def testSortAsc(self):
            result = tuple(x.b for x in self.d1.subfield.SORTASC.b if x.HAS.b)
            self.failUnless(result == ("aabb", "ccdd", "eeff"))

        def testSortDesc(self):
            result = reversed(tuple(x.b for x in self.d1.subfield.SORTDESC.b if x.HAS.b))
            self.failUnless(tuple(result) == ("aabb", "ccdd", "eeff"))

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
