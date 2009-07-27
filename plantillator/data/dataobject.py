#!/usr/bin/env python
# -*- vim: expandtab tabstop=4 shiftwidth=4 smarttab autoindent


from itertools import islice


def DataObject(base):

    """Devuelve un tipo derivado de "base" que se comporta como un dict.

    Los atributos de los objetos de este tipo seran accesibles como entradas
    de diccionario. Es decir, x['attrib'] == x.attrib

    Los DataObjects estan relacionados en forma de arbol. Cada nodo "hijo"
    tiene un nodo "padre", y un nodo "padre" puede tener varios nodos "hijo".
    """

    class _DataObject(base):

        def __init__(self, up=None, data=None):
            super(_DataObject, self).__init__()
            self._up = up
            if data:
                self.update(data)

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
            for (k, v) in self.__dict__.iteritems():
                if not k.startswith('_') and k not in ('up', 'fb'):
                    yield (k, v)

        def __getitem__(self, item):
            return getattr(self, item)

        def __setitem__(self, name, value):
            setattr(self, name, value)

        # Herramientas para filtrado

        def _matches(self, kw):
            """Comprueba si el atributo indicado cumple el criterio."""
            return all(crit(self.get(key)) for key, crit in kw.iteritems())

    return _DataObject


class Fallback(DataObject(object)):

    """Realiza fallback en la jerarquia de objetos

    Objeto que implementa el mecanismo de fallback de los DataObjects.
    """

    def __init__(self, up, data=None, depth=None):
        super(Fallback, self).__init__(up, data)
        self._depth = depth

    def __getattr__(self, attr):
        """Busca el atributo en este objeto y sus ancestros"""
        try:
            return super(Fallback, self).__getattr__(self, attr)
        except AttributeError:
            for ancestor in islice(self._ancestors(), 0, self._depth):
                retval = ancestor.get(attr)
                if retval is not None:
                    return retval
            raise

    def _ancestors(self):
        while self._up:
            self = self._up
            yield self

