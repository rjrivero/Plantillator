#/usr/bin/env python


from itertools import chain
import re


from .ip import IPAddress
from .meta import Field, BaseSet, BaseList, PeerSet


class IntField(Field):

    def convert(self, data):
        try:
            return int(data) if data.strip() else None
        except ValueError:
            return None


class StrField(Field):

    def convert(self, data):
        # es increible el p*to excel... la "ntilde" la representa con distintos
        # caracteres en un mismo fichero, y luego al pasarlo a unicode no
        # hay forma de recuperarlo, ni siquiera con "normalize". Asi que
        # cuidado con los identificadores, mejor que sean solo ASCII...
        #return unicodedata.normalize('NFKC', data.strip()) or None
        return data.strip() or None


class IPField(Field):

    def convert(self, data):
        if not data.strip():
            return None
        try:
            if data.find("/") < 0:
                data = data + "/32"
            return IPAddress(data)
        except ValueError:
            return None


class ObjectField(Field):

    def collect(self, items):
        return PeerSet(items)


class ListField(Field):

    def __init__(self, nestedfld):
        super(ListField, self).__init__(indexable=False)
        self.nestedfld = nestedfld

    def convert(self, data):
        """Interpreta una cadena de caracteres como una lista

        Crea al vuelo una lista a partir de una cadena de caracteres. La cadena
        es un conjunto de valores separados por ','.
        """
        value = (self.nestedfld.convert(i) for i in data.split(","))
        value = BaseList(x for x in value if x is not None)
        return value or None


class SetField(Field):

    def __init__(self, nestedfld):
        super(SetField, self).__init__(indexable=False)
        self.nestedfld = nestedfld

    def convert(self, data):
        """Interpreta una cadena de caracteres como un set

        Crea al vuelo una lista a partir de una cadena de caracteres. La cadena
        es un conjunto de valores separados por ','.
        """
        value = (self.nestedfld.convert(i) for i in data.split(","))
        value = BaseSet(x for x in value if x is not None)
        return value or None


class RangeField(Field):

    RANGE = re.compile(r'^(?P<pref>.*[^\d])?(?P<from>\d+)\s*\-\s*(?P<to>\d+)(?P<suff>[^\d].*)?$')

    def __init__(self, nestedfld):
        super(RangeField, self).__init__(indexable=False)
        self.nestedfld = nestedfld

    def convert(self, data):
        """Interpreta una cadena de caracteres como un rango

        Crea al vuelo un rango a partir de una cadena de caracteres.
        La cadena es un rango (numeros separados por '-'), posiblemente
        rodeado de un prefijo y sufijo no numerico.
        """
        match, rango = RangeField.RANGE.match(data), []
        if match:
            start = int(match.group('from'))
            stop = int(match.group('to'))
            pref = match.group('pref') or ""
            suff = match.group('suff') or ""
            for i in range(start, stop+1):
                value = self.nestedfld.convert("%s%d%s" % (pref, i, suff))
                if value is not None:
                    rango.append(value)
        else:
            value = self.nestedfld.convert(data)
            if value is not None:
                rango.append(value)
        return BaseList(rango) or None


class ListRangeField(RangeField):

    def __init__(self, nestedfld):
        super(ListRangeField, self).__init__(nestedfld)

    def convert(self, data):
        """Interpreta una cadena de caracteres como una lista de rangos"""
        ranges = (super(ListRangeField, self).convert(x) for x in data.split(","))
        ranges = (x for x in ranges if x is not None)
        return BaseList(chain(*ranges)) or None


class FieldMap(object):

    ScalarFields = {
        'int': IntField,
        'string': StrField,
        'ip': IPField,
    }

    VectorFields = {
        'list': ListField,
        'set': SetField,
        'range': RangeField,
        'rangelist': ListRangeField,
    }

    @classmethod
    def resolve(cls, filtername):
        try:
            vector, scalar = filtername.split(".")
        except ValueError:
            vector, scalar = None, filtername
        try:
            if vector:
                vector = cls.VectorFields[vector.strip().lower()]
            scalar = cls.ScalarFields[scalar.strip().lower()]
            return scalar() if not vector else vector(scalar())
        except KeyError:
            raise ValueError(filtername)

        
if __name__ == "__main__":

    import unittest

    class TestField(unittest.TestCase):

        def testInt(self):
            field = FieldMap.resolve('Int')
            self.failUnless(field.convert("  5 ") == 5)
            self.failUnless(field.convert("  ") is None)
            self.assertRaises(ValueError, field.convert, "a")

        def testString(self):
            field = FieldMap.resolve('String')
            self.failUnless(field.convert("  abc ") == "abc")
            self.failUnless(field.convert("   ") is None)

        def testIP(self):
            field = FieldMap.resolve('IP')
            self.failUnless(field.convert("  1.2.3.4 /24 ") == IPAddress("1.2.3.4/24"))
            self.failUnless(field.convert("  10.10.10.1  ") == IPAddress("10.10.10.1/32"))
            self.failUnless(field.convert("") is None)

        def testListInt(self):
            field = FieldMap.resolve('list.Int')
            self.assertRaises(ValueError, field.convert, "  a, b, c ")
            self.failUnless(field.convert("  5, 6  ") == (5, 6))
            self.failUnless(field.convert("  ") is None)

        def testListStr(self):
            field = FieldMap.resolve('List. string')
            self.failUnless(field.convert("  a, b, c ") == ("a", "b", "c"))
            self.failUnless(field.convert("  5  ") == ("5",))
            self.failUnless(field.convert("  ") is None)

        def testListIP(self):
            field = FieldMap.resolve('list.IP')
            self.failUnless(field.convert("  10.1.2.3 ") == (IPAddress("10.1.2.3/32"),))
            self.failUnless(field.convert("  1.1.1.1/10, 2.2.2.2/10  ") == (IPAddress("1.1.1.1/10"), IPAddress("2.2.2.2/10"),))
            self.failUnless(field.convert("") is None)

        def testSetInt(self):
            field = FieldMap.resolve('SET .Int')
            self.assertRaises(ValueError, field.convert, "  a, b, c ")
            self.failUnless(field.convert("  5, 6  ") == frozenset((5, 6)))
            self.failUnless(field.convert("") is None)

        def testSetStr(self):
            field = FieldMap.resolve('SET .String')
            self.failUnless(field.convert("  a, b, c ") == frozenset(("a", "b", "c")))
            self.failUnless(field.convert("  5  ") == frozenset(("5",)))
            self.failUnless(field.convert("  ") is None)

        def testSetIP(self):
            field = FieldMap.resolve('SET .IP')
            f1 = field.convert("  1.1.1.1/10, 2.2.2.2/10  ")
            v1 = (IPAddress("1.1.1.1/10"), IPAddress("2.2.2.2/10"))
            for ip in f1:
                self.failUnless(any(ip == x for x in v1))
            f2 = field.convert("  10.1.2.3 ")
            self.failUnless(+f2 == IPAddress("10.1.2.3/32"))

        def testRangeInt(self):
            field = FieldMap.resolve('range.Int')
            self.failUnless(field.convert(" 2 - 5  ") == ((2, 3, 4, 5)))
            self.failUnless(field.convert(" 10  ") == (10,))
            self.failUnless(field.convert("  ") is None)

        def testRangeStr(self):
            field = FieldMap.resolve('range.string')
            self.failUnless(field.convert("  a 1-3 b") == ("a 1 b", "a 2 b", "a 3 b"))
            self.failUnless(field.convert(" a10b  ") == ("a10b",))
            self.failUnless(field.convert("  ") is None)

        def testListRangeInt(self):
            field = FieldMap.resolve('rangelist.Int')
            self.failUnless(field.convert("1-3") == (1,2,3))
            self.failUnless(field.convert("   1-3, 6-9") == (1,2,3,6,7,8,9))
            self.failUnless(field.convert(" 9, 11  ") == (9, 11))
            self.failUnless(field.convert(" ") is None)
            
        def testListRangeStr(self):
            field = FieldMap.resolve('rangelist.string')
            self.failUnless(field.convert("1-3") == ("1","2","3"))
            self.failUnless(field.convert("   a1-3, 6-7b") == ("a1","a2","a3","6b","7b"))
            self.failUnless(field.convert(" a9, 11b  ") == ("a9", "11b"))
            self.failUnless(field.convert("") is None)

    unittest.main()
