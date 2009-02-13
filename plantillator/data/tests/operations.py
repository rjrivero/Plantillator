#!/usr/bin/env python
# -*- vim: expandtab tabstop=4 shiftwidth=4 smarttab autoindent

import unittest
import operator
from data.operators import *


class Test_DeferredOp(unittest.TestCase):

    def setUp(self):
        self.first, self.second = None, None
        self.deferred = DeferredOperation(self.myop, "second")

    def myop(self, first, second):
        self.first = first
        self.second = second

    def test_construct(self):
        self.failUnless(self.deferred.operator == self.myop)
        self.failUnless(self.deferred.operand == "second")

    def test_deferred(self):
        """Operator is called with operands in the right order"""
        self.deferred("first")
        self.failUnless(self.first == "first")
        self.failUnless(self.second == "second")


class Test_DeferredAny(unittest.TestCase):

    def setUp(self):
        self.deferred = DeferredOperation(operator.ge, 10)
        self.deferredany = DeferredAny(self.deferred)

    def test_construct(self):
        self.failUnless(self.deferredany.operator == self.deferred)

    def test_any(self):
        """True if any item matches the criterium"""
        self.failUnless(self.deferredany((5, 10, 15)) == True)

    def test_none(self):
        """False if no item matches"""
        self.failUnless(self.deferredany((6, 7, 8)) == False)


DeferrerTests = [
    (lambda x, y: x == y,     5,      10,           False),
    (lambda x, y: x == y,     "ok",   "ko",         False),
    (lambda x, y: x == y,     "ok",   "ok",         True),
    (lambda x, y: x == y,     5,      5,            True),
    (lambda x, y: x != y,     5,      10,           True),
    (lambda x, y: x != y,     "ok",   "ko",         True),
    (lambda x, y: x != y,     "ok",   "ok",         False),
    (lambda x, y: x != y,     10,     10,           False),
    (lambda x, y: x > y,      5,      10,           False),
    (lambda x, y: x > y,      10,     5,            True),
    (lambda x, y: x < y,      5,      10,           True),
    (lambda x, y: x < y,      10,     5,            False),
    (lambda x, y: x >= y,     5,      10,           False),
    (lambda x, y: x >= y,     10,     10,           True),
    (lambda x, y: x <= y,     5,      5,            True),
    (lambda x, y: x <= y,     10,     5,            False),
    (lambda x, y: x + y,      2,      (1,2,3),      True),
    (lambda x, y: x + y,      4,      (1,2,3),      False),
    (lambda x, y: x + y,      "ok",   ("ok","ko"),  True),
    (lambda x, y: x + y,      "KO",   ("ok","ko"),  False),
    (lambda x, y: x - y,      2,      (1,2,3),      False),
    (lambda x, y: x - y,      4,      (1,2,3),      True),
    (lambda x, y: x - y,      "ok",   ("ok","ko"),  False),
    (lambda x, y: x - y,      "KO",   ("ok","ko"),  False),
    (lambda x, y: x * y,      "ok",   "k.*",        True),
    (lambda x, y: x * y,      "ok",   "ko"          False)
]

def make_deferred_tests():
    class Test(object):
        def __init__(self, func, x, y, expected):
            self.func = func
            self.x = x
            self.y = y
            self.expected = expected
        def __call__(self):
            return (self.func(Deferred(), self.y)(self.x) == self.expected)
    tests = dict(("test_%d" % index, Test(*data))
                for index, data in enumerate(DeferrerTests))
    return type("Test_Deferrer", (unittest.TestCase,), tests)

Test_Deferrer = make_deferrer_tests()


if __name__ == "__main__":
    unittest.main()

