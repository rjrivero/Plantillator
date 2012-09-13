#!/usr/bin/env python

#
# Basado en la receta:
# http://code.activestate.com/recipes/576694/
#

from collections import MutableSet
from itertools import repeat, chain

try:
	from collections import OrderedDict
except ImportError:
	from odict import OrderedDict


class OrderedSet(MutableSet):

    def __init__(self, iterable=tuple()):
        self.__setstate__(iterable)

    def __getstate__(self):
        return self.keymap.keys()

    def __setstate__(self, iterable):
        self.keymap = OrderedDict(zip(iterable, repeat(None)))
        
    def __len__(self):
        return len(self.keymap)

    def __contains__(self, key):
        return key in self.keymap

    def add(self, key):
        self.keymap.setdefault(key, None)

    def discard(self, key):
        self.keymap.pop(key, None)

    def __iter__(self):
        return self.keymap.iterkeys()

    def __reversed__(self):
        return reversed(self.keymap.iterkeys())

    def pop(self, last=True):
        return self.keymap.popitem(last).key
 
    def __repr__(self):
        if not self:
            return '%s()' % (self.__class__.__name__,)
        return '%s(%r)' % (self.__class__.__name__, list(self))

    def __eq__(self, other):
        return frozenset(self) == frozenset(other)

    def union(self, other):
        return OrderedSet(chain(self, other))
