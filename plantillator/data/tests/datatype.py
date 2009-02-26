#!/usr/bin/env python
# -*- vim: expandtab tabstop=4 shiftwidth=4 smarttab autoindent


from unittest import TestCase, main

from tests.helper import *
from data.datatype import *


class Test_DataType_Construct(TestCase):
    
    def test_construct(self):
        dt = DataType()
        self.failIf(dt.blocked)
        self.failIf(dt.subtypes)
        self.failIf(dt.up)

    def test_construct_parent(self):
        up = DataType()
        dt = DataType(up)
        self.failIf(dt.blocked)
        self.failIf(dt.subtypes)
        self.failUnless(dt.up == up)


#------------------------
# Test add_field function
#------------------------

AddFieldTests = [
    # arguments to add  |  expected field name | blocked?
    (("field", True),      "field",              True),
    (("field",),           "field",              True),
    (("field", False),     "field",              False),
    (("0invalid", True),   None,                 None),
    (("0invalid", False),  None,                 None),
    ((" stripme ", True),  "stripme",            True),
    ((" stripme ", False), "stripme",            False),
    (("", True),           None,                 False),
    (("", False),          None,                 False),
    (("  ", True),         None,                 False),
    (("  ", False),        None,                 False)
]

def addfield_tester(args, result, blocked):
    if blocked is None:
        def test(self):
            self.assertRaises(SyntaxError, self.dt.add_field, *args)
    else:
        def test(self):
            field = self.dt.add_field(*args)
            self.failUnless(field == result)
            self.failUnless((field in self.dt.blocked) == blocked)
    return test
                
class Test_Add(build_tester("AddFieldTester", AddFieldTests, addfield_tester)):
    
    def setUp(self):
        self.dt = DataType()


#------------------------
# Test add_subtype function
#------------------------

AddSubtypeTests = [
    # arguments to add | expected type name
    ("subtype",          "subtype"),
    ("0invalid",         None,),
    (" stripme ",        "stripme"),
    ("",                 None),
    ("  ",               None),
]

def addsubtype_tester(name, result):
    if result is None:
        def test(self):
            self.assertRaises(SyntaxError, self.dt.add_subtype, name)
    else:
        def test(self):
            field, stype = self.dt.add_subtype(name)
            self.failUnless(field == result)
            self.failUnless(field in self.dt.blocked)
            self.failUnless(field in self.dt.subtypes)
            self.failUnless(self.dt.subtypes[field] == stype)
            self.failUnless(stype.up == self.dt)
    return test
                
class Test_Subtype(build_tester("AddSubtypeTester", AddSubtypeTests, addsubtype_tester)):
    
    def setUp(self):
        self.dt = DataType()


#------------------------
# Test addapt function
#------------------------

def imTrue(ignore):
    return True

def imFalse(ignore):
    return False

AdaptTests = [
    # items to addapt |     test value |   test result
    ({"key1": imTrue},      None,          True),
    ({"key2": imFalse},     None,          False),
    ({"key3": 10},          10,            True),
    ({"key4": 10},          5,             False),
    ({"key5": "ok"},        "ok",          True),
    ({"key6": "ok"},        "ko",          False),
    ({"subtypeA": imTrue},  (None, None),  True),
    ({"subtypeB": imFalse}, (None, None),  False),
    ({"subtypeA": 10},      (5, 10),       True),
    ({"subtypeB": 10},      (5, 15),       False),
    ({"subtypeA": "ok"},    ("ok", "ko"),  True),
    ({"subtypeB": "ok"},    ("ko", "KO!"), False)
]

def adapt_tester(kw, value, expected):
    def test(self):
        result = self.dt.adapt(kw)
        self.failUnless(len(result) == 1)
        for key, ignore in kw.iteritems():
            self.failUnless(key in result)
            self.failUnless(result[key](value) == expected)
    return test

def combine_tests():
    for x in range(0, len(AdaptTests)):
        for y in range(x+1, len(AdaptTests)):
            test1 = AdaptTests[x]
            test2 = AdaptTests[y]
            kw1 = test1[0].iteritems().next()
            kw2 = test2[0].iteritems().next()
            if kw1[0] != kw2[0]:
                yield ((kw1, kw2), (test1[1:], test2[1:]))

def combined_tester(kwlist, results):
    def test(self):
        result = self.dt.adapt(dict(kwlist))
        self.failUnless(len(result) == len(kwlist))
        for (key, ignore), (value, expected) in zip(kwlist, results):
            self.failUnless(key in result)
            self.failUnless(result[key](value) == expected)
    return test

class Test_Adapt(
    build_tester("AdaptTester", AdaptTests, adapt_tester),
    build_tester("CombinedTester", combine_tests(), combined_tester)):
    
    def setUp(self):
        self.dt = DataType()
        self.dt.add_subtype("subtypeA")
        self.dt.add_subtype("subtypeB")
