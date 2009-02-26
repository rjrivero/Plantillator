#!/usr/bin/env python
# -*- vim: expandtab tabstop=4 shiftwidth=4 smarttab autoindent


from unittest import TestCase, main
import operator

from tests.helper import *
from data.operations import *


class Test_DeferredOp(TestCase):

    def setUp(self):
        self.first, self.second = None, None
        self.deferred = DeferredOp(self.myop, "second")

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


class Test_DeferredAny(TestCase):

    def setUp(self):
        self.deferred = DeferredOp(operator.ge, 10)
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
    (lambda x, y: x - y,      "KO",   ("ok","ko"),  True),
    (lambda x, y: x * y,      "ok",   "k.*",        True),
    (lambda x, y: x * y,      "ok",   "ko",         False)
]

def deferrer_tester(func, x, y, expected):
    def test(self):
        if func(Deferrer(), y)(x) != expected:
            print "Error: %s <op> %s != %s" % (str(x), str(y), str(expected))
            self.fail()
    return test

Test_Deferrer = build_tester("Test_Deferrer", DeferrerTests, deferrer_tester)


if __name__ == "__main__":
    main()

