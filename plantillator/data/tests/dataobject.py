#!/usr/bin/env python
# -*- vim: expandtab tabstop=4 shiftwidth=4 smarttab autoindent

from unittest import TestCase, main

try:
    from data.dataobject import *
except ImportError:
    import sys
    sys.path.append("..")
    sys.path.append("../..")
    from data.dataobject import *
from data.dataset import *


class TestDataObject(TestCase):

    def setUp(self):
        self.data = DataObject()

    def test_construct_empty(self):
        data = DataObject()
        self.failUnless(self.data.up is None)

    def test_construct_data(self):
        initial = {
            'a': 5,
            'b': 10
        }
        data = DataObject(None, initial)
        self.failUnless(data.a == 5)
        self.failUnless(data.b == 10)

    def test_up(self):
        derived = DataObject(self.data)
        self.failUnless(derived.up == self.data)

    def test_attrib(self):
        self.data.x = 5
        self.failUnless(self.data.x == 5)

    def test_dict(self):
        self.data["x"] = 10
        self.failUnless(self.data["x"] == 10)

    def test_mixed(self):
        self.data["x"] = 15
        self.failUnless(self.data.x == 15)

    def test_nofallback(self):
        derived = DataObject(self.data)
        self.data.x = 5
        self.assertRaises(AttributeError, getattr, derived, "x")

    def test_fallback(self):
        derived = DataObject(self.data)
        self.data.x = 5
        self.failUnless(derived.fb.x == 5)

    def test_get_hit(self):
        self.data.x = 100
        self.failUnless(self.data.get("x", 5) == 100)

    def test_get_miss(self):
        self.data.x = 100
        self.failUnless(self.data.get("y", 5) == 5)

    def test_setdefault_hit(self):
        self.data.x = 100
        self.failUnless(self.data.setdefault("x", 5) == 100)
        self.failUnless(self.data.x == 100)

    def test_setdefault_miss(self):
        self.data.x = 100
        self.failUnless(self.data.setdefault("y", 5) == 5)
        self.failUnless(self.data.y == 5)

    def test_type(self):
        self.failUnless(self.data._type == DataObject)

    def test_len_empty(self):
        self.failUnless(len(self.data) == 1)

    def test_len_full(self):
        self.data.x = 100
        self.failUnless(len(self.data) == 1)

    def test_iter_is_self(self):
        for item in self.data:
            self.failUnless(item == self.data)

    def test_iter_once(self):
        count = 0
        for item in self.data:
            count = count + 1
        self.failUnless(count == 1)

    def test_adapt_callable(self):
        callme = lambda x: True
        result = self.data._type._adapt({"x": callme})
        self.failUnless("x" in result)
        self.failUnless(len(result) == 1)
        self.failUnless(result["x"] == callme)

    def test_adapt_regular(self):
        result = self.data._type._adapt({"x": 5})
        self.failUnless("x" in result)
        self.failUnless(len(result) == 1)
        self.failUnless(result["x"](10) == False)
        self.failUnless(result["x"](5)  == True)

    def test_adapt_several(self):
        result = self.data._type._adapt({"x": 5, "y": 10})
        self.failUnless("x" in result)
        self.failUnless(len(result) == 2)
        self.failUnless(result["x"](10) == False)
        self.failUnless(result["x"](5)  == True)
        self.failUnless(result["y"](10) == True)
        self.failUnless(result["y"](5)  == False)

    def test_call_True(self):
        callme = lambda x: True
        result = self.data(x=callme)
        self.failUnless(result == self.data)

    def test_call_False(self):
        callme = lambda x: False
        result = self.data(x=callme)
        self.failUnless(isinstance(result, DataSet))
        self.failUnless(result._type == self.data._type)        
        self.failIf(result)

    def test_call_regular_True(self):
        self.data.x = 10
        result = self.data(x=10)
        self.failUnless(result == self.data)

    def test_call_regular_False(self):
        self.data.x = 10
        result = self.data(x=5)
        self.failUnless(isinstance(result, DataSet))
        self.failUnless(result._type == self.data._type)        
        self.failIf(result)


class TestDataType(TestCase):

    def setUp(self):
        self.root = RootType()
        self.data = self.root()

    def test_construct(self):
        self.failUnless(self.root._Parent is None)
        self.failIf(self.root._Children)

    def test_new_child_binding(self):
        child = self.root._GetChild("x")
        self.failUnless("x" in self.root._Children)

    def test_new_child_parent(self):
        child = self.root._GetChild("x")
        self.failUnless(child._Parent == self.root)

    def test_new_child_dataset(self):
        child = self.root._GetChild("x")
        self.failUnless(isinstance(self.data.x, DataSet))
        self.failUnless(self.data.x._type == child)
        self.failIf(self.data.x)


class TestFallback(TestCase):

    def setUp(self):
        self.data = DataObject()
        self.fb = self.data.fb

    def test_set(self):
        self.fb.x = 5
        self.assertRaises(AttributeError, getattr, self.data, "x")
        self.failUnless(self.fb.x == 5)

    def test_get(self):
        self.data.x = 10
        self.failUnless(self.fb.x == 10)

    def test_call(self):
        self.data.x = 10
        self.failUnless(self.data(x=10) == self.data)
        self.failUnless(self.fb(x=10) == self.fb)

    def test_call_deep(self):
        self.data.x = 5
        subitem = DataObject(self.data)
        self.failUnless(self.data(x=5) == self.data)
        self.failIf(subitem(x=5))
        self.failUnless(self.fb(x=5) == self.fb)


if __name__ == "__main__":
    main()
