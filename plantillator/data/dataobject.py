#!/usr/bin/env python
# -*- vim: expandtab tabstop=4 shiftwidth=4 smarttab autoindent


from itertools import islice, chain


def DataType(base):

    """Devuelve un tipo derivado de "base" que se comporta como un dict.

    Los atributos de los objetos de este tipo seran accesibles como entradas
    de diccionario. Es decir, x['attrib'] == x.attrib

    Los DataObjects estan relacionados en forma de arbol. Cada nodo "hijo"
    tiene un nodo "padre", y un nodo "padre" puede tener varios nodos "hijo".

    Los elementos del diccionario clsdict se le agregan a la clase devuelta.
    """

    class _DataObject(base):

        @property
        def _type(self):
            return self.__class__

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
            for key in (str(x) for x in self._type._DOMD.attribs):
                value = self.get(key)
                if value is not None:
                    yield (key, value)

        def __getitem__(self, item):
            try:
                return getattr(self, item)
            except AttributeError as details:
                raise KeyError(details)

        def __setitem__(self, name, value):
            setattr(self, name, value)

        # Herramientas para filtrado

        def _matches(self, kw):
            """Comprueba si el atributo indicado cumple el criterio."""
            return all(crit._verify(self.get(key), self) for key, crit in kw.iteritems())

        def follow(self, table, **kw):
            """Sigue una referencia a una tabla.

            Recibe una tabla y unos criterios de filtrado. Resuelve todas las referencias
            a "self" que haya en los criterios, sustituyendolas por si mismo, y luego
            aplica los criterios a la tabla que se esta siguiendo, y almacena el resultado
            en un atributo con el mismo nombre que la tabla.

            Devuelv self.
            """
            self._type._DOMD.add_synthetic(table, **kw)
            return self

        # Necesario para que django no meta basurilla por medio
        class Meta(object):
            abstract = True

    return _DataObject


class MetaData(object):

    """MetaDatos relacionados con una clase de DataObject

    name: label de la clase (string)
    parent: clase padre, en la jerarquia (DataObject.__class__)
    children: clases hijo en la jerarquia (dict(string, DataObject.__class__))
    attribs: conjunto de atributos (list(string))
    synthetic: atributos "sinteticos" (foreign keys)
    summary: lista ordenada de atributos que puede usarse como
             "sumario" o descripcion abreviada de un objeto

    Por convencion, las clases derivadas de DataObject(...) deben tener un
    atributo _DOMD (DataObject MetaData) de este tipo.
    """

    def __init__(self, cls, name='', parent=None):
        # Nos encargamos de poner el atributo aqui
        setattr(cls, '_DOMD', self)
        # por convencion, el tipo siempre se llama _type.
        self._type = cls
        self.parent = parent
        self.name = name
        self.synthetic = dict()
        #self.children = dict()
        #self.attribs = set()
        #self.summary = list()

    def follow(self, table, **kw):
        """Agrega un nuevo atributo sintetico"""
        self.synthetic[table._type._DOMD.name] = (table, kw)

    @property
    def descendants(self):
        return sorted(set(chain(self.children.keys(), self.synthetic.keys())))

    def produce(self, item, attr):
        """Genera la lista de objetos hijos del item actual.

        Solo recorre los sinteticos, no los children. El tipo de
        objetos children y la forma de crear listas a partir de ellos
        depende del tipo derivado de MetaData que se este usando.
        """
        table, kw = self.synthetic[attr]
        crit = dict((k, (v if not hasattr(v, '_resolve') else v._resolve(item)))
                           for (k, v) in kw.iteritems())
        return table(**crit)


class Fallback(DataType(object)):

    """Realiza fallback en la jerarquia de objetos

    Objeto que implementa el mecanismo de fallback de los DataObjects.
    """

    def __init__(self, up, data=None, depth=None):
        super(Fallback, self).__init__()
        self._up = up
        if data:
            self.update(data)
        self._depth = depth

    @property
    def _type(self):
        """Sobrecargo "_type" para que pueda accederse a los MetaDatos"""
        return self._up._type

    def __getattr__(self, attr):
        """Busca el atributo en este objeto y sus ancestros"""
        if attr.startswith('__'):
            raise AttributeError(attr)
        for value in islice(self._fallback(attr), 0, self._depth):
            if value is not None:
                return value
        raise AttributeError(attr)

    def _fallback(self, attr):
        self = self._up
        while self:
            yield self.get(attr)
            self = self._up

    def __setitem__(self, index, value):
        setattr(self, index, value)

