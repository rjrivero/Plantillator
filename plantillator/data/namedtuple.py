#!/usr/bin/env python


from operator import itemgetter
from itertools import chain


def NamedTuple(class_name, docstr, **fields):
    """Crea un tipo de NamedTuple con los campos indicados

    los argumentos con nombre definen los nombres de los campos,
    y su valor es la posicion del campo dentro de la tupla.

    Por ejemplo:
    >>> Point = NamedTuple("Point", "a 2D Point", x=0, y=1)
    >>> p = Point(10, 20)
    >>> p.x
    10
    >>> p.y
    20
    >>> p[0]
    10
    >>> p[1]
    20
    """
    def tnew(cls, *arg):
        return tuple.__new__(cls, arg)
    tdict = dict((x, property(itemgetter(y))) for x, y in fields.iteritems())
    tdict.update({ '__new__': tnew, '__doc__': docstr })
    return type(class_name, (tuple,), tdict)

