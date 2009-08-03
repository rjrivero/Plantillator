#!/usr/bin/env python
# -*- vim: expandtab tabstop=4 shiftwidth=4 smarttab autoindent


from itertools import chain
from collections import namedtuple
from gettext import gettext as _

from plantillator.data.dataobject import DataType
from ..data import dataobject

_NOT_ANCHOR = _("%(class)s.%(field)s debe ser un ANCHOR")


class AnchorMeta(namedtuple('AnchorMeta', 'kind, relations, field, arg, kw')):

    class Relation(namedtuple('Relation', 'model, attrib')):
        def __repr__(self):
            return "%s.%s" % (self.model._DOMD.name, self.attrib)

    def relate(self, model, attrib):
        self.relations.add(AnchorMeta.Relation(model, attrib))

    def __repr__(self):
        return str(self.relations)


def anchor(field_cls, *arg, **kw):
    """Marca un campo como un 'ancla' al que otros modelos pueden referirse.

    Permite automatizar la creacion de pseudo foreign-keys. No se usan
    ForeignKeys autenticas del ORM, porque en ese caso el comportamiento no
    seria compatible con el backend CSV, y las plantillas no serian validas
    para los dos backends.

    se utiliza envolvendo la creacion del campo, por ejemplo:
    nombre = anchor(models.CharField, max_length=64)
    """

    f = field_cls(*arg, **kw)
    f._DOMD = AnchorMeta('anchor', set(), field_cls, arg, kw)
    return f


class ChildOfMeta(namedtuple('ChildOfMeta', 'kind, model')):
    def __repr__(self):
        print "child of %s" % self.model._DOMD.name


def childOf(fk, model, *arg, **kw):
    """Marca un campo como Foreign Key hacia el modelo padre

    Por convencion, el nombre del campo sera "_up", aunque eso no lo
    chequea esta funcion, sino la metaclase.

    Se usa envolviendo la creacion del Foreign Key en el ORM, por ejemplo:
    _up = childOf(models.ForeignKey, ParentModel)
    """

    f = fk(model, *arg, **kw)
    f._DOMD = ChildOfMeta('childOf', model)
    return f


class RelationMeta(namedtuple('RelationMeta', 'kind, model, field, filter')):

    @property
    def anchor(self):
        return self.model._DOMD.anchors[self.field]

    def __repr__(self):
        print "%s.%s" % (self.model._DOMD.name, self.field)


def relation(model, field_name, **kw):
    """Crea una relacion a un campo de otro modelo

    Marca el campo como un campo relacionado con otro modelo. No se usan
    Foreign Keys reales del ORM porque entonces los datos recuperados serian
    objetos y no campos simples, lo que los haria incompatibles con el 
    backend csv y requeriria que las plantillas fuesen distintas.

    Esta funcion se usa como un decorador, decorando una funcion que filtra
    los valores que puede tomar el campo. Por ejemplo:
    @relation(Switches, 'nombre')
    def switch(self, data):
        return data.sedes(nombre=self.sede).switches
    """

    try:
        anchor = model._DOMD.anchors[field_name]
    except KeyError:
        raise TypeError, _NOT_ANCHOR % {'class': model.__class__.__name__, 
                                        'field': field_name }
    kw.update(anchor.kw)
    related = anchor.field(*anchor.arg, **kw)
    def wrapper(filter):
        related._DOMD = RelationMeta('relation', model, field_name, filter)
        return related
    return wrapper


class DynamicMeta(namedtuple('DynamicMeta', 'kind, func')):
    def __repr__(self):
        return self.func.__doc__


def dynamic(field_cls, *arg, **kw):
    """Decorador que marca los campos dinamicos

    Un campo dinamico se comporta en funcion de lo que se
    encuentra en la base de datos:

    - Si el campo de la base de datos es None, el campo
      dinamico se recalcula cada vez que se accede a el.
    - Si el campo de la base de datos no es None, el campo
      dinamico toma el valor del elemento de la bd.

    Para que la cosa funcione bien, los campos dinamicos
    deben definirse en el modelo con un nombre que empiece
    por "_". La metaclase crea propiedades sin el "_".
    """

    field = field_cls(*arg, **kw)
    def wrapper(func):
        field._DOMD = DynamicMeta('dynamic', func)
        return field
    return wrapper


class MetaData(dataobject.MetaData):

    def __init__(self, cls, name, bases, d, data):
        """Procesa el diccionario de una nueva clase de DataObject.

        Debe ser llamada por la funcion __new__ de la Metaclase, antes de
        comenzar con el proceso del tipo. Recorre el diccionario recuperando
        los metadatos, y eleminando los que no sean significativos para
        el ORM.
        """

        try:
            parent = d['_up']._DOMD
        except KeyError:
            parent = data._type
        else:
            assert(parent.kind == 'childOf')
            parent = parent.model
        # nombres duplicados (ej: sedes.vlans.switches, sedes.switches).
        # Como esto no lo soporta django, lo que hago es partir el nombre de
        # la clase en trozos separados por "_", y quedarme como nombre para
        # el atributo solo con la ultima parte.
        name = name.split("_").pop().lower()
        super(MetaData, self).__init__(cls, name, parent)
        self.anchors = dict()
        self.related = dict()
        self.dynamic = set()
        # proceso los atributos
        for key, value in d.iteritems():
            try:
                domd = value._DOMD
            except AttributeError:
                if not key.startswith('_'):
                    self.attribs.add(key)
            else:
                func = getattr(self, 'add_%s' % domd.kind)
                func(domd, key, data)

    def add_childOf(self, domd, key, data):
        assert(key == '_up')
        self.parent._DOMD.children[self.name] = self._type

    def add_relation(self, domd, key, data):
        anchor = domd.anchor
        anchor.relate(self._type, key)
        self.attribs.add(key)
        self.related[key] = domd

    def add_anchor(self, domd, key, data):
        self.anchors[key] = domd
        self.attribs.add(key)

    def add_dynamic(self, domd, key, data):
        assert(key.startswith('_'))
        propname = key[1:]
        def fget(self):
            val = self.get(key)
            return val if val is not None else domd.func(self, data)
        def fset(self, val):
            setattr(self, key, val)
        setattr(cls, propname, property(fget, fset))
        self.dynamic.add(propname)


def RootData():
    """Crea un nuevo tipo raiz (parent == None)"""
    root = DataType(object)
    data = root()
    setattr(root, '_DOMD', MetaData(root, 'ROOT', root.__bases__, {}, data))
    return data

