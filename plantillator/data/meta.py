#!/usr/bin/env python
# -*- vim: expandtab tabstop=4 shiftwidth=4 smarttab autoindent


from itertools import chain
from django.db import models
from plantillator.data.dataobject import _DataObject
from plantillator.data.dataset import DataSet


def Relation(model, *arg, **kw):
    """Marca los campos que son foreign keys"""
    fk = models.ForeignKey(model, *arg, **kw)
    fk._type = model
    return fk


def dynamic(field):
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
    def wrap(func):
        field._Dynamic = func
        return field
    return wrap


def django_prop(cls, attrib):
    """Factoria de propiedades

    Es una factoria "falsa", porque en este caso las propiedades
    no se aprenden bajo demanda, sino que se construyen junto con
    el modelo. Asi que se limita a generar "AttributeError"
    """
    raise AttributeError(attrib)


def add_dataobject(cls, name, bases, d, data):
    """Extiende el tipo "cls" convirtiendolo en un DataObject.

    Esta funcion debe ser llamada desde la funcion __new__
    de la metaclase. Modifica "cls" para que se comporte como
    un DataObject, y enlaza los tipos adecuadamente.

    "data" debe ser el DataObject raiz.

    Lamentablemente esta funcion depende bastante de la estructura
    interna del _DataObject. Esperemos que no cambie mucho...
    """
    # obtengo el tipo "padre"
    try:
        parent = d['_up']._type
    except (KeyError, AttributeError):
        parent = data._type
        #setattr(cls, '_up', None)
    # Por la estructura de la base de datos, puede haber modelos con
    # nombres duplicados (ej: sedes.vlans.switches, sedes.switches).
    # Como esto no lo soporta django, lo que hago es partir el nombre de la
    # clase en trozos separados por "_", y quedarme como nombre para el
    # atributo solo con la ultima parte.
    name = name.split("_").pop().lower()
    try:
        return parent._Properties[name]._type
    except (AttributeError, KeyError):
        parent._Properties[name] = SetBuilder(cls)
        for key, val in _DataObject.__dict__.iteritems():
            if not key.startswith('__') or key.startswith('__get'):
                setattr(cls, key, val)
        setattr(cls, '_Parent', parent)
        setattr(cls, '_Properties', dict())
        return cls


def add_dynamic(cls, name, bases, d, data):
    """Agrega los campos dinamicos a la clase"""
    for key, val in d.iteritems():
        if hasattr(val, '_Dynamic'):
            def fget(self):
                val = getattr(self, key)
                return val if val is not None else func(self, data)
            def fset(self, val):
                setattr(self, key, val)
            setattr(cls, key[1:], property(fget, fset))


def new(metaclass, cls, name, bases, d, data):
    """Cuerpo de la metaclase que debe crearse para cada aplicacion"""
    cls = metaclass.__new__(cls, name, bases, d)
    add_dynamic(cls, name, bases, d, data)
    add_dataobject(cls, name, bases, d, data)
    return cls


class SetBuilder(object):

    """Factoria de datos

    Dado un objeto y el atributo al que se quiere acceder, recupera
    el atributo de la base de datos y lo devuelve como un DataSet.
    """

    def __init__(self, model):
        self._type = model

    def __call__(self, obj, attr):
        if obj.pk is not None:
            return DataSet(self._type, self._type.objects.filter(_up=obj.pk))
        else:
            return DataSet(self._type, self._type.objects.all())           

