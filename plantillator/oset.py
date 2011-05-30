#!/usr/bin/env python

#
# Basado en la receta:
# http://code.activestate.com/recipes/576694/
#

import collections
from itertools import chain


class OrderedSet(collections.MutableSet):

    def __init__(self, iterable=None):
        self.end = end = [] 
        end += [None, end, end]         # sentinel node for doubly linked list
        self.keymap = {}                   # key --> [key, prev, next]
        if iterable is not None:
            self |= iterable

    def __len__(self):
        return len(self.keymap)

    def __contains__(self, key):
        return key in self.keymap

    def add(self, key, KEY=0, PREV=1, NEXT=2):
        if key not in self.keymap:
            end = self.end
            curr = end[PREV]
            curr[NEXT] = end[PREV] = self.keymap[key] = [key, curr, end]

    def discard(self, key, KEY=0, PREV=1, NEXT=2):
        if key in self.keymap:        
            key, prev, next = self.keymap.pop(key)
            prev[NEXT] = next
            next[PREV] = prev

    def __iter__(self, KEY=0, PREV=1, NEXT=2):
        end = self.end
        curr = end[NEXT]
        while curr is not end:
            yield curr[KEY]
            curr = curr[NEXT]

    def __reversed__(self, KEY=0, PREV=1, NEXT=2):
        end = self.end
        curr = end[PREV]
        while curr is not end:
            yield curr[KEY]
            curr = curr[PREV]

    def pop(self, last=True):
        if not self:
            raise KeyError('set is empty')
        key = next(reversed(self)) if last else next(iter(self))
        self.discard(key)
        return key

    def __repr__(self):
        if not self:
            return '%s()' % (self.__class__.__name__,)
        return '%s(%r)' % (self.__class__.__name__, list(self))

    def __eq__(self, other):
        if isinstance(other, OrderedSet):
            return len(self) == len(other) and list(self) == list(other)
        return set(self) == set(other)

    def __del__(self):
        self.clear() # remove circular references

    def union(self, other):
        return OrderedSet(chain(self, other))
