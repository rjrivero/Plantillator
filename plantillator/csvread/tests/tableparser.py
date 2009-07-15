#!/usr/bin/env python
# -*- vim: expandtab tabstop=4 shiftwidth=4 smarttab autoindent


from unittest import TestCase, main

try:
    from csvread.tableparser import *
except ImportError:
    import sys
    sys.path.append("..")
    sys.path.append("../..")
    from csvread.tableparser import *
from data.dataobject import *
from data.dataset import *


class TestValidHeader(TestCase):

    def test_single(self):
        v = ValidHeader("testme")
        self.failUnless(v == "testme")
        self.failUnless(v.suffix == "testme")
        self.failUnless(v.prefix is None)

    def test_double(self):
        v = ValidHeader("testme.attrib")
        self.failUnless(v == "testme.attrib")
        self.failUnless(v.suffix == "attrib")
        self.failUnless(v.prefix == "testme")

    def test_single_ws(self):
        v = ValidHeader("  testme  ")
        self.failUnless(v == "testme")
        self.failUnless(v.suffix == "testme")
        self.failUnless(v.prefix is None)

    def test_double_ws(self):
        v = ValidHeader(" testme .   attrib")
        self.failUnless(v == "testme.attrib")
        self.failUnless(v.suffix == "attrib")
        self.failUnless(v.prefix == "testme")

    def test_single_invalid(self):
        self.assertRaises(ValueError, ValidHeader, " 4test")

    def test_double_invalid(self):
        self.assertRaises(ValueError, ValidHeader, "test.4attrib")


class TestRowFilterConstruct(TestCase):

    def test_construct_empty(self):
        head = [ValidHeader(x) for x in ("a", "b", "c")]
        copy = head[:]
        filt = RowFilter("test", copy)
        self.failUnless(head == copy)
        self.failIf(filt)

    def test_construct_match(self):
        head = [ValidHeader(x) for x in ("test.a", "b", "c", "test.d")]
        filt = RowFilter("test", head)
        self.failUnless(head == ["b", "c"])
        self.failUnless(len(filt) == 2)
        self.failUnless("test.a" in filt)
        self.failUnless("test.d" in filt)


class TestRowFilter(TestCase):

    def setUp(self):
        self.root = RootType(GroupTree({'test': GroupTree()}))
        self.dset = DataSet(self.root)
        subtype = self.root._Properties['test']._type
        self.data1, self.data2 = self.root(), self.root()
        self.subi1, self.subi2 = subtype(self.data1), subtype(self.data2)
        self.data1.test.add(self.subi1)
        self.data2.test.add(self.subi2)
        self.dset.update((self.data1, self.data2))
        head = [ValidHeader(x) for x in ("test.a", "b", "c", "test.d")]
        self.filt = RowFilter("test", head)
        self.subi1.a, self.subi1.d = 5, 10
        self.subi2.a, self.subi2.d = 10, 5

    def test_not_indexes(self):
        self.assertRaises(SyntaxError, self.filt, self.dset, {'test.a':5})

    def test_index_error(self):
        self.assertRaises(SyntaxError, self.filt, self.dset,
                          {'test.a': 20, 'test.d': 30})

    def test_single_match(self):
        result = self.filt(self.dset, {'test.a': 10, 'test.d': 5})
        self.failUnless(result == self.subi2)

    def test_single_remove_indexes(self):
        data = {'test.a': 10, 'test.d': 5, 'x': 10}
        result = self.filt(self.dset, data)
        self.failUnless(len(data) == 1)
        self.failUnless(data['x'] == 10)

    def test_double_match(self):
        match  = lambda x: True
        result = self.filt(self.dset, {'test.a': match, 'test.d': match})
        self.failUnless(self.subi1 in result)
        self.failUnless(self.subi2 in result)
        self.failUnless(len(result) == 2)

    def test_no_crit(self):
        header = [ValidHeader(x) for x in ("a", "b", "c", "d")]
        result = RowFilter("test", header)(self.dset, {'a':10})
        self.failUnless(self.subi1 in result)
        self.failUnless(self.subi2 in result)
        self.failUnless(len(result) == 2)


class TestTableParserConstruct(TestCase):

    def setUp(self):
        self.root = RootType(GroupTree(
            {'test': GroupTree(
                {'nested': GroupTree()})
            }))
        self.data = self.root()

    def test_plain(self):
        pars = TableParser(self.data, [ValidHeader("test")])
        self.failIf(pars.path)
        self.failUnless(pars.attr == "test")

    #def test_deep_fail(self):
    #    path = [ValidHeader(x) for x in ("test", "nested")]
    #    self.assertRaises(SyntaxError, TableParser, self.data, path)
        
    def test_deep_ok(self):
        test = self.root._Properties["test"]._type
        path = [ValidHeader(x) for x in ("test", "nested")]
        pars = TableParser(self.data, path)
        self.failUnless(pars.path == ["test"])
        self.failUnless(pars.attr == "nested")


class Block(object):
    def __init__(self, headers, data):
        self.headers = headers
        self.data = data
    def __iter__(self):
        return enumerate(self.data)


class TestTableParserCallPlain(TestCase):

    def setUp(self):
        self.root = RootType(GroupTree({'test': GroupTree()}))
        self.data = self.root()
        self.pars = TableParser(self.data, [ValidHeader("test")])

    def test_call_empty(self):
        dset = self.pars(self.data, "test")
        self.failUnless(dset._type == self.root._Properties["test"]._type)
        self.failIf(dset)

    def test_nested_fail(self):
        data = [{'a': 10, 'b': 2, 'c':3, 'e':10}]
        head = [ValidHeader(x) for x in ('a', 'b', 'fail.nested')]
        self.pars.append(("source", Block(head, data)))
        self.assertRaises(DataError, self.pars, self.data, "test")

    #def test_path_fail(self):
    #    self.path = [ValidHeader(x) for x in ("fail", "nested")]
    #    self.assertRaises(SyntaxError, TableParser, self.data, self.path)

    def test_does_empty(self):
        data = [{'a': 5, 'b': 3}]
        head = [ValidHeader(x) for x in ('a', 'b', 'c')]
        self.pars.append(("source", Block(head, data)))
        self.pars(self.data, "test")
        self.failIf(self.pars)

    def test_plain(self):
        data = [
           {'a': 10, 'b': 2, 'c':3, 'e':10},
           {'a': 50, 'b': 20, 'h': 5},
           {'a': 20, 'c': 200, 'j': 2}
        ]
        head = [ValidHeader(x) for x in ('a', 'b', 'c')]
        self.pars.append(("source", Block(head, data)))
        self.pars(self.data, "test")
        self.failUnless(len(self.data.test) == 3)
        dmap = dict((d['a'], d) for d in data)
        for item in self.data.test:
            comp = dmap.pop(item.a)
            for key, val in comp.iteritems():
                self.failUnless(item[key] == val)


class TestTableParserCallAppend(TestCase):

    def setUp(self):
        self.root = RootType(GroupTree(
            {'test': GroupTree(
                {'nested': GroupTree()})
            }))
        self.data = self.root()
        self.path = [ValidHeader(x) for x in ("test", "nested")]
        self.subt = self.root._Properties["test"]._type
        self.pars = TableParser(self.data, self.path)
        self.data.test.add(self.subt(self.data, {'a':1}))
        self.data.test.add(self.subt(self.data, {'a':2}))

    def test_nested_missing(self):
        data = [{'x': 10, 'y': 2, 'z':10}]
        head = [ValidHeader(x) for x in ('x', 'y', 'test.a')]
        self.pars.append(("source", Block(head, data)))
        item = self.data.test(a=1)
        self.assertRaises(DataError, self.pars, item, "nested")

    def test_nested(self):
        data = [
           {'test.a': 1, 'x': 2, 'y': 5},
           {'test.a': 1, 'x': 5, 'y': 0},
           {'test.a': 2, 'x': 8, 'y': 4}
        ]
        head = [ValidHeader(x) for x in ('test.a', 'x', 'y')]
        self.pars.append(("source", Block(head, data)))
        self.pars(self.data.test(a=1), "nested")
        nested1 = self.data.test(a=1).nested
        nested2 = self.data.test(a=2).nested()
        self.failUnless(len(nested1) == 2)
        self.failUnless(len(nested2) == 1)
        self.failUnless(nested2.x == 8 and nested2.y == 4)
        self.failUnless(nested1(x=2).y == 5)
        self.failUnless(nested1(x=5).y == 0)


if __name__ == "__main__":
    main()
