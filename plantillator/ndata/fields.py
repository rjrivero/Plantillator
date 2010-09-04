#/usr/bin/env python


from itertools import chain
import re
import unicodedata

from ip import IPAddress
from meta import Field, BaseSet, BaseList


class IntField(Field):

    def convert(self, data):
        return int(data) if data.strip() else None


class StrField(Field):

    def convert(self, data):
        # es increible el p*to excel... la "ntilde" la representa con distintos
        # caracteres en un mismo fichero, y luego al pasarlo a unicode no
        # hay forma de recuperarlo, ni siquiera con "normalize". Asi que
        # cuidado con los identificadores, mejor que sean solo ASCII...
        #return unicodedata.normalize('NFKC', unicode(data).strip()) or None
        return unicode(data).strip() or None


class IPField(Field):

    def convert(self, data):
        if not data.strip():
            return None
        if data.find(u"/") < 0:
            data = data + u"/32"
        return IPAddress(data)


class ListField(Field):

    def __init__(self, nestedfld):
        super(ListField, self).__init__(indexable=False)
        self.nestedfld = nestedfld

    def convert(self, data):
        """Interpreta una cadena de caracteres como una lista

        Crea al vuelo una lista a partir de una cadena de caracteres. La cadena
        es un conjunto de valores separados por ','.
        """
        value = (self.nestedfld.convert(i) for i in data.split(u","))
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
        value = (self.nestedfld.convert(i) for i in data.split(u","))
        value = BaseSet(x for x in value if x is not None)
        return value or None


class RangeField(Field):

    _RANGO = re.compile(r'^(?P<pref>.*[^\d])?(?P<from>\d+)\s*\-\s*(?P<to>\d+)(?P<suff>[^\d].*)?$')

    def __init__(self, nestedfld):
        super(RangeField, self).__init__(indexable=False)
        self.nestedfld = nestedfld

    def convert(self, data):
        """Interpreta una cadena de caracteres como un rango

        Crea al vuelo un rango a partir de una cadena de caracteres.
        La cadena es un rango (numeros separados por '-'), posiblemente
        rodeado de un prefijo y sufijo no numerico.
        """
        match, rango = RangeField._RANGO.match(data), []
        if match:
            start = int(match.group('from'))
            stop = int(match.group('to'))
            pref = unicode(match.group('pref')) or u""
            suff = unicode(match.group('suff')) or u""
            for i in range(start, stop+1):
                value = self.nestedfld.convert(u"%s%d%s" % (pref, i, suff))
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
        ranges = (super(ListRangeField, self).convert(x) for x in data.split(u","))
        ranges = (x for x in ranges if x is not None)
        return BaseList(chain(*ranges)) or None


class Map(object):

    ScalarFields = {
        'int': IntField,
        'string': StrField,
        'ip': IPField,
    }

    VectorFields = {
        'list': ListField,
        'set': SetField,
        'range': RangeField,
        'list-range': ListRangeField,
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
            return None

        
if __name__ == "__main__":

    import unittest

    class TestField(unittest.TestCase):

        def testInt(self):
            field = Map.resolve('Int')
            self.failUnless(field.convert("  5 ") == 5)
            self.failUnless(field.convert("  ") is None)
            self.assertRaises(ValueError, field.convert, "a")

        def testString(self):
            field = Map.resolve('String')
            self.failUnless(field.convert("  abc ") == u"abc")
            self.failUnless(field.convert("   ") is None)

        def testIP(self):
            field = Map.resolve('IP')
            self.failUnless(field.convert("  1.2.3.4 /24 ") == IPAddress("1.2.3.4/24"))
            self.failUnless(field.convert("  10.10.10.1  ") == IPAddress("10.10.10.1/32"))
            self.failUnless(field.convert("") is None)

        def testListInt(self):
            field = Map.resolve('list.Int')
            self.assertRaises(ValueError, field.convert, "  a, b, c ")
            self.failUnless(field.convert("  5, 6  ") == (5, 6))
            self.failUnless(field.convert("  ") is None)

        def testListStr(self):
            field = Map.resolve('List. string')
            self.failUnless(field.convert("  a, b, c ") == (u"a", u"b", u"c"))
            self.failUnless(field.convert("  5  ") == (u"5",))
            self.failUnless(field.convert("  ") is None)

        def testListIP(self):
            field = Map.resolve('list.IP')
            self.failUnless(field.convert("  10.1.2.3 ") == (IPAddress("10.1.2.3/32"),))
            self.failUnless(field.convert("  1.1.1.1/10, 2.2.2.2/10  ") == (IPAddress("1.1.1.1/10"), IPAddress("2.2.2.2/10"),))
            self.failUnless(field.convert("") is None)

        def testSetInt(self):
            field = Map.resolve('SET .Int')
            self.assertRaises(ValueError, field.convert, "  a, b, c ")
            self.failUnless(field.convert("  5, 6  ") == frozenset((5, 6)))
            self.failUnless(field.convert("") is None)

        def testSetStr(self):
            field = Map.resolve('SET .String')
            self.failUnless(field.convert("  a, b, c ") == frozenset((u"a", u"b", u"c")))
            self.failUnless(field.convert("  5  ") == frozenset((u"5",)))
            self.failUnless(field.convert("  ") is None)

        def testSetIP(self):
            field = Map.resolve('SET .IP')
            f1 = field.convert("  1.1.1.1/10, 2.2.2.2/10  ")
            v1 = (IPAddress("1.1.1.1/10"), IPAddress("2.2.2.2/10"))
            for ip in f1:
                self.failUnless(any(ip == x for x in v1))
            f2 = field.convert("  10.1.2.3 ")
            self.failUnless(+f2 == IPAddress("10.1.2.3/32"))

        def testRangeInt(self):
            field = Map.resolve('range.Int')
            self.failUnless(field.convert(" 2 - 5  ") == ((2, 3, 4, 5)))
            self.failUnless(field.convert(" 10  ") == (10,))
            self.failUnless(field.convert("  ") is None)

        def testRangeStr(self):
            field = Map.resolve('range.string')
            self.failUnless(field.convert("  a 1-3 b") == (u"a 1 b", u"a 2 b", u"a 3 b"))
            self.failUnless(field.convert(" a10b  ") == ("a10b",))
            self.failUnless(field.convert("  ") is None)

        def testListRangeInt(self):
            field = Map.resolve('list-range.Int')
            self.failUnless(field.convert("   1-3, 6-9") == (1,2,3,6,7,8,9))
            self.failUnless(field.convert(" 9, 11  ") == (9, 11))
            self.failUnless(field.convert(" ") is None)
            
        def testListRangeStr(self):
            field = Map.resolve('list-range.string')
            self.failUnless(field.convert("   a1-3, 6-7b") == (u"a1",u"a2",u"a3",u"6b",u"7b"))
            self.failUnless(field.convert(" a9, 11b  ") == (u"a9", u"11b"))
            self.failUnless(field.convert("") is None)

    unittest.main()
