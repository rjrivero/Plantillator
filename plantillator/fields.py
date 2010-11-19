#/usr/bin/env python
# -*- coding: cp1252 -*-


from itertools import chain
import re

from .ip import IPAddress
from .meta import Field, BaseSet, BaseList


class IntField(Field):

    def convert(self, data, converter=int):
        try:
            return converter(data) if data else None
        except ValueError:
            return None


class BoolField(Field):

    def convert(self, data,
        truevals  = ("SI", "SÍ", "S", "YES", "Y", "1"),
        falsevals = ("NO", "N", "0")):
        data = data.upper()
        if data in truevals:
            return True
        if data in falsevals:
            return False
        raise ValueError(data)


class StrField(Field):

    def convert(self, data):
        # es increible el p*to excel... la "ntilde" la representa con distintos
        # caracteres en un mismo fichero, y luego al pasarlo a unicode no
        # hay forma de recuperarlo, ni siquiera con "normalize". Asi que
        # cuidado con los identificadores, mejor que sean solo ASCII...
        #return unicodedata.normalize('NFKC', data.strip()) or None
        return data or None


class IPv4Field(Field):

    def convert(self, data, converter=IPAddress):
        if not data:
            return None
        try:
            if data.find("/") < 0:
                # interpreto una direccion "*" como 0.0.0.0/0
                if data == "*":
                    data = "0.0.0.0/0"
                else:
                    data = data + "/32"
            return converter(data)
        except ValueError:
            return None


class IPv6Field(Field):

    def convert(self, data, converter=IPAddress):
        if not data:
            return None
        try:
            if data.find("/") < 0:
                # interpreto una direccion "*" como 0.0.0.0/0
                if data == "*":
                    data = "::0/0"
                else:
                    data = data + "/128"
            return converter(data)
        except ValueError:
            return None


class ListField(Field):

    def __init__(self, nestedfld):
        super(ListField, self).__init__(indexable=False)
        self.nestedfld = nestedfld

    def convert(self, data, converter=BaseList):
        """Interpreta una cadena de caracteres como una lista

        Crea al vuelo una lista a partir de una cadena de caracteres. La cadena
        es un conjunto de valores separados por ','.
        """
        value = (self.nestedfld.convert(i.strip()) for i in data.split(","))
        value = converter(x for x in value if x is not None)
        return value or None

    def dynamic(self, item, attr):
        return BaseList()


class SetField(Field):

    def __init__(self, nestedfld):
        super(SetField, self).__init__(indexable=False)
        self.nestedfld = nestedfld

    def convert(self, data, converter=BaseSet):
        """Interpreta una cadena de caracteres como un set

        Crea al vuelo una lista a partir de una cadena de caracteres. La cadena
        es un conjunto de valores separados por ','.
        """
        value = (self.nestedfld.convert(i.strip()) for i in data.split(","))
        value = converter(x for x in value if x is not None)
        return value or None

    def dynamic(self, item, attr):
        return BaseSet()


class RangeField(Field):

    RANGE = re.compile(r'^(?P<pref>.*[^\d])?(?P<from>\d+)\s*\-\s*(?P<to>\d+)(?P<suff>[^\d].*)?$')

    def __init__(self, nestedfld):
        super(RangeField, self).__init__(indexable=False)
        self.nestedfld = nestedfld

    def convert(self, data, converter=BaseList):
        """Interpreta una cadena de caracteres como un rango

        Crea al vuelo un rango a partir de una cadena de caracteres.
        La cadena es un rango (numeros separados por '-'), posiblemente
        rodeado de un prefijo y sufijo no numerico.
        """
        match, rango = RangeField.RANGE.match(data), []
        if match:
            start = int(match.group('from'))
            stop = int(match.group('to'))
            pref = (match.group('pref') or "").strip()
            suff = (match.group('suff') or "").strip()
            for i in range(start, stop+1):
                value = self.nestedfld.convert("%s%d%s" % (pref, i, suff))
                if value is not None:
                    rango.append(value)
        else:
            value = self.nestedfld.convert(data)
            if value is not None:
                rango.append(value)
        return converter(rango) or None

    def dynamic(self, item, attr):
        return BaseList()


class ListRangeField(RangeField):

    def __init__(self, nestedfld):
        super(ListRangeField, self).__init__(nestedfld)

    def convert(self, data, converter=BaseList):
        """Interpreta una cadena de caracteres como una lista de rangos"""
        ranges = (super(ListRangeField, self).convert(x.strip()) for x in data.split(","))
        ranges = (x for x in ranges if x is not None)
        return converter(chain(*ranges)) or None

    def dynamic(self, item, attr):
        return BaseList()


class ComboField(Field):

    """Un campo que puede tener valores de distintos tipos.

    Va intentando convertir con cada tipo de conversor, hasta que
    encuentre uno que no devuelva None.
    """

    def __init__(self, fields):
        super(ComboField, self).__init__(indexable=False)
        self.fields = fields

    def convert(self, data):
        for f in self.fields:
            val = f.convert(data)
            if val is not None:
                return val


class FieldMap(object):

    ScalarFields = {
        'int': IntField,
        'bool': BoolField,
        'boolean': BoolField,
        'string': StrField,
        'ip': IPv4Field,
        'ipv4': IPv4Field,
        'ipv6': IPv6Field,
    }

    VectorFields = {
        'list': ListField,
        'set': SetField,
        'range': RangeField,
        'rangelist': ListRangeField,
    }

    @classmethod
    def resolve(cls, filtername):
        fields = tuple(cls.resolve_single(f) for f in filtername.split(" OR "))
        if len(fields) == 1:
            return fields[0]
        return ComboField(fields)

    @classmethod
    def resolve_single(cls, filtername):
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
