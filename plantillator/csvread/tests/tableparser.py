
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
        self.root = RootType()
        self.dset = DataSet(self.root)
        subtype = self.root._GetChild("test")
        self.data1, self.data2 = self.root(), self.root()
        self.subi1, self.subi2 = subtype(self.data1), subtype(self.data2)
        self.data1.test.add(self.subi1)
        self.data2.test.add(self.subi2)
        self.dset.update((self.data1, self.data2))
        head = [ValidHeader(x) for x in ("test.a", "b", "c", "test.d")]
        self.filt = RowFilter("test", head)

    def test_not_indexes(self):
        self.subi1.a, self.subi1.d = 5, 10
        self.subi2.a, self.subi2.d = 10, 5
        self.assertRaises(SyntaxError, self.filt, self.dset, {'test.a':5})

    def test_index_error(self):
        self.subi1.a, self.subi1.d = 5, 10
        self.subi2.a, self.subi2.d = 10, 5
        self.assertRaises(SyntaxError, self.filt, self.dset,
                          {'test.a': 20, 'test.d': 30})

    def test_single_match(self):
        self.subi1.a, self.subi1.d = 5, 10
        self.subi2.a, self.subi2.d = 10, 5
        result = self.filt(self.dset, {'test.a': 10, 'test.d': 5})
        self.failUnless(result == self.subi2)

    def test_double_match(self):
        self.subi1.a, self.subi1.d = 5, 10
        self.subi2.a, self.subi2.d = 10, 5
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
        self.root = RootType()
        self.data = self.root()

    def test_plain(self):
        pars = TableParser(self.data, [ValidHeader("test")])
        self.failUnless(pars.type == self.root._Children["test"])
        self.failIf(pars.path)
        self.failUnless(pars.attr == "test")

    def test_deep_fail(self):
        path = [ValidHeader(x) for x in ("test", "nested")]
        self.assertRaises(SyntaxError, TableParser, self.data, path)
        
    def test_deep_ok(self):
        test = self.root._GetChild("test")
        path = [ValidHeader(x) for x in ("test", "nested")]
        pars = TableParser(self.data, path)
        self.failUnless(pars.type == test._Children["nested"])
        self.failUnless(pars.path == ["test"])
        self.failUnless(pars.attr == "nested")


class TestTableParserCall(TestCase):

    def setUp(self):
        self.root = RootType()
        self.data = self.root()
        self.pars = TableParser(self.data, [ValidHeader("test")])
        self.ok   = 0
        self.item = DataObject(self.data)
        def _block(*arg, **kw):
            self.ok = self.ok + 1
            self.data.test.add(self.item)
        self.pars._block = _block

    def test_call_empty(self):
        dset = self.pars(self.data, "test")
        self.failUnless(dset._type == self.root._Children["test"])
        self.failIf(dset)

    def test_call_once(self):
        self.pars.append(("source", [("blockid", {})]))
        self.pars(self.data, "test")
        self.failUnless(self.ok == 1)

    def test_call_return(self):
        self.pars.append(("source", "block"))
        self.failUnless(self.item in self.pars(self.data, "test"))


if __name__ == "__main__":
    main()
