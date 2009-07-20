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
        self.root = RootType(GroupTree())
        self.data = self.root()

    def test_construct_empty(self):
        data = self.root()
        self.failUnless(self.data.up is None)

    def test_construct_data(self):
        initial = {
            'a': 5,
            'b': 10
        }
        data = self.root(None, initial)
        self.failUnless(data.a == 5)
        self.failUnless(data.b == 10)

    def test_up(self):
        derived = self.root(self.data)
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
        derived = self.root(self.data)
        self.data.x = 5
        self.assertRaises(AttributeError, getattr, derived, "x")

    def test_fallback(self):
        derived = self.root(self.data)
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
        self.failUnless(self.data._type == self.root)

    #def test_len_empty(self):
    #    self.failUnless(len(self.data) == 1)

    #def test_len_full(self):
    #    self.data.x = 100
    #    self.failUnless(len(self.data) == 1)

    #def test_iter_is_self(self):
    #    for item in self.data:
    #        self.failUnless(item == self.data)

    #def test_iter_once(self):
    #    count = 0
    #    for item in self.data:
    #        count = count + 1
    #    self.failUnless(count == 1)

    def test_invalid_attrib(self):
        self.assertRaises(AttributeError, getattr, self.data, "_test")

    def test_contains(self):
        self.data.x = 5
        self.failUnless("x" in self.data)

    def test_not_contains(self):
        self.data.x = 5
        self.failIf("y" in self.data)


class TestDataType(TestCase):

    def setUp(self):
        self.tree = GroupTree({'x': GroupTree()})
        self.root = RootType(self.tree)
        self.data = self.root()

    def test_construct(self):
        self.failUnless(self.root._Parent is None)

    def test_property_single(self):
        data = self.root()
        data.x.add(data.x._type(data, {'y': 10}))
        self.failUnless(+data.x(y=10))

    def test_property_double(self):
        data1 = self.root()
        data2 = self.root()
        data1.x.add(data1.x._type(data1, {'y': 10}))
        data2.x.add(data2.x._type(data2, {'y': 20}))
        self.failUnless(+data1.x(y=10))
        self.failIf(data1.x(y=20))

    def test_new_child_dataset(self):
        self.failUnless(isinstance(self.data.x, DataSet))
        self.failUnless(self.data.x._type._Parent == self.root)
        self.failIf(self.data.x)

    def test_eval(self):
        data = self.root()
        data.x.add(data.x._type(data, {'x': 10, 'y': 5}))
        data["item"] = +data.x(x=10)
        self.assertRaises(AttributeError, eval, "item.fail", {}, data)

    def test_exec(self):
        data = self.root()
        data.x.add(data.x._type(data, {'x': 10, 'y': 5}))
        data["item"] = +data.x(x=10)
        try:
            exec "test = item.fail" in {}, data
            self.failIf(True)
        except AttributeError:
            pass
        except:
            self.failIf(True)


class TestFallback(TestCase):

    def setUp(self):
        self.root = RootType(GroupTree())
        self.data = self.root()
        self.fb = self.data.fb

    def test_set(self):
        self.fb.x = 5
        self.assertRaises(AttributeError, getattr, self.data, "x")
        self.failUnless(self.fb.x == 5)

    def test_get(self):
        self.data.x = 10
        self.failUnless(self.fb.x == 10)

    #def test_call(self):
    #    self.data.x = 10
    #    self.failUnless(+self.data(x=10) == self.data)
    #    self.failUnless(+self.fb(x=10) == self.fb)

    #def test_call_deep(self):
    #    self.data.x = 5
    #    subitem = self.root(self.data)
    #    self.failUnless(+self.data(x=5) == self.data)
    #    self.failIf(subitem(x=5))
    #    self.failUnless(+self.fb(x=5) == self.fb)

    def test_contains(self):
        self.data.x = 5
        self.failUnless("x" in self.data.fb)

    def test_contains_db(self):
        fb = self.data.fb
        fb.x = 10
        self.failUnless("x" in fb)
        self.failIf("x" in self.data)

    def test_not_contains(self):
        self.data.x = 5
        self.failIf("y" in self.data.fb)



if __name__ == "__main__":
    main()
