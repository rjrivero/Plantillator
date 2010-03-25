#!/usr/bin/env python
# -*- vim: expandtab tabstop=4 shiftwidth=4 smarttab autoindent

from itertools import islice, chain


class DataObject(object):

    """Objeto que adopta algunos comportamientos de un dict.

    Los atributos de los objetos de este tipo seran accesibles como entradas
    de diccionario. Es decir, x['attrib'] == x.attrib

    Los DataObjects estan relacionados en forma de arbol. Cada nodo "hijo"
    tiene un nodo "padre", y un nodo "padre" puede tener varios nodos "hijo".

    Los elementos del diccionario clsdict se le agregan a la clase devuelta.
    """

    def __init__(self, up=None, data=None, domd=None):
        """Construye el objeto con atributos escalares"""
        if data:
            self.update(data)
        self._up = up
        self._domd = domd or self.__class__._domd

    @property
    def _type(self):
        return self.__class__

    @property
    def fb(self, data=None, depth=None):
        """Devuelve un "proxy" para la busqueda de atributos.

        Cualquier atributo al que se acceda sera buscado en el objeto que
        ha generado el fallback y sus ancestros
        """
        return Fallback(self, data, depth)

    def __getattr__(self, attr):
        """Intenta acceder a un atributo dinamico"""
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
        # Excluyo atributos magicos
        if attr.startswith("_"):
            raise AttributeError(attr)
        try:
            data = self._domd.produce(self, attr)
        except KeyError:
            raise AttributeError(attr)
        else:
            setattr(self, attr, data)
            return data

    def __add__(self, other):
        """Concatena dos DataSets"""
        if self._domd != other._domd:
            raise TypeError(other._domd._type)
        return self._domd.concat(self, other)

    def __str__(self):
        fields = (self.get(k) for k in self._domd.summary)
        return ", ".join(str(f) for f in fields if f is not None)

    def __repr__(self):
        # No es una representacion completa, es solo para no meter
        # mucha morralla en la shell
        return "DataObject<%s> (%s,...)" % (self._domd.name, str(self))

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
        """itera sobre los atributos estaticos (no descendants)"""
        for key in (str(x) for x in self._domd.attribs):
            value = self.get(key)
            if value is not None:
                yield (key, value)

    def __getitem__(self, item):
        try:
            return getattr(self, item)
        except AttributeError as detail:
            raise KeyError(detail)

    def __setitem__(self, name, value):
        setattr(self, name, value)

    def __len__(self):
        """Invariante, siempre devuelve 1"""
        # esta funcion hace falta para soportar DataSet.up, porque
        # el atributo up es especial: aunque es de tipo DataObject,
        # no esta en una lista, sino suelto.
        return 1

    # Herramientas para filtrado

    def follow(self, table, **kw):
        """Sigue una referencia a una tabla.

        Recibe una tabla y unos criterios de filtrado. Resuelve todas las referencias
        a "self" que haya en los criterios, sustituyendolas por si mismo, y luego
        aplica los criterios a la tabla que se esta siguiendo, y almacena el resultado
        en un atributo con el mismo nombre que la tabla.

        Devuelv self.
        """
        domd = self._domd
        domd.follow(table, domd.crit(kw))
        self.invalidate()
        return self

    def invalidate(self, attribs=None):
        """Invalida los atributos dinamicos del objeto.

        Se incluyo para poder cambiar referencias dinamicamente,
        y refrescar, en el DataNav.
        """
        for attr in (attribs or self._domd.mutables):
            try:
                delattr(self, attr)
            except AttributeError:
                pass


class DataSet(set):

    """Lista basica de DataObjects

    Implementa las funciones de acceso a atributos y filtrado, delegandolas
    en el objeto MetaData.
    """

    def __init__(self, domd, data=None):
        """Crea una lista"""
        set.__init__(self, data or tuple())
        self._domd = domd

    def __call__(self, **kw):
        """Busca los elementos de la lista que cumplan los criterios dados"""
        return self._filter({}, kw)

    def _filter(self, symbols, kw):
        """Como __call__, pero acepta una tabla de simbolos"""
        domd = self._domd
        return domd.filterset(symbols, self, domd.crit(kw))

    def __add__(self, other):
        """Concatena dos DataSets"""
        if self._domd != other._domd:
            raise TypeError(other._domd)
        return self._domd.concat(self, other)

    def __pos__(self):
        """Extrae el unico elemento del DataSet"""
        if len(self) == 1:
            return self.copy().pop()
        raise IndexError(0)

    def __getattr__(self, attr):
        """Selecciona un item en la lista

        Devuelve un set con los distintos valores del atributo seleccionado
        en cada uno de los elementos de la lista.

        Si el atributo seleccionado es una sublista, en lugar de un set
        se devuelve un DataSet con todos los elementos encadenados.
        """
        if attr.startswith("_"):
            raise AttributeError(attr)
        try:
            data = self._domd.produceset(self, attr)
        except KeyError as details:
            raise AttributeError(details)
        else:
            setattr(self, attr, data)
            return data

    def __repr__(self):
        # No hago un volcado correcto, simplemente evito que
        # me saque por pantalla mucha morralla...
        return "CSVSet<%s> [%d items]" % (self._domd.path, len(self))

    def follow(self, table, **kw):
        """Modifica los objetos, agregando la referencia seguida.

        Cada objeto de la lista tendra un nuevo campo con el nombre de la tabla,
        y que apuntara a la tabla (filtrada con los criterios especificados).
        """
        # creo o actualizo el campo sintetico.
        domd = self._domd
        domd.follow(table, domd.crit(kw))
        self.invalidate((table._domd.name,))
        return self

    def invalidate(self, attribs=None):
        self._domd.invalidate(self, attribs)

    @property
    def _type(self):
        return self._domd._type


class Fallback(DataObject):

    """Realiza fallback en la jerarquia de objetos

    Objeto que implementa el mecanismo de fallback de los DataObjects.
    """

    def __init__(self, item, data=None, depth=None):
        super(Fallback, self).__init__(item._up, data, item._domd)
        self._fb = item
        self._depth = depth

    @property
    def back(self):
        """Permite acceder directamente al objeto fallback"""
        return self._fb

    def __getattr__(self, attr):
        """Busca el atributo en este objeto y sus ancestros"""
        if attr.startswith('_'):
            raise AttributeError(attr)
        for value in islice(self._fallback(attr), 0, self._depth):
            if value is not None:
                return value
        raise AttributeError(attr)

    def _fallback(self, attr):
        obj = self._fb
        while obj:
            yield obj.get(attr)
            obj = obj.up

