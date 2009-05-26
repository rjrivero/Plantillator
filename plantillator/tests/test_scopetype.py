#!/usr/bin/env python
# -*- vim: expandtab tabstop=4 shiftwidth=4 smarttab autoindent

import unittest
import operator

from helper import tester
from scopetype import ScopeType
from deferop import *


class Test_ScopeType_Construct(unittest.TestCase):

    def test_construct_empty(self):
        """construction and default values"""
        mytype = ScopeType()
        self.failUnless(mytype.up is None)
	self.check_common(mytype)

    def test_construct_parent(self):
        """construction with a given parent"""
        parenttype = ScopeType()
        childtype = ScopeType(parenttype)
        self.failUnless(childtype.up == parenttype)
	self.check_common(childtype)

    def check_common(self, mytype):
        self.failUnless(mytype.pkey is None)
        self.failUnless(isinstance(mytype.subtypes, dict))
        self.failUnless(len(mytype.subtypes) == 0)
        self.failUnless(isinstance(mytype.blockset, set))
        self.failUnless(len(mytype.blockset) == 0)


class Test_ScopeType_fieldset(unittest.TestCase):

    def setUp(self):
        self.mytype = ScopeType()

    def compare_sets(self, controlset):
        self.failUnless(len(self.mytype.blockset) == len(controlset))
        self.failIf(self.mytype.blockset.difference(set(controlset)))

    def compare_lists(self, list1, list2):
        self.failUnless(len(list1) == len(list2))
        for i, j in zip(list1, list2):
            self.failIf(i != j)

    def test_pkey(self):
        """Primary key is correctly assigned from first field"""
        self.mytype.fieldset(("key", "field1"))
        self.failUnless(self.mytype.pkey == "key")

    def test_blockset_none(self):
        """Fields are added to the blockset"""
        self.mytype.fieldset(("key", "field1"))
        self.compare_sets(("key", "field1"))

    def test_blockset_field(self):
        """Marked fields are not added to the blockset"""
        self.mytype.fieldset(("key", "field1*"))
        self.compare_sets(("key",))

    def test_blockset_pkey(self):
        """Primary key can be marked to not be added to the blockset"""
        self.mytype.fieldset(("key*", "field1"))
        self.compare_sets(("field1",))

    def test_fallback_pkey(self):
        """Primary key is correctly identified even if not in blockset"""
        self.mytype.fieldset(("key*", "field1"))
        self.failUnless(self.mytype.pkey == "key")

    def test_strip(self):
        """Whitespace removed from field names in blockset"""
        self.mytype.fieldset(("key ", " field1"))
        self.compare_sets(("key", "field1"))

    def test_none(self):
        """Primary key can not be none"""
        self.assertRaises(ValueError, self.mytype.fieldset, ("  ", "field1"))

    def test_return_none(self):
        """Empty fields replaced by None"""
        fset = self.mytype.fieldset(("key", "  ", "field2"))
        self.compare_lists(fset, ("key", None, "field2"))

    def test_return_strip(self):
        """Whitespace removed in returned field names"""
        fset = self.mytype.fieldset(("key ", " field1"))
        self.compare_lists(fset, ("key", "field1"))

    def test_return_blockset_field(self):
        """Marks removed in returned field names"""
        fset = self.mytype.fieldset(("key", "field1*"))
        self.compare_lists(fset, ("key", "field1"))

    def test_return_blockset_pkey(self):
        """Marks removed in returned primary key"""
        fset = self.mytype.fieldset(("key*", "field1"))
        self.compare_lists(fset, ("key", "field1"))

    def test_return_block_strip(self):
        """Both marks and whitespace removed in returned fields"""
        fset = self.mytype.fieldset(("key", " field1* "))
        self.compare_lists(fset, ("key", "field1"))

    def test_overwrite(self):
        """Blockset grows when fields added"""
        fset = self.mytype.fieldset(("key ", " field1 "))
        fset = self.mytype.fieldset((" key", " field2 "))
        self.compare_sets(("key", "field1", "field2"))

    def test_replace_pkey(self):
        """Primary key can not be replaced"""
        fset = self.mytype.fieldset(("key ", " field1 "))
        self.assertRaises(SyntaxError, self.mytype.fieldset, (" newkey", "field2"))


class Test_ScopeType_subtype(unittest.TestCase):

    def setUp(self):
        self.mytype = ScopeType()
        self.subtype = self.mytype.subtype("test")

    def test_subtypes(self):
        """subtype is added to list"""
	self.failUnless(self.mytype.subtypes["test"] == self.subtype)

    def test_blocklist(self):
        """subtype is added to blocklist"""
        self.failUnless(self.mytype.blockset.pop() == "test")

    def test_parent(self):
        """subtype has right parent"""
        self.failUnless(self.subtype.up == self.mytype)


class Test_ScopeType_normcrit(unittest.TestCase):

    def setUp(self):
        self.mytype = ScopeType()
        self.mytype.fieldset(("key", "field1"))
        self.mytype.subtype("field2")

    def check_true(self, crit, **kw):
        self.failUnless(len(crit) == len(kw))
        self.failUnless(all(crit[x](y) for x, y in kw.iteritems()))

    def check_false(self, crit, **kw):
        self.failUnless(len(crit) == len(kw))
        self.failUnless(all(not crit[x](y) for x, y in kw.iteritems()))

    def test_empty_pkey(self):
        """No Pkey raises a KeyError"""
        self.assertRaises(KeyError, ScopeType().normcrit, (5,), {})

    def test_args(self):
        """More than one positional argument raises a ValueError"""
        self.assertRaises(ValueError, self.mytype.normcrit, (5,6,), {})

    def test_arg(self):
        """normcrit called with a single positional argument"""
        crit = self.mytype.normcrit((5,), {})
        self.check_true(crit, key=5)
        self.check_false(crit, key=6)

    def test_kw(self):
        """Normalization of not not-UnaryOperator crit"""
        crit = self.mytype.normcrit(tuple(), {'field1': "val1"})
        self.check_true(crit, field1="val1")
        self.check_false(crit, field1="val2")

    def test_arg_unary(self):
        """Normalization of UnaryOperator crit as positional argument"""
        crit = self.mytype.normcrit((DeferOp()>10,), {})
        self.check_true(crit, key=15)
        self.check_false(crit, key=5)

    def test_kw_unary(self):
        """Normalization of UnaryOperator crit as keyword argument"""
        crit = self.mytype.normcrit(tuple(), {'field1': DeferOp()<10})
        self.check_true(crit, field1=5)
        self.check_false(crit, field1=15)

    def test_arg_kw(self):
        """Both positional and keyword UnaryOperators"""
        crit = self.mytype.normcrit((DeferOp()<10,), {'field1': DeferOp()>10})
        self.check_true(crit, key=5, field1=15)
        self.check_false(crit, key=15, field1=5)
        

    def test_sublist(self):
        """Searching a literal in a sublist attribute"""
        crit = self.mytype.normcrit(tuple(), {'field2': "test"})
        self.check_true(crit, field2=("a", "test"))
        self.check_false(crit, field2=("an", "example"))

    def test_sublist_unary(self):
        """Searching an UnaryOperator in a sublist attribute"""
        crit = self.mytype.normcrit(tuple(), {'field2': DeferOp()>10 })
        self.failUnless(len(crit) == 1)
        self.check_true(crit, field2=(5, 10, 15))
        self.check_false(crit, field2=(2, 4, 6))


if __name__ == "__main__":
    unittest.main()

