#!/usr/bin/env python


import operator, re


class Resolver(object):

    def __init__(self, symbol):
        self.symbol = symbol

    def _resolve(self, symbol_table):
        return symbol_table[self.symbol]

    def __getattr__(self, attrib):
        if attrib.startswith("_"):
            raise AttributeError(attrib)
        return AttributeResolver(self, attrib)

    def __call__(self, *arg, **kw):
        return CallResolver(self, arg, kw)

    def __add__(self, other):
        return BinaryResolver(self, other, operator.add)

    def __sub__(self, other): 
        return BinaryResolver(self, other, operator.sub)

    def __mul__(self, other):
        return BinaryResolver(self, other, operator.mul)

    def __div__(self, other):
        return BinaryResolver(self, other, operator.div)

    def __floordiv__(self, other):
        return BinaryResolver(self, other, operator.floordiv)

    def __mod__(self, other):
        return BinaryResolver(self, other, operator.mod)

    def IN(self, *arg):
        def is_in(self, other):
            return self in other
        if len(arg) == 1 and (hasattr(arg[0], '_resolve') or hasattr(arg[0], '__contains__')):
            arg = arg[0]
        return BinaryResolver(self, arg, is_in)

    def NOTIN(self, *arg):
        def isNOTIN(self, other):
            return self not in other
        if len(arg) == 1 and (hasattr(arg[0], '_resolve') or hasattr(arg[0], '__contains__')):
            arg = arg[0]
        return BinaryResolver(self, arg, isNOTIN)

    def IS(self, other):
        return BinaryResolver(self, other, operator.is_)

    def ISNOT(self, other):
        return BinaryResolver(self, other, operator.is_not)

    def MATCH(self, other):
        # optimizacion: pre-compilo las regexps que me dan como texto.
        if isinstance(other, basestring):
            regexp = re.compile(other)
            def is_match(self):
                return bool(regexp.search(self))
            return UnaryResolver(self, is_match)
        else:
            def is_match(self, other):
                regexp = re.compile(other)
                return bool(regexp.search(self))
            return BinaryResolver(self, other, is_match)

    def __lt__(self, other): 
        # mini-especializacion: cuando se compara con un literal de
        # cadena, menor significa "endswith")
        if isinstance(other, basestring):
            def operation(this, other):
                return this.lower().endswith(other)
            return LogicalResolver(self, other.lower(), operation)
        return LogicalResolver(self, other, operator.lt)

    def __le__(self, other):
        # mini-especializacion: cuando se compara con un literal de
        # cadena, menor significa "endswith")
        if isinstance(other, basestring):
            def operation(this, other):
                return this.lower().endswith(other)
            return LogicalResolver(self, other.lower(), operation)
        return LogicalResolver(self, other, operator.le)

    def __eq__(self, other):
        return LogicalResolver(self, other, operator.eq)

    def __ne__(self, other):
        return LogicalResolver(self, other, operator.ne)

    def __gt__(self, other):
        # mini-especializacion: cuando se compara con un literal de
        # cadena, mayor significa "startswith")
        if isinstance(other, basestring):
            def operation(this, other):
                return this.lower().startswith(other)
            return LogicalResolver(self, other.lower(), operation)
        return LogicalResolver(self, other, operator.gt)

    def __ge__(self, other):
        # mini-especializacion: cuando se compara con un literal de
        # cadena, mayor significa "startswith")
        if isinstance(other, basestring):
            def operation(this, other):
                return this.lower().startswith(other)
            return LogicalResolver(self, other.lower(), operation)
        return LogicalResolver(self, other, operator.ge)

    def __pos__(self):
        return UnaryResolver(self, operator.pos)


class ChainedResolver(Resolver):

    def __init__(self, parent, **kw):
        self.__dict__.update(kw)
        self.parent = parent


class AttributeResolver(ChainedResolver):

    def __init__(self, parent, attrib):
        super(AttributeResolver, self).__init__(parent, attrib=attrib)

    def _resolve(self, symbol_table):
        return getattr(self.parent._resolve(symbol_table), self.attrib)


class CallResolver(ChainedResolver):

    def __init__(self, parent, arg, kw):
        super(CallResolver, self).__init__(parent, arg=arg, kw=kw)

    def _resolve(self, symbol_table):
        return self.parent._resolve(symbol_table)(*self.arg, **self.kw)


class BinaryResolver(ChainedResolver):

    def __init__(self, parent, other, op):
        super(BinaryResolver, self).__init__(parent, other=other, op=op)

    def _resolve(self, symbol_table):
        this, other = self.parent._resolve(symbol_table), self.other
        if hasattr(other, '_resolve'):
            other = other._resolve(symbol_table)
        return self.op(this, other)


class UnaryResolver(ChainedResolver):

    def __init__(self, parent, op):
        super(UnaryResolver, self).__init__(parent, op=op)

    def _resolve(self, symbol_table):
        return self.op(self.parent._resolve(symbol_table))


class LogicalResolver(ChainedResolver):

    def __init__(self, parent, other, op):
        super(LogicalResolver, self).__init__(parent, other=other, op=op)

    def _resolve(self, symbol_table):
        this, other = self.parent._resolve(symbol_table), self.other
        if hasattr(other, '_resolve'):
            other = other._resolve(symbol_table)
        if hasattr(this, '__iter__'):
            # Los operadores de comparacion no funcionan con listas. En ese
            # caso, lo que comparo es la longitud.
            this = len((this if hasattr(this, "__len__") else tuple(this)))
        return self.op(this, other)


if __name__ == "__main__":

    import unittest

    class ResolveTest(unittest.TestCase):

        def setUp(self):
            self.r = Resolver('self')

        def resolve(self, resolver, **kw):
            class X(object):
                pass
            x = X()
            for name, val in kw.iteritems():
                setattr(x, name, val)
            symbols = {'self': x}
            return resolver._resolve(symbols)

        def testAttr(self):
            self.failUnless(self.resolve(self.r.dummy, dummy=10) == 10)

        def testCall(self):
            arg, kw = [], {}
            def test(*a, **k):
                arg.extend(a)
                kw.update(k)
            self.resolve(self.r.test(1, dummy=2), test=test)
            self.failUnless(arg[0] == 1)
            self.failUnless(kw['dummy'] == 2)

        def testAdd(self):
            self.failUnless(self.resolve(self.r.x+5, x=10) == 15)
            self.failUnless(self.resolve(self.r.x+self.r.y, x=10, y=20) == 30)

        def testSub(self):
            self.failUnless(self.resolve(self.r.y-5, y=10) == 5)
            self.failUnless(self.resolve(self.r.y-self.r.z, y=10, z=10) == 0)

        def testMul(self):
            self.failUnless(self.resolve(self.r.z*2, z=8) == 16)
            self.failUnless(self.resolve(self.r.z*self.r.a, z=8, a=4) == 32)

        def testDiv(self):
            self.failUnless(self.resolve(self.r.a/5, a=20) == 4)
            self.failUnless(self.resolve(self.r.a/self.r.b, a=20, b=2) == 10)

        def testFloorDiv(self):
            self.failUnless(self.resolve(self.r.b//5, b=43) == 8)
            self.failUnless(self.resolve(self.r.b//self.r.c, b=43, c=10) == 4)

        def testMod(self):
            self.failUnless(self.resolve(self.r.c%5, c=44) == 4)
            self.failUnless(self.resolve(self.r.c%self.r.d, c=44, d=7) == 2)

        def testPos(self):
            self.failUnless(self.resolve(+self.r.d, d=-5) == -5)

        def testIn(self):
            self.failUnless(self.resolve(self.r.e.IN (1, 2, 3), e=5) == False)
            self.failUnless(self.resolve(self.r.e.IN (1, 2, 3), e=1) == True)
            self.failUnless(self.resolve(self.r.e.IN ((1, 2, 3)), e=6) == False)
            self.failUnless(self.resolve(self.r.e.IN ((1, 2, 3)), e=2) == True)
            self.failUnless(self.resolve(self.r.e.IN (self.r.f), e=5, f=(1,2,3)) == False)
            self.failUnless(self.resolve(self.r.e.IN (self.r.f), e=1, f=(1,2,3)) == True)

        def testNotIn(self):
            self.failUnless(self.resolve(self.r.e.NOTIN (1, 2, 3), e=5) == True)
            self.failUnless(self.resolve(self.r.e.NOTIN (1, 2, 3), e=1) == False)
            self.failUnless(self.resolve(self.r.e.NOTIN ((1, 2, 3)), e=6) == True)
            self.failUnless(self.resolve(self.r.e.NOTIN ((1, 2, 3)), e=2) == False)
            self.failUnless(self.resolve(self.r.e.NOTIN (self.r.f), e=6, f=(1,2,3)) == True)
            self.failUnless(self.resolve(self.r.e.NOTIN (self.r.f), e=2, f=(1,2,3)) == False)

        def testIs(self):
            self.failUnless(self.resolve(self.r.f.IS(None), f=None) == True)
            self.failUnless(self.resolve(self.r.f.IS(None), f=0) == False)
            self.failUnless(self.resolve(self.r.f.IS(self.r.g), f=None, g=None) == True)
            self.failUnless(self.resolve(self.r.f.IS(self.r.g), f=0, g=None) == False)

        def testIsNot(self):
            self.failUnless(self.resolve(self.r.f.ISNOT(None), f=None) == False)
            self.failUnless(self.resolve(self.r.f.ISNOT(None), f=0) == True)
            self.failUnless(self.resolve(self.r.f.ISNOT(self.r.g), f=None, g=None) == False)
            self.failUnless(self.resolve(self.r.f.ISNOT(self.r.g), f=0, g=None) == True)

        def testMatch(self):
            self.failUnless(self.resolve(self.r.g.MATCH("n?ena"), g="antena") == True)
            self.failUnless(self.resolve(self.r.g.MATCH("pp"), g="luisa") == False)
            self.failUnless(self.resolve(self.r.g.MATCH(self.r.h), g="antena", h="n?ena") == True)
            self.failUnless(self.resolve(self.r.g.MATCH(self.r.h), g="luisa", h="pp") == False)

        def testEq(self):
            self.failUnless(self.resolve(self.r.h == 1, h=1) == True)
            self.failUnless(self.resolve(self.r.h == 5, h=10) == False)
            self.failUnless(self.resolve(self.r.h == self.r.i, h=5, i=5) == True)
            self.failUnless(self.resolve(self.r.h == self.r.i, h=10, i=9) == False)
            # comparar strings, comaprten algunos atributos con las listas
            # (__len__) y no otros (__iter__)
            self.failUnless(self.resolve(self.r.h == "pepe", h="pepe") == True)
            self.failUnless(self.resolve(self.r.h == "pepe", h="paco") == False)
            # comparar listas
            self.failUnless(self.resolve(self.r.h == 1, h=(10,)) == True)
            self.failUnless(self.resolve(self.r.h == 5, h=(10,20)) == False)

        def testNe(self):
            self.failUnless(self.resolve(self.r.h != 1, h=1) == False)
            self.failUnless(self.resolve(self.r.h != 5, h=10) == True)
            self.failUnless(self.resolve(self.r.h != self.r.i, h=5, i=5) == False)
            self.failUnless(self.resolve(self.r.h != self.r.i, h=10, i=9) == True)
            # comparar strings, comaprten algunos atributos con las listas
            # (__len__) y no otros (__iter__)
            self.failUnless(self.resolve(self.r.h != "pepe", h="pepe") == False)
            self.failUnless(self.resolve(self.r.h != "pepe", h="paco") == True)
            # comparar listas
            self.failUnless(self.resolve(self.r.h != 1, h=(9,)) == False)
            self.failUnless(self.resolve(self.r.h != 5, h=(9, 18)) == True)

        def testLt(self):
            self.failUnless(self.resolve(self.r.h < 1, h=2) == False)
            self.failUnless(self.resolve(self.r.h < 1, h=1) == False)
            self.failUnless(self.resolve(self.r.h < 5, h=3) == True)
            self.failUnless(self.resolve(self.r.h < self.r.i, h=5, i=3) == False)
            self.failUnless(self.resolve(self.r.h < self.r.i, h=5, i=5) == False)
            self.failUnless(self.resolve(self.r.h < self.r.i, h=9, i=10) == True)
            # comparar listas
            self.failUnless(self.resolve(self.r.h < 1, h=(10, 20)) == False)
            self.failUnless(self.resolve(self.r.h < 1, h=(10,)) == False)
            self.failUnless(self.resolve(self.r.h < 5, h=(9, 18)) == True)

        def testLe(self):
            self.failUnless(self.resolve(self.r.h <= 1, h=2) == False)
            self.failUnless(self.resolve(self.r.h <= 5, h=5) == True)
            self.failUnless(self.resolve(self.r.h <= 5, h=4) == True)
            self.failUnless(self.resolve(self.r.h <= self.r.i, h=5, i=3) == False)
            self.failUnless(self.resolve(self.r.h <= self.r.i, h=10, i=10) == True)
            self.failUnless(self.resolve(self.r.h <= self.r.i, h=9, i=10) == True)
            # comparar listas
            self.failUnless(self.resolve(self.r.h <= 1, h=(5, 10)) == False)
            self.failUnless(self.resolve(self.r.h <= 5, h=(1, 2, 3, 4, 5)) == True)
            self.failUnless(self.resolve(self.r.h <= 5, h=(1, 2, 3, 4)) == True)

        def testGt(self):
            self.failUnless(self.resolve(self.r.h > 1, h=-5) == False)
            self.failUnless(self.resolve(self.r.h > 5, h=5) == False)
            self.failUnless(self.resolve(self.r.h > 5, h=7) == True)
            self.failUnless(self.resolve(self.r.h > self.r.i, h=7, i=11) == False)
            self.failUnless(self.resolve(self.r.h > self.r.i, h=9, i=5) == True)
            # comparar listas
            self.failUnless(self.resolve(self.r.h > 1, h=(-10,)) == False)
            self.failUnless(self.resolve(self.r.h > 5, h=(-1, -2, -3, -4, -5)) == False)
            self.failUnless(self.resolve(self.r.h > 5, h=(-1, -2, -3, -4, -5, -6)) == True)

        def testLe(self):
            self.failUnless(self.resolve(self.r.h >= 9, h=2) == False)
            self.failUnless(self.resolve(self.r.h >= 5, h=5) == True)
            self.failUnless(self.resolve(self.r.h >= 5, h=9) == True)
            self.failUnless(self.resolve(self.r.h >= self.r.i, h=5, i=8) == False)
            self.failUnless(self.resolve(self.r.h >= self.r.i, h=10, i=10) == True)
            self.failUnless(self.resolve(self.r.h >= self.r.i, h=15, i=10) == True)
            # comparar listas
            self.failUnless(self.resolve(self.r.h >= 6, h=(100,200)) == False)
            self.failUnless(self.resolve(self.r.h >= 4, h=(-10, -20, -30, -40, 50)) == True)
            self.failUnless(self.resolve(self.r.h >= 2, h=(-1, 2)) == True)

    class ResolveDepthTest(ResolveTest):

        """Los mismos tests, pero con un nivel adicional de profundidad.

        Lo he incluido porque en la primera version olvide derivar
        ChainedResolver de Resolver (derivaba directamente de object),
        pero los primeros tests no capturaban el fallo.
        """

        def setUp(self):
            self.r = Resolver('self').secondLevel

        def resolve(self, resolver, **kw):
            class X(object):
                pass
            x = X()
            x.secondLevel = X()
            for name, val in kw.iteritems():
                setattr(x.secondLevel, name, val)
            symbols = {'self': x}
            return resolver._resolve(symbols)

    unittest.main()
