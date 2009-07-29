#!/usr/bin/env python
# -*- vim: expandtab tabstop=4 shiftwidth=4 smarttab autoindent


from unittest import TestCase, main

try:
    from plantillator.csvread.parser import *
except ImportError:
    import sys
    sys.path.append("../../..")
    from plantillator.csvread.parser import *
from plantillator.data.pathfinder import StringSource
from plantillator.csvread.csvdata import *
from plantillator.csvread.csvset import *


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
        source = StringSource("test", 
        """test, a , d
               , 5 , 10
           test, a,  d
               , 10, 5
           """)
        self.loader = DataSource()
        self.root = RootType(self.loader)
        self.data = self.root()
        self.loader.read(source, self.data)
        head = [ValidHeader(x) for x in ("test.a", "b", "c", "test.d")]
        self.filt = RowFilter("test", head)
        self.subi1 = +self.data.test(a=5, d=10)
        self.subi2 = +self.data.test(a=10, d=5)

    def test_not_indexes(self):
        self.assertRaises(SyntaxError, self.filt, self.data, {'test.a':5})

    def test_index_error(self):
        self.assertRaises(SyntaxError, self.filt, self.data,
                          {'test.a': 20, 'test.d': 30})

    def test_single_match(self):
        result = self.filt(self.data, {'test.a': 10, 'test.d': 5})
        self.failUnless(+result == self.subi2)

    def test_single_remove_indexes(self):
        data = {'test.a': 10, 'test.d': 5, 'x': 10}
        result = self.filt(self.data, data)
        self.failUnless(len(data) == 1)
        self.failUnless(data['x'] == 10)

    def test_double_match(self):
        match  = lambda x: True
        result = self.filt(self.data, {'test.a': match, 'test.d': match})
        self.failUnless(self.subi1 in result)
        self.failUnless(self.subi2 in result)
        self.failUnless(len(result) == 2)

    def test_no_crit(self):
        header = [ValidHeader(x) for x in ("a", "b", "c", "d")]
        result = RowFilter("test", header)(self.data, {'a':10})
        self.failUnless(self.subi1 in result)
        self.failUnless(self.subi2 in result)
        self.failUnless(len(result) == 2)


class TestTableParserConstruct(TestCase):

    def setUp(self):
        self.root = RootType(DataSource())
        self.data = self.root()

    def test_plain(self):
        pars = TableParser(self.data, [ValidHeader("test")])
        self.failIf(pars.path)
        self.failUnless(pars.attr == "test")

    #def test_deep_fail(self):
    #    path = [ValidHeader(x) for x in ("test", "nested")]
    #    self.assertRaises(SyntaxError, TableParser, self.data, path)
        
    def test_deep_ok(self):
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
        self.loader = DataSource()
        self.root = RootType(self.loader)
        self.data = self.root()
        self.parser = TableParser(self.data, [ValidHeader("test")])
        self.loader["test"] = self.parser

    def test_call_empty(self):
        dset = self.parser(self.data, "test")
        self.failUnless(dset._type == self.root._DOMD.children["test"])
        self.failIf(dset)

    def test_nested_fail(self):
        data = [{'a': 10, 'b': 2, 'c':3, 'e':10}]
        head = [ValidHeader(x) for x in ('a', 'b', 'fail.nested')]
        self.parser.append(("source", Block(head, data)))
        self.assertRaises(DataError, self.parser, self.data, "test")

    def test_does_empty(self):
        data = [{'a': 5, 'b': 3}]
        head = [ValidHeader(x) for x in ('a', 'b', 'c')]
        self.parser.append(("source", Block(head, data)))
        self.parser(self.data, "test")
        self.failIf(self.parser)

    def test_plain(self):
        data = [
           {'a': 10, 'b': 2, 'c':3, 'e':10},
           {'a': 50, 'b': 20, 'h': 5},
           {'a': 20, 'c': 200, 'j': 2}
        ]
        head = [ValidHeader(x) for x in ('a', 'b', 'c')]
        self.parser.append(("source", Block(head, data)))
        self.parser(self.data, "test")
        self.failUnless(len(self.data.test) == 3)
        dmap = dict((d['a'], d) for d in data)
        for item in self.data.test:
            comp = dmap.pop(item.a)
            for key, val in comp.iteritems():
                self.failUnless(item[key] == val)


class TestTableParserCallAppend(TestCase):

    def setUp(self):
        self.loader = DataSource()
        self.root = RootType(self.loader)
        self.data = self.root()
        source = StringSource("test", 
        """test, a , d
               , 5 , 10
               , 10, 5
               , 15, 15 
           """)
        self.loader.read(source, self.data)
        self.path = [ValidHeader(x) for x in ("test", "nested")]
        self.parser = TableParser(self.data, self.path)
        data = [
           {'test.a': 5, 'x': 2, 'y': 5},
           {'test.a': 5, 'x': 5, 'y': 0},
           {'test.a': 10, 'x': 8, 'y': 4}
        ]
        self.head = [ValidHeader(x) for x in ('test.a', 'x', 'y')]
        self.parser.append(("source", Block(self.head, data)))
        self.loader["test.nested"] = self.parser

    def test_not_add_subtype_in_attribs(self):
        testtype = self.data.test(a=5)._type
        self.failIf('nested' in testtype._DOMD.attribs)

    def test_not_add_attribs_before_parsing(self):
        testtype = self.root._DOMD.subtype('test')
        nesttype = testtype._DOMD.subtype('nested')
        self.failIf('x' in nesttype._DOMD.attribs)
        self.failIf('y' in nesttype._DOMD.attribs)

    def test_add_attribs_after_parsing(self):
        subtype = self.data.test(a=5).nested._type
        self.failUnless('x' in subtype._DOMD.attribs)
        self.failUnless('y' in subtype._DOMD.attribs)
        
    def test_nested_missing_key(self):
        data = [{'x': 10, 'y': 2, 'z':10}]
        self.parser.append(("source", Block(self.head, data)))
        item = self.data.test(a=15)
        self.assertRaises(DataError, self.parser, item, "nested")

    def test_nested(self):
        nested1 = self.data.test(a=5).nested
        nested2 = +self.data.test(a=10).nested
        self.failUnless(len(nested1) == 2)
        #self.failUnless(len(nested2) == 1)
        self.failUnless(nested2.x == 8 and nested2.y == 4)
        self.failUnless(+nested1(x=2).y == 5)
        self.failUnless(+nested1(x=5).y == 0)


if __name__ == "__main__":
    main()

