#!/usr/bin/env python
# -*- vim: expandtab tabstop=4 shiftwidth=4 smarttab autoindent

import unittest
import operator

from helper import tester
from deferop import *


class Test_UnaryOperator(unittest.TestCase):

    def test_call(self):
        """Raise NotImplementedError"""
        op = UnaryOperator()
        self.assertRaises(NotImplementedError, op, None)


class Test_DeferredOperation(unittest.TestCase):

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


class Test_DeferAny(unittest.TestCase):

    def setUp(self):
        self.deferred = DeferredOperation(operator.ge, 10)
        self.deferany = DeferAny(self.deferred)

    def test_construct(self):
        self.failUnless(self.deferany.operator == self.deferred)

    def test_any(self):
        """True if any item matches the criterium"""
        self.failUnless(self.deferany((5, 10, 15)) == True)

    def test_none(self):
        """False if no item matches"""
        self.failUnless(self.deferany((6, 7, 8)) == False)


class Test_DeferOp(unittest.TestCase):

    def setUp(self):
        self.myop = DeferOp()

    def test_eq(self):
        """Operator '=='"""
        op = self.myop == "testeq"
        self.failUnless(op("testeq") == True)
        self.failUnless(op("testuneq") == False)

    def test_ne(self):
        """Operator '!='"""
        op = self.myop != "testeq"
        self.failUnless(op("testeq") == False)
        self.failUnless(op("testuneq") == True)

    def test_lt(self):
        """Operator '<'"""
        op = self.myop < 5
        self.failUnless(op(4) == True)
        self.failUnless(op(6) == False)

    def test_le(self):
        """Operator '<='"""
        op = self.myop <= 5
        self.failUnless(op(5) == True)
        self.failUnless(op(6) == False)

    def test_gt(self):
        """Operator '>'"""
        op = self.myop > 10
        self.failUnless(op(11) == True)
        self.failUnless(op(9) == False)

    def test_ge(self):
        """Operator '>='"""
        op = self.myop >= 10
        self.failUnless(op(10) == True)
        self.failUnless(op(8) == False)

    def test_bool_empty(self):
        """Empty lists evaluate to false, non empty lists don't"""
        self.failUnless(self.myop([]) == False)
        self.failUnless(self.myop([None]) == True)

    def test_bool_string(self):
        """Empty strings evaluate to False, non empty strings don't"""
        self.failUnless(self.myop("") == False)
        self.failUnless(self.myop("   ") == True)


class Test_DeferIn(unittest.TestCase):

    def setUp(self):
        self.mysearch = DeferIn()

    def test_eq(self):
        """Searching x in y, y is a list"""
        op = self.mysearch == (1, 2, 3)
        self.failUnless(op(2) == True)
        self.failUnless(op(4) == False)

    def test_ne(self):
        """Searching x not in y, y is a list"""
        op = self.mysearch != (1, 2, 3)
        self.failUnless(op(4) == True)
        self.failUnless(op(3) == False)


if __name__ == "__main__":
    unittest.main()

