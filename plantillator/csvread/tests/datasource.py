#!/usr/bin/env python
# -*- vim: expandtab tabstop=4 shiftwidth=4 smarttab autoindent


from unittest import TestCase, main

try:
    from csvread.datasource import *
except ImportError:
    import sys
    sys.path.append("..")
    sys.path.append("../..")
    from csvread.datasource import *
from csvread.tableparser import *
from data.dataobject import *
from data.dataset import *
from data.pathfinder import *


class TestDataSource(TestCase):

    def setUp(self):
        self.loader = DataSource()
        self.root = RootType(self.loader)
        self.data = self.root()

    def test_simple_variables(self):
        source = StringSource("test", 
        """variables, nombre, valor
           ,      test, 5
           ,      me,  10""")
        self.loader.read(source, self.data)
        self.failUnless(self.data.test == 5)
        self.failUnless(self.data.me == 10)

    def test_simple_except(self):
        source = StringSource("test", 
        """variables, nombre, valor
           ,      10, 20""")
        self.assertRaises(DataError, self.loader.read, source, self.data)

    def test_simple_except_lineno(self):
        source = StringSource("test", 
        """variables, name, value
           ,      test, x
           ,       5, fail
           ,      me, ok""")
        try:
            self.loader.read(source, self.data)
            self.failIf(True)
        except DataError as details:
            self.failUnless(details.itemid == 3)

    def test_no_deps(self):
        source = StringSource("test", 
        """simple, x, y
           ,      10, 20,
           ,      test, me""")
        deps = self.loader.read(source, self.data)
        self.failIf(deps)

    def test_dependencies(self):
        source = StringSource("test", 
        """dependencias, fichero
           ,      fichero1,
           ,      fichero2""")
        deps = self.loader.read(source, self.data)
        self.failUnless(len(deps) == 2)
        self.failUnless("fichero1" in deps)
        self.failUnless("fichero2" in deps)

    def test_invalid_header(self):
        source = StringSource("test", 
        """variables, name
           ,      test, x""")
        self.assertRaises(DataError, self.loader.read, source, self.data)

    
if __name__ == "__main__":
    main()
