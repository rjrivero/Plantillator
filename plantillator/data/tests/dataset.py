#!/usr/bin/env python
# -*- vim: expandtab tabstop=4 shiftwidth=4 smarttab autoindent


import operator
from unittest import TestCase, main

try:
    from data.dataobject import *
except ImportError:
    import sys
    sys.path.append("..")
    sys.path.append("../..")
    from data.dataobject import *
from data.dataset import *


class TestDataSet(TestCase):

    def setUp(self):
        self.root = RootType(GroupTree({'subtype': GroupTree()}))
        self.data = self.root()
        self.dset = DataSet(self.root)
        self.dset.add(self.data)

    def test_construct(self):
        dset = DataSet(self.root)
        self.failUnless(dset._type == self.root)
        self.failIf(dset)

    def test_construct_data(self):
        dset = DataSet(self.root, self.data)
        self.failUnless(self.data in dset)

    def test_add_fail(self):
        subtype = self.root._Properties["subtype"]._type
        other = DataSet(subtype)
        self.assertRaises(TypeError, operator.add, self.dset, other)

    def test_add(self):
        other_data = self.root()
        combined = self.dset + DataSet(self.root, other_data)
        self.failUnless(len(combined) == 2)
        self.failUnless(other_data in combined)
        self.failUnless(self.data in combined)

    def test_up_empty(self):
        subtype = self.root._Properties["subtype"]._type
        dset = DataSet(subtype)
        self.failUnless(isinstance(dset.up, DataSet))
        self.failUnless(dset.up._type == self.root)
        self.failIf(dset.up)

    def test_up(self):
        subtype = self.root._Properties["subtype"]._type
        subitem = subtype(self.data)
        self.data.subtype.add(subitem)
        dset = DataSet(subtype, subitem)
        self.failUnless(len(dset.up) == 1)
        self.failUnless(self.data in dset.up)

    def test_attrib(self):
        self.data.x = 100
        self.failUnless(len(self.dset.x) == 1)
        self.failUnless(100 in self.dset.x)

    def test_attrib_empty(self):
        self.data.x = 10
        self.failUnless(len(self.dset.y) == 0)

    def test_subitem(self):
        subtype = self.root._Properties["subtype"]._type
        data1 = self.root()
        data2 = self.root()
        subitem1 = subtype(data1)
        subitem2 = subtype(data2)
	data1.subtype.add(subitem1)
        data2.subtype.add(subitem2)
        dset = DataSet(self.root, (data1, data2))
        self.failUnless(len(dset.subtype) == 2)
        self.failUnless(subitem1 in dset.subtype)
        self.failUnless(subitem2 in dset.subtype)

    def test_call(self):
        data2 = self.root()
        data3 = self.root()
        self.data.x, self.data.y = 5, 10
        data2.x, data2.y = 5, 15
        data3.x, data3.y = 15, 10
        self.dset.update((data2, data3))
        result2 = self.dset(x=5)
        result3 = self.dset(y=10)
        self.failUnless(len(result2) == 2)
        self.failUnless(len(result3) == 2)
        self.failUnless(self.data in result2 and self.data in result3)
        self.failUnless(data2 in result2)
        self.failUnless(data3 in result3)

    def test_call_unpack(self):
        self.data.x = 10
        self.failUnless(self.dset(x=10) == self.data)

    def test_call_True(self):
        crit = lambda x: True
        self.failUnless(self.dset(x=crit) == self.data)

    def test_call_False(self):
        crit = lambda x: False
        self.failIf(self.dset(x=crit))

    def test_call_type(self):
        crit = lambda x: False
        self.failIf(self.dset(x=crit)._type != self.root)


if __name__ == "__main__":
    main()
