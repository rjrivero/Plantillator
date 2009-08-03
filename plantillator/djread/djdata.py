#!/usr/bin/env python
# -*- vim: expandtab tabstop=4 shiftwidth=4 smarttab autoindent


from django.db import models, backend
from django.db.models import Count

from ..data.base import BaseSet
from ..data.dataobject import DataType
import meta


def anchor(field_cls, *arg, **kw):
    kw['db_index'] = True
    return meta.anchor(field_cls, *arg, **kw)

def childOf(model, *arg, **kw):
    return meta.childOf(models.ForeignKey, model, *arg, **kw)

def relation(model, field_name, **kw):
    kw['db_index'] = True
    return meta.relation(model, field_name, **kw)

dynamic = meta.dynamic


class Deferrer(object):

    """Adapta el Deferrer de data.base para usarlo con Django"""

    def _defer(self, positive, operator, operand):
        """Devuelve una funcion f(x) == (positive, x__operator, operand)

        'positive' indica si debe usarse logica positiva (incluir los valores
        que cumplen el criterio) o negativa (excluirlos).
        """
        def decorate(colname):
            return (positive, "%s__%s" % (colname, operator), operand)
        return decorate

    def __call__(self, item):
        return self.defer(True, 'isnull', False)

    def __eq__(self, other):
        return self._defer(True, 'iexact', other)

    def __ne__(self, other):
        return self._defer(False, 'iexact', other)

    def __lt__(self, other):
        return self._defer(True, 'lt', other)

    def __le__(self, other):
        return self._defer(True, 'lte', other)

    def __gt__(self, other):
        return self._defer(True, 'gt', other)

    def __ge__(self, other):
        return self._defer(True, 'gte', other)

    def __mul__(self, other):
        """Comprueba la coincidencia con una exp. regular"""
        return self._defer(True, 'regex', other)

    def __add__(self, arg):
        """Comprueba la pertenecia a una lista"""
        return self._defer(True, 'in', asIter(arg))

    def __sub__(self, arg):
        """Comprueba la no pertenencia a una lista"""
        return self._defer(False, 'in', asIter(arg))


class DJSet(models.query.QuerySet):

    """QuerySet que implementa la interfaz de los DataSets

    Cuidado! solo esta pensado para ser usado con los metodos que se
    definen en esta clase. Si se usan directamente los metodos heredados de
    QuerySet, los resultados pueden ser inconsistentes.
    """

    def __init__(self, *arg, **kw):
        super(DJSet, self).__init__(*arg, **kw)
        # criterios que han llevado a la obtencion de este QuerySet
        self._pos = dict()
        self._neg = dict()
        # True si hay alguna columna de agregado
        self._agg = False
 
    def __call__(self, **kw):
        """Filtra el DJSet acorde al criterio especificado"""
        domd = self._type._DOMD
        base, pos, neg, agg = self, dict(), dict(), self._agg
        for key, val in kw.iteritems():
            if not hasattr(val, '__call__'):
                val = (Deferrer() == val)
            if key in domd.attribs:
                p, crit, val = val(key)
            else:
                child = domd.children[key]
                agg   = True
                refer = child._meta.object_name.lower()
                label = '%s_count' % key
                base  = base.annotate(**{label: Count(refer)})
                p, crit, val = val(label)
            if p:
                pos[crit] = val
            else:
                neg[crit] = val
        if pos:
            base = base.filter(**pos)
        if neg:
            base = base.exclude(**neg)
        pos.update(self._pos)
        neg.update(self._neg)
        base._agg = agg
        base._pos = pos
        base._neg = neg
        return base

    def __getattr__(self, attrib):
        """Obtiene el atributo seleccionado"""
        domd = self._type._DOMD
        if attrib in domd.attribs:
            return BaseSet(x[attrib] for x in self.values(attrib))
        try:
            objects = domd.children[attrib].objects.all()
        except KeyError as details:
            raise AttributeError(details)
        pos, neg = dict(), dict()
        if self._agg:
            pos['_up__in'] = self.values('pk').query
        else:
            for key, val in self._pos.iteritems():
                pos['_up__%s' % key] = val
            for key, val in self._neg.iteritems():
                neg['_up__%s' % key] = val
        if pos:
            objects = objects.filter(**pos)
        if neg:
            objects = objects.exclude(**neg)
        objects._agg = False
        objects._pos = pos
        objects._neg = neg
        return objects

    @property
    def up(self):
        parent = self._type._DOMD.parent.objects.all()
        pos    = {'pk__in': self.values('_up').query}
        parent = parent.filter(**pos)
        parent._agg = False
        parent._pos = pos
        parent._neg = dict()
        return parent

    @property
    def _type(self):
        return self.model


class DJManager(models.Manager):

    def get_query_set(self):
        return DJSet(self.model)


class DJModel(DataType(models.Model)):

    objects = DJManager()

    class Meta(object):
        abstract = True

