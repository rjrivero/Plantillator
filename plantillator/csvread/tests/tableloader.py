#!/usr/bin/env python
# -*- vim: expandtab tabstop=4 shiftwidth=4 smarttab autoindent


from unittest import TestCase, main

try:
    from csvread.tableloader import *
except ImportError:
    import sys
    sys.path.append("..")
    sys.path.append("../..")
    from csvread.tableloader import *
from csvread.tableparser import *
from data.dataobject import *
from data.dataset import *
from data.pathfinder import *


class TestBlock(TestCase):

    def test_construct(self):
        headers = ["  a. x", "b  "]
        lines   = [(5, ("x", "y")), (10, ("v", "w"))]
        block   = Block(headers, lines)
        self.failUnless(block.headers == ["a.x", "b"])
        block   = list(block)
        self.failUnless(len(block) == 2)
        self.failUnless(block[0][0] == 5)
        self.failUnless(block[0][1]["a.x"] == "x")
        self.failUnless(block[0][1]["b"] == "y")
        self.failUnless(block[1][0] == 10)
        self.failUnless(block[1][1]["a.x"] == "v")
        self.failUnless(block[1][1]["b"] == "w")

    def test_construct_fail(self):
        headers = ["3845", "dummy"]
        self.assertRaises(ValueError, Block, headers, [])


class TestTableLoaderConstruct(TestCase):

    def test_construct(self):
        loader = TableLoader()
        self.failUnless(loader.root)
        self.failUnless(loader.data)
        

class TestTableLoader(TestCase):

    def setUp(self):
        self.loader = TableLoader()

    def test_simple(self):
        source = StringSource("test", """simple, x, y""")
        self.loader.read(source)
        self.failIf(self.loader)

    def test_simple_property(self):
        source = StringSource("test", 
        """simple, x, y
           ,      10, 20""")
        self.loader.read(source)
        self.failUnless(len(self.loader) == 1)
        self.failUnless("simple" in self.loader)

    def test_simple_except(self):
        source = StringSource("test", 
        """simple, x, y
           ,      10, 20
           fail.5, a, b""")
        self.assertRaises(DataError, self.loader.read, source)

    def test_simple_except_lineno(self):
        source = StringSource("test", 
        """simple, x, y
           ,      10, 20
           fail.5, a, b
           ,       4, 21""")
        try:
            self.loader.read(source)
            self.failIf(True)
        except DataError as details:
            self.failUnless(details.itemid == 3)

    def test_simple_data(self):
        source = StringSource("test", 
        """simple, x, y
           ,      10, 20,
           ,      test, me""")
        self.loader.read(source)
        data = self.loader.data
        self.failUnless(data.simple(x=10).y == 20)
        self.failUnless(data.simple(x="test").y == "me")

    def test_simple_lazy(self):
        source = StringSource("test", 
        """simple, x, y
           ,      10, 20,
           ,      test, me""")
        self.loader.read(source)
        data = self.loader.data
        self.failUnless(len(data._type._Properties) == 0)
        dummy = data.simple
        self.failUnless(len(data._type._Properties) == 1)

    def test_simple_missing(self):
        source = StringSource("test", 
        """simple, x, y, z
           ,      10,  , 20,
           ,      test, me, """)
        self.loader.read(source)
        data = self.loader.data
        self.assertRaises(AttributeError, getattr, data.simple(x=10), "y")
        self.assertRaises(AttributeError, getattr, data.simple(x="test"), "z")

    def test_simple_concat(self):
        source = StringSource("test", 
        """simple, x, y
           ,      100, 150,
           ,        ,   ,
           ,      a, b""")
        self.loader.read(source)
        data = self.loader.data
        self.failUnless(data.simple(x=100).y == 150)
        self.failUnless(data.simple(x="a").y == "b")

    def test_double_empty(self):
        source = StringSource("test", 
        """empty, a, b, 
           simple, x, y
           ,      10, 20""")
        self.loader.read(source)
        self.failUnless(len(self.loader) == 1)
        self.failUnless("simple" in self.loader)

    def test_double_data(self):
        source = StringSource("test", 
        """simple, x, y
           ,      10, 20,
           ,      test, me
           double, a, b, c
           ,       10, , 5""")
        self.loader.read(source)
        data = self.loader.data
        self.failUnless(data.simple(x=10).y == 20)
        self.failUnless(data.simple(x="test").y == "me")
        self.failUnless(data.double(a=10).c == 5)
 
    def test_nested_data(self):
        source = StringSource("test", 
        """parent, x, y
           ,      10, 20,
           ,      test, me
           parent.child, parent.x, b, c
           ,             10,       1, 2
           ,             test,     1, 5  """)
        self.loader.read(source)
        data = self.loader.data
        self.failUnless(data.parent(x=10).child(b=1).c == 2)
        self.failUnless(data.parent(x="test").child(b=1).c == 5)

    def test_nested_norepeat(self):
        source = StringSource("test", 
        """parent, x, y
           ,      10, 20,
           ,      test, me
           parent.child, parent.x, b, c
           ,             10,       1, 2
           ,             test,     1, 5""")
        self.loader.read(source)
        data = self.loader.data
        self.failUnless(len(data.parent(x=10).child) == 1)
        self.failUnless(len(data.parent(x="test").child) == 1)

    def test_nested_lazy(self):
        source = StringSource("test", 
        """super, x, y
           ,      10, 20,
           super.sub, super.x, b, c
           ,            10,    11, 22
           super.sub2, super.x, m, n
           ,            10,     5, 7""")
        self.loader.read(source)
        data = self.loader.data
        self.failUnless(len(data._type._Properties) == 0)
        dummy = data.super
        self.failUnless(len(data._type._Properties) == 1)
        self.failUnless(len(data.super._type._Properties) == 0)
        dummy = data.super.sub
        self.failUnless(len(data.super._type._Properties) == 1)
        dummy = data.super.sub2
        self.failUnless(len(data.super._type._Properties) == 2)

    def test_nested_except(self):
        source = StringSource("test", 
        """super, x, y
           ,      10, 20,
           super.sub, super.x, b, c
           ,           fail,  11, 22""")
        self.loader.read(source)
        data = self.loader.data
        self.assertRaises(DataError, getattr, data.super, "sub")


if __name__ == "__main__":
    main()
