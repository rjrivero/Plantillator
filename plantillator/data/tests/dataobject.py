#!/usr/bin/env python
# -*- vim: expandtab tabstop=4 shiftwidth=4 smarttab autoindent

from unittest import TestCase, main

try:
    from data.dataobject import DataType, MetaData, Fallback
except ImportError:
    import sys
    sys.path.append("..")
    sys.path.append("../..")
    from data.dataobject import DataType, MetaData, Fallback


class TestDataObject(TestCase):

    def setUp(self):
        self.root = DataType(object)
        self.root._DOMD = MetaData(self.root)
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
        self.assertRaises(AttributeError, getattr, derived, 'x')

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

    def test_magicattr_fail(self):
        self.assertRaises(AttributeError, getattr, self.data, '__iter__')

    def test_invalid_attrib(self):
        self.assertRaises(AttributeError, getattr, self.data, '_test')

    def test_contains(self):
        self.data.x = 5
        self.failUnless("x" in self.data)

    def test_not_contains(self):
        self.data.x = 5
        self.failIf("y" in self.data)

    def test_iteritems(self):
        self.root._DOMD.attribs.update(('x', 'y', 'z'))
        self.data.x = 1
        self.data.z = 2
        self.data.unknown = 10
        items = self.data.iteritems()
        self.failUnless(items.next() == ('x', 1))
        self.failUnless(items.next() == ('z', 2))
        self.assertRaises(StopIteration, items.next)

    def test_eval_fail(self):
        self.data.item = self.root()
        self.assertRaises(AttributeError, eval, "item.fail", {}, self.data)

    def test_eval_ok(self):
        self.data.item = self.root()
        self.data.item.ok = True
        self.failUnless(eval("item.ok", {}, self.data) is True)

    def test_exec_fail(self):
        self.data.item = self.root()
        try:
            exec "test = item.fail" in {}, self.data
            self.failIf(True)
        except AttributeError:
            pass
        except:
            self.failIf(True)

    def test_exec_ok(self):
        self.data.item = self.root()
        self.data.item.ok = True
        try:
            exec "test = item.ok" in {}, self.data
            self.failUnless(self.data.test is True)
        except:
            self.failIf(True)


class TestFallback(TestCase):

    def setUp(self):
        self.root = DataType(object)
        self.data = self.root()
        self.fb = self.data.fb

    def test_set(self):
        self.fb.x = 5
        self.assertRaises(AttributeError, getattr, self.data, 'x')
        self.failUnless(self.fb.x == 5)

    def test_get(self):
        self.data.x = 10
        self.failUnless(self.fb.x == 10)

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
