#!/usr/bin/env python
# -*- vim: expandtab tabstop=4 shiftwidth=4 smarttab autoindent

import unittest
import operator

from helper import tester
from scopetype import ScopeType
from scopedict import ScopeDict
from myoperator import *


class Test_ScopeType_Construct(unittest.TestCase):

    def test_construct_empty(self):
        """construction and default values"""
        mytype = ScopeType()
        self.failUnless(mytype.pkey is None)
        self.failUnless(isinstance(mytype.subtypes, dict))
        self.failUnless(len(mytype.subtypes) == 0)
        self.failUnless(isinstance(mytype.blockset, set))
        self.failUnless(len(mytype.blockset) == 0)


class Test_ScopeType_fieldset(unittest.TestCase):

    def setUp(self):
        self.mytype = ScopeType()

    def test_pkey(self):
        """Primary key is correctly assigned from first field"""
        self.mytype.fieldset(("key", "field1"))
        self.failUnless(self.mytype.pkey == "key")

    def test_blockset_none(self):
        """Fields are added to the blockset"""
        self.mytype.fieldset(("key", "field1"))
        self.failUnless(len(self.mytype.blockset) == 2)
        self.failUnless("key" in self.mytype.blockset)
        self.failUnless("field1" in self.mytype.blockset)

    def test_blockset_field(self):
        """Marked fields are not added to the blockset"""
        self.mytype.fieldset(("key", "field1*"))
        self.failUnless(len(self.mytype.blockset) == 1)
        self.failUnless("key" in self.mytype.blockset)

    def test_blockset_pkey(self):
        """Primary key can be marked to not be added to the blockset"""
        self.mytype.fieldset(("key*", "field1"))
        self.failUnless(len(self.mytype.blockset) == 1)
        self.failUnless("field1" in self.mytype.blockset)

    def test_fallback_pkey(self):
        """Primary key is correctly identified even if not in blockset"""
        self.mytype.fieldset(("key*", "field1"))
        self.failUnless(self.mytype.pkey == "key")

    def test_strip(self):
        """Whitespace removed from field names in blockset"""
        self.mytype.fieldset(("key ", " field1"))
        self.failUnless(self.mytype.pkey == "key")
        self.failUnless("field1" in self.mytype.blockset)

    def test_none(self):
        """Primary key can not be none"""
        self.assertRaises(ValueError, self.mytype.fieldset, ("  ", "field1"))

    def test_return_none(self):
        """Empty fields replaced by None"""
        fset = self.mytype.fieldset(("key", "  ", "field2"))
        self.failUnless(fset[0] == "key")
        self.failUnless(fset[1] == None)
        self.failUnless(fset[2] == "field2")
        self.failUnless(len(fset) == 3)

    def test_return_strip(self):
        """Whitespace removed in returned field names"""
        fset = self.mytype.fieldset(("key ", " field1"))
        self.failUnless(fset[0] == "key")
        self.failUnless(fset[1] == "field1")
        self.failUnless(len(fset) == 2)

    def test_return_blockset_field(self):
        """Marks removed in returned field names"""
        fset = self.mytype.fieldset(("key", "field1*"))
        self.failUnless(fset[0] == "key")
        self.failUnless(fset[1] == "field1")
        self.failUnless(len(fset) == 2)

    def test_return_blockset_pkey(self):
        """Marks removed in returned primary key"""
        fset = self.mytype.fieldset(("key*", "field1"))
        self.failUnless(fset[0] == "key")
        self.failUnless(fset[1] == "field1")
        self.failUnless(len(fset) == 2)

    def test_return_block_strip(self):
        """Both marks and whitespace removed in returned fields"""
        fset = self.mytype.fieldset(("key", " field1* "))
        self.failUnless(fset[0] == "key")
        self.failUnless(fset[1] == "field1")
        self.failUnless(len(fset) == 2)

    def test_overwrite(self):
        """Blockset grows when fields added"""
        fset = self.mytype.fieldset(("key ", " field1 "))
        fset = self.mytype.fieldset((" key", " field2 "))
        self.failUnless(len(self.mytype.blockset) == 3)
        self.failUnless("key" in self.mytype.blockset)
        self.failUnless("field1" in self.mytype.blockset)
        self.failUnless("field2" in self.mytype.blockset)

    def test_replace_pkey(self):
        """Primary key can not be replaced"""
        fset = self.mytype.fieldset(("key ", " field1 "))
        self.assertRaises(SyntaxError, self.mytype.fieldset, (" newkey", "field2"))


class Test_ScopeType_addtype(unittest.TestCase):

    def setUp(self):
        self.mytype = ScopeType()

    def test_addtype(self):
        """Addition of a subtype blocks the name"""
        subtype = ScopeType()
        self.mytype.addtype("test", subtype)
        self.failUnless("test" in self.mytype.blockset)
        self.failUnless(self.mytype.subtypes["test"] == subtype)


class Test_ScopeType_fallback(unittest.TestCase):

    def setUp(self):
        self.mytype = ScopeType()
        self.mytype.fieldset(("key", "field1", "field2*"))
        up = {
            'field1': 'up1',
            'field2': 'up2',
            'field3': 'up3',
        }
        up = ScopeDict(self.mytype, up)
        self.scoped = ScopeDict(self.mytype, None, up)

    def test_block_fallback(self):
        """Fallback of blocked fields fails"""
        self.assertRaises(KeyError, self.mytype.fallback, self.scoped, "field1")

    def test_fallback(self):
        """Fallback of explicitly unblocked fields works"""
        self.failUnless(self.mytype.fallback(self.scoped, "field2") == "up2")

    def test_fallback_unknown(self):
        """Fallback of unknown fields works"""
        self.failUnless(self.mytype.fallback(self.scoped, "field3") == "up3")


class Test_ScopeType_normcrit(unittest.TestCase):

    def setUp(self):
        self.mytype = ScopeType()
        self.mytype.fieldset(("key", "field1", "field2*"))

    def test_arg(self):
        """normcrit called with a single positional argument"""
        crit = self.mytype.normcrit((5,), {})
        self.failUnless(len(crit) == 1)
        self.failUnless(isinstance(crit["key"], DeferredOperation))
        self.failUnless(crit["key"].operator == operator.eq)
        self.failUnless(crit["key"].operand == 5)

    def test_args(self):
        """More than one positional argument raises a KeyError"""
        self.assertRaises(KeyError, self.mytype.normcrit, (5,6,), {})

    def test_kw(self):
        """Normalization of not not-UnaryOperator crit"""
        crit = self.mytype.normcrit(tuple(), {'field1': "val1"})
        self.failUnless(len(crit) == 1)
        self.failUnless(isinstance(crit["field1"], DeferredOperation))
        self.failUnless(crit["field1"].operator == operator.eq)
        self.failUnless(crit["field1"].operand == "val1")

    def test_arg_unary(self):
        """Normalization of UnaryOperator crit as positional argument"""
        oper = UnaryOperator()
        crit = self.mytype.normcrit((oper,), {})
        self.failUnless(len(crit) == 1)
        self.failUnless(crit["key"] == oper)

    def test_kw_unary(self):
        """Normalization of UnaryOperator crit as keyword argument"""
        oper = UnaryOperator()
        crit = self.mytype.normcrit(tuple(), {'field2': oper})
        self.failUnless(len(crit) == 1)
        self.failUnless(crit["field2"] == oper)

    def test_arg_kw(self):
        """Both positional and keyword UnaryOperators"""
        oper1 = UnaryOperator()
        oper2 = UnaryOperator()
        crit = self.mytype.normcrit((oper1,), {'field1': oper2})
        self.failUnless(len(crit) == 2)
        self.failUnless(crit["key"] == oper1)
        self.failUnless(crit["field1"] == oper2)

    def test_sublist(self):
        """Searching a literal in a sublist attribute"""
        self.mytype.fieldset(("key", "field1"))
        self.mytype.addtype("field2", ScopeType())
        crit = self.mytype.normcrit(tuple(), {'field2': "test"})
        self.failUnless(len(crit) == 1)
        self.failUnless(isinstance(crit["field2"], DeferredAny))
        self.failUnless(isinstance(crit["field2"].operator, DeferredOperation))
        self.failUnless(crit["field2"].operator.operator == operator.eq)
        self.failUnless(crit["field2"].operator.operand == "test")

    def test_sublist_unary(self):
        """Searching an UnaryOperator in a sublist attribute"""
        self.mytype.fieldset(("key", "field1"))
        self.mytype.addtype("field2", ScopeType())
        oper = UnaryOperator()
        crit = self.mytype.normcrit(tuple(), {'field2': oper})
        self.failUnless(len(crit) == 1)
        self.failUnless(isinstance(crit["field2"], DeferredAny))
        self.failUnless(crit["field2"].operator == oper)


if __name__ == "__main__":
    unittest.main()

