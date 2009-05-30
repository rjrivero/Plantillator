#!/usr/bin/env python
# -*- vim: expandtab tabstop=4 shiftwidth=4 smarttab autoindent

import unittest
import operator

from helper import tester
from deferop import *


class Test_Normalize(unittest.TestCase):

    def test_empty(self):
        """Empty string normalizes to None"""
        self.failUnless(normalize("") is None)

    def test_space(self):
        """Whitespace string normalizes to None"""
        self.failUnless(normalize("  \t") is None)

    def test_int(self):
        """Numeric string normalizes to int, even with ehitespaces"""
        self.failUnless(normalize("  234\t") == 234)

    def test_string(self):
        """Strings are stripped"""
        self.failUnless(normalize("  hello!\n") == "hello!")

    def test_escape_string(self):
        """Escaped strings are not interpreted"""
        self.failUnless(normalize("'   Hi!\n'") == "   Hi!\n")

    def test_escape_int(self):
        """Escaped integers are not interpreted"""
        self.failUnless(normalize("'25'") == "25")


class Test_AsList(unittest.TestCase):

    def test_singlevalue(self):
        """Single values are stripped and normalized"""
        al = asList("")
        self.failUnless(len(al) == 1)
        self.failUnless(al[0] is None)
        al = asList("  \t")
        self.failUnless(len(al) == 1)
        self.failUnless(al[0] is None)
        al = asList(" 234\t")
        self.failUnless(len(al) == 1)
        self.failUnless(al[0] == 234)
        al = asList(" hello!\n")
        self.failUnless(len(al) == 1)
        self.failUnless(al[0] == "hello!")
        al = asList("'100'")
        self.failUnless(len(al) == 1)
        self.failUnless(al[0] == "100")

    def test_multivalue(self):
        """Multiple values are split by comma"""
        al = asList("  , abc  , 456")
        self.failUnless(len(al) == 3)
        self.failUnless(al[0] is None)
        self.failUnless(al[1] == "abc")
        self.failUnless(al[2] == 456)


class Test_AsRange(unittest.TestCase):

    def test_singlevalue(self):
        """If not a range, return empty list"""
        self.failUnless(len(asRange("  12-abc")) == 0)

    def test_prefix(self):
        """Add prefix to generated range"""
        ranges = asRange("  pref-  1-3 ")
        self.failUnless(len(ranges) == 3)
        self.failUnless(ranges[0] == "pref-  1")
        self.failUnless(ranges[1] == "pref-  2")
        self.failUnless(ranges[2] == "pref-  3")

    def test_suffix(self):
        """Add suffix to generated range"""
        ranges = asRange("  15-16- suff ")
        self.failUnless(len(ranges) == 2)
        self.failUnless(ranges[0] == "15- suff")
        self.failUnless(ranges[1] == "16- suff")

    def test_both(self):
        """Add both prefix and suffix"""
        ranges = asRange("  pre/10-10- post ")
        self.failUnless(len(ranges) == 1)
        self.failUnless(ranges[0] == "pre/10- post")

    def test_several(self):
        """If several ranges, just expand the last one"""
        ranges = asRange("first:0-9/second:1-3/third:18-19")
        self.failUnless(len(ranges) == 2)
        self.failUnless(ranges[0] == "first:0-9/second:1-3/third:18")
        self.failUnless(ranges[1] == "first:0-9/second:1-3/third:19")

    def test_invalid(self):
        """If range is invalid, return empty list"""
        self.failUnless(len(asRange("5-4")) == 0)


class Test_IterWrapper(unittest.TestCase):

    def compare(self, list1, list2):
        """Compare two lists item by item"""
        l1 = tuple(list1)
        l2 = tuple(list2)
        if len(l1) != len(l2):
            return False
        for x, y in zip(l1, l2):
            if x != y: return False
        return True
        
    def test_int(self):
        """Wrap an int into a list"""
        self.failUnless(self.compare(iterWrapper(5), (5,)))

    def test_string(self):
        """Wrap an int into a list"""
        self.failUnless(self.compare(iterWrapper("hi"), ("hi",)))

    def test_dict(self):
        """Wrap a dict into a list"""
        d = {'key1': 'val1', 'key2': 'val2'}
        self.failUnless(self.compare(iterWrapper(d), (d,)))

    def test_tuple(self):
        """Leave tuples as-is"""
        t = tuple(('a', 'b', 'c'))
        self.failUnless(self.compare(iterWrapper(t), t))

    def test_list(self):
        """Leave lists as-is"""
        l = list(('x', 'y', 'z'))
        self.failUnless(self.compare(iterWrapper(l), l))

    def test_scopedict(self):
        """Wrap scopedicts into a list"""
        sd = ScopeDict(ScopeType())
        sd['key'] = 'val'
        self.failUnless(self.compare(iterWrapper(sd), (sd,)))


class Test_UnaryOperator(unittest.TestCase):

    def test_call(self):
        """Raise NotImplementedError"""
        op = UnaryOperator()
        self.assertRaises(NotImplementedError, op, None)


class Test_DeferredOperation(unittest.TestCase):

    def setUp(self):
        self.first, self.second = None, None
        self.deferred = DeferredOperation(self.myop, "second")

    def myop(self, first, second):
        self.first = first
        self.second = second

    def test_construct(self):
        self.failUnless(self.deferred.operator == self.myop)
        self.failUnless(self.deferred.operand == "second")

    def test_deferred(self):
        """Operator is called with operands in the right order"""
        self.deferred("first")
        self.failUnless(self.first == "first")
        self.failUnless(self.second == "second")


class Test_DeferredAny(unittest.TestCase):

    def setUp(self):
        self.deferred = DeferredOperation(operator.ge, 10)
        self.deferredany = DeferredAny(self.deferred)

    def test_construct(self):
        self.failUnless(self.deferredany.operator == self.deferred)

    def test_any(self):
        """True if any item matches the criterium"""
        self.failUnless(self.deferredany((5, 10, 15)) == True)

    def test_none(self):
        """False if no item matches"""
        self.failUnless(self.deferredany((6, 7, 8)) == False)


class Test_MyOperator(unittest.TestCase):

    def setUp(self):
        self.myop = MyOperator()

    def test_eq(self):
        """Operator '=='"""
        op = self.myop == "testeq"
        self.failUnless(op("testeq") == True)
        self.failUnless(op("testuneq") == False)

    def test_ne(self):
        """Operator '!='"""
        op = self.myop != "testeq"
        self.failUnless(op("testeq") == False)
        self.failUnless(op("testuneq") == True)

    def test_lt(self):
        """Operator '<'"""
        op = self.myop < 5
        self.failUnless(op(4) == True)
        self.failUnless(op(6) == False)

    def test_le(self):
        """Operator '<='"""
        op = self.myop <= 5
        self.failUnless(op(5) == True)
        self.failUnless(op(6) == False)

    def test_gt(self):
        """Operator '>'"""
        op = self.myop > 10
        self.failUnless(op(11) == True)
        self.failUnless(op(9) == False)

    def test_ge(self):
        """Operator '>='"""
        op = self.myop >= 10
        self.failUnless(op(10) == True)
        self.failUnless(op(8) == False)

    def test_bool_empty(self):
        """Empty lists evaluate to false, non empty lists don't"""
        self.failUnless(self.myop([]) == False)
        self.failUnless(self.myop([None]) == True)

    def test_bool_string(self):
        """Empty strings evaluate to False, non empty strings don't"""
        self.failUnless(self.myop("") == False)
        self.failUnless(self.myop("   ") == True)

    def test_bool_scopedict(self):
        """ScopeDict objects always evaluate to True"""
        self.failUnless(self.myop(ScopeDict(ScopeType())) == True)


class Test_MySearcher(unittest.TestCase):

    def setUp(self):
        self.mysearch = MySearcher()

    def test_eq(self):
        """Searching x in y, y is a list"""
        op = self.mysearch == (1, 2, 3)
        self.failUnless(op(2) == True)
        self.failUnless(op(4) == False)

    def test_ne(self):
        """Searching x not in y, y is a list"""
        op = self.mysearch != (1, 2, 3)
        self.failUnless(op(4) == True)
        self.failUnless(op(3) == False)

    def test_eq_single(self):
        """Searching x in y, y is a single item"""
        op = self.mysearch == "ham"
        self.failUnless(op("ham") == True)
        self.failUnless(op("bread") == False)

    def test_ne_single(self):
        """Searching x not in y, y is a single item"""
        op = self.mysearch != "butter"
        self.failUnless(op("bread") == True)
        self.failUnless(op("butter") == False)

    def test_eq_sd_single(self):
        """Searching x in y, y is a ScopeDict"""
        sd = ScopeDict(ScopeType())
        ot = ScopeDict(ScopeType())
        op = self.mysearch == sd
        self.failUnless(op(sd) == True)
        self.failUnless(op(ot) == False)

    def test_ne_sd_single(self):
        """Searching x not in y, y is a ScopeDict"""
        sd = ScopeDict(ScopeType())
        ot = ScopeDict(ScopeType())
        op = self.mysearch != sd
        self.failUnless(op(ot) == True)
        self.failUnless(op(sd) == False)

    def test_sd_list(self):
        """Search a ScopeDict in a list"""
        sd1, sd2 = ScopeDict(ScopeType()), ScopeDict(ScopeType())
        op = self.mysearch == (sd1, sd2)
        self.failUnless(op(sd1) == True)
        self.failUnless(op(ScopeDict(ScopeType())) == False)


if __name__ == "__main__":
    unittest.main()

