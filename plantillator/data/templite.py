#!/usr/bin/env python

import sys, re, copy, traceback, ast
from collections import namedtuple
from itertools import izip, cycle, chain
from datetime import datetime

try:
    import cPickle as pickle
except ImportError:
    import pickle


class ParseException(Exception):

    """
    Encapsula las excepciones lanzadas durante la compilacion de un template.

    - self.template: plantilla (sin procesar) que ha provocado la excepcion
    - self.exc_info: tupla (tipo, excepcion, traceback)
    """

    def __init__(self, template, exc_info):
        super(ParseException, self).__init__()
        self.template = template
        self.exc_info = exc_info

    def __unicode__(self):
        return u"".join(traceback.format_exception(*(self.exc_info)))

    def __repr__(self):
        return "ParseException(%s, %s)" % (repr(self.template), repr(self.exc_info))


class TemplateException(Exception):

    """
    Encapsula las excepciones lanzadas durante la ejecucion de un template.

    - self.template: plantilla (procesada) que ha provocado la excepcion
    - self.local: diccionario con las variables locales de la plantilla en el
                  momento de la excepcion.
    - self.exc_info: tupla (tipo, excepcion, traceback)
    """

    def __init__(self, template, local, exc_info):
        super(TemplateException, self).__init__()
        self.template = template
        self.local = local
        self.exc_info = exc_info

    def __unicode__(self):
        return u"".join(traceback.format_exception(*(self.exc_info)))

    def __repr__(self):
        return "TemplateException(%s, %s, %s)" % (repr(self.template), repr(self.local), repr(self.exc_info))


class Templite(object):

    """
    Evaluador de plantillas.

    Permite procesar y evaluar plantillas con practicamente todo
    el poder expresivo de python.

    Las plantillas son documentos de texto (unicode) que pueden contener
    tres tipos de elementos:

    - Texto literal (cualquier texto)
    - Expresiones (expresiones python encerradas entre "delimitadores")
    - Bloques (bloques de codigo python encerrados entre marcadores
               de "inicio" y "fin" de bloque).

    El delimitador por defecto es "?", y se admite cualquier expresion
    python valida, por ejemplo,

        Hola, ?"mundo"? !
        Hola, ?"mun" + "do"? !
        Hola, ?"".join(("m", "u", "n", "d", "o"))?
        Los dedos de la mano son ?4+1?

    El delimitador debe ser de longitud 1 y se escapa repitiendolo:

        Un interrogante: ?? , una expresion delimitada: ?"hola!"?

    Los marcadores de inicio y fin por defecto son "{{" y "}}" respectivamente,
    y se admite cualquier expresion python valida, por ejemplo:

        {{nombre = "Pedro"}}
        Hola, ?nombre? !

    Los marcadores deben ser de longitud 2 y se escapan insertando
    un caracter \\ entre ellos:

        llaves abiertas: {\\{, llaves cerradas: }\\}

    Tambien se admiten bloques (como "if", "for", "def"...). Los bloques han
    de ser terminados por un nuevo bloque que empiece por ":":

        {{a = 10}}
        {{if a > 5:}}
            A es mayor que 5
        {{:else:}}
            A es menor o igual que 5
        {{:end if}}

        {{
          dedos = {
              "Este puso un huevo",
              "Este lo friyo",
              "Este le echo la sal",
              "Este lo probo",
              "Y este gordinflon se lo comio",
          }
        }}
        {{for i in xrange(5):
            mensaje = dedos[i]
        }}
            Dedo ?i+1?: ?mensaje?
        {{:end for
            El bloque de cierre puede contener cualquier cosa,
            se ignora a menos que sea un :else:
        }}

    Cuidado! no se recomienda tener mas de un nivel de indentacion
    por bloque, porque puede inducir a error:

        {{
        #####################
        # Esto NO funciona: #
        #####################
        }}
        {{for i in range(5):
            for j in range(10):
        }}
                i, j: ?i?, ?j?
        {{:end for}}

        {{
        ############
        # Esto SI: #
        ############
        }}
        {{for i in range(5):}}
            {{for j in range(10):}}
                i, j: ?i?, ?j?
            {{:end for}}
        {{:end for}}
    
    Las plantillas se compilan y se ejecutan mediante el paso de
    mensajes a un consumidor. Un consumidor es una corutina, es decir,
    un generador que acepte los metodos "send" y "close". Los
    mensajes que se envian al consumidor son cadenas de texto unicode,
    el resultado de evaluar cada porcion de la plantilla.

    Las variables miembros de una plantilla son:

    - timestamp:  una marca de tiempo que identifica el momento en que
                  se proceso el template. 
    - translated: el codigo python de la plantilla, interpretada y
                  lista para ser compilada.
    - code:       el codigo compilado.
    """

    # ----------------------------------------------
    # Parte "privada", solo se utiliza internamente
    # ----------------------------------------------

    class Literal(object):

        """
        Procesador de una parte literal de una plantilla.

        Procesa un trozo de plantilla no encerrado en un bloque. Genera
        una lista ordenada de bloques de texto y expresiones a evaluar.
        """

        def __init__(self, part, delim):
            # Para evitar demasiadas newlines, si la primera linea
            # del texto entre bloques esta vacia, la elimino.
            first = part.find(u"\n")
            if first >= 0:
                if part[:(first+1)].isspace():
                    part = part[(first+1):]
            self.parts = list()
            actions, accum = cycle((self.odd, self.even)), u""
            for subpart in part.split(delim):
                accum = actions.next()(subpart, accum, delim)
            if accum:
                self.parts.append(accum)

        def odd(self, subpart, accum, delim):
            """Posiciones impares: todo es simplemente texto"""
            return accum + subpart

        def even(self, subpart, accum, delim):
            """Posiciones pares.
            Si esta vacio, es que habia un delimitador repetido.
            Si no, es un eval.
            """
            if not subpart:
                return accum + delim
            self.parts.append(accum)
            self.parts.append(subpart)
            return u""

        def __iter__(self):
            return iter(self.parts)

    class Block(object):

        """
        Procesador de un bloque de una plantilla.

        Procesa un trozo de plantilla encerrado en un bloque. Genera
        consecutivamente offsets y listas de comandos.
        """

        def __init__(self, part, start, end):
            first, offset, body = part.strip(), 0, 0
            # si el primer caracter no espacio es ":", es un bloque de
            # continuacion
            if first.startswith(u":"):
                first = first[1:]
                offset = -1
            lines = tuple(l for l in first.splitlines() if not l.isspace())
            first = lines[0].strip()
            # Si la primera linea termina en ":", el cuerpo se indenta
            # un nivel adicional respecto a ella.
            if first.endswith(u":"):
                body = 1
            elif offset < 0:
                # Un fin de bloque que no inicie otro, se descarta
                first, lines = None, None
            # Dedentamos las lineas que siguen a la primera.
            if lines:
                lines = self.dedent(lines[1:])
            self.__dict__.update(**locals())

        def dedent(self, lines):
            if lines:
                level = min(len(l) - len(l.lstrip()) for l in lines)
                return tuple(l[level:].rstrip() for l in lines)
            
        def __iter__(self):
            yield self.offset
            if self.first:
                yield (self.first,)
                yield self.body
                if self.lines:
                    yield self.lines

    def do_literal(self, part, start, end, delim, indent):
        """Procesa un trozo de plantilla fuera de bloques"""
        indent = self.offset * indent
        def odd(subpart):
            return indent + (u"_consumer.send(%s)" % repr(subpart))
        def even(subpart):
            return indent + (u"_consumer.send(unicode(%s))" % subpart)
        actions = cycle((odd, even))
        for subpart in Templite.Literal(part, delim):
            yield actions.next()(subpart)

    def do_block(self, part, start, end, delim, indent):
        """Procesa un trozo de plantilla dentro de un bloque."""
        def odd(offset, dummy=[]):
            # Los elementos impares son cambios en el offset: (-1, 0, 1)
            self.offset += offset
            if self.offset < 0:
                raise SyntaxError(u"No block statement to terminate: ${%s}$" % part)
            return dummy
        def even(lines):
            # Los elementos pares son listas de lineas sin indentar.
            offset = self.offset * indent
            return (offset + l for l in lines)
        actions = cycle((odd, even))
        for subpart in Templite.Block(part, start, end):
            for result in actions.next()(subpart):
                yield result

    def do_template(self, template, start, end, delim, indent):
        """Procesa el template linea a linea"""
        delimiter = re.compile(r'%s(.*?)%s' % (re.escape(start), re.escape(end)), re.DOTALL | re.UNICODE)
        actions = cycle((self.do_literal, self.do_block))
        for subpart in delimiter.split(template):
            subpart = subpart.replace(u"\\".join(start), start)
            subpart = subpart.replace(u"\\".join(end), end)
            for block in actions.next()(subpart, start, end, delim, indent):
                yield block

    CURRENT = (1, sys.version_info)
    @classmethod
    def State(cls, timestamp, template, ast):
        return {
            'version': cls.CURRENT,
            'timestamp': timestamp, 
            'template': template,
            'ast': ast,
        }

    def parse_template(self, template, start, end, delim, indent, timestamp):
        try:
            self.offset = 0
            translated = u"\n".join(self.do_template(template, start, end, delim, indent))
            if self.offset:
                raise SyntaxError(u"%i block statement(s) not terminated" % self.offset)
            tree = ast.parse(translated, u"<templite %r>" % template[:20], 'exec')
            return Templite.State(timestamp, translated, tree)
        except Exception as details:
            raise ParseException(template, sys.exc_info())

    # ----------------
    # Parte "publica"
    # ----------------

    def __init__(self, template=u"", start=u"{{", end=u"}}", delim=u"?", indent=u"    ", timestamp=None):
        """Analiza, valida y construye el template.

        En caso de error durante el proceso, lanza una ParseException con
        los detalles del problema.
        """
        assert(isinstance(template, unicode))
        assert(isinstance(start, unicode))
        assert(isinstance(end, unicode))
        assert(isinstance(delim, unicode))
        assert(isinstance(indent, unicode))
        assert(len(start) == 2 and len(end) == 2)
        assert(len(delim) == 1)
        assert(indent.isspace())
        self.__setstate__(self.parse_template(template, start, end, delim, indent, timestamp or datetime.now()))

    def __getstate__(self):
        """Devuelve el estado del objeto, para 'pickle'."""
        return Templite.State(self.timestamp, self.translated, self.ast)

    def __setstate__(self, state):
        """Restablece el estado del objeto desde un 'pickle'."""
        if state['version'] != self.__class__.CURRENT:
            raise pickle.UnpicklingError(u"Versions do not match: %s != %s" % (unicode(state['version']), unicode(self.__class__.CURRENT)))
        self.timestamp = state['timestamp']
        self.translated = state['template']
        self.ast = state['ast']
        self.code = compile(self.ast, u"<templite %r>" % self.translated[:20], 'exec')

    def render(self, consumer, glob=None, loc=None):
        """Ejecuta la plantilla con el consumidor y datos dados.

        El consumidor es una corutina. Cada vez que la plantilla genera
        un trozo de texto (bien por tener texto literal, o por una
        expresion), ese texto se alimenta al consumidor a traves del metodo
        "send". Por ejemplo, la plantilla:

            {{nombre = "Pedro"}}
            Hola, ?nombre? !

        Se convierte en la siguiente secuencia de llamadas:
            consumer.next()
            consumer.send(u"Hola, ")
            consumer.send(u"Pedro")
            consumer.send(u" !")
            consumer.close()

        Al terminar la ejecucion, el scope local se analiza y se traspasan
        al global todos los elementos que cumplan alguna de las
        siguientes condiciones:

        - son invocables (tienen el atributo "__call__")
        - son clases
        - son modulos

        Si se produce alguna excepcion durante la ejecucion de la plantilla,
        se le traslada al consumidor envuelta en un TemplateException, y se
        aborta la ejecucion del template.
        """
        if glob is None:
            glob = dict()
        if loc is None:
            loc = dict()
        glob["_consumer"] = consumer
        consumer.next()
        try:
            exec self.code in glob, loc
        except Exception:
            try:
                consumer.throw(TemplateException(self.translated, loc, sys.exc_info()))
            except StopIteration:
                # No tengo ni idea de por que me lanza un StopIteration
                # despues de hacer el throw... me parece una tonteria, pero
                # bueno, lo capturo.
                pass
        finally:
            del(glob["_consumer"])
            consumer.close()
        # Pongo en el alcance global los siguientes elementos:
        # - clases
        # - modulos
        # - funciones
        for item, value in loc.iteritems():
            if hasattr(value, '__call__') or type(value).__name__ in ('classobj', 'module'):
                glob[item] = value


if __name__ == '__main__':

    import unittest

    class Consumer(object):

        def __init__(self, glob, loc):
            self.result = None
            self.closed = False
            self.exc = None
            self.glob = glob
            self.loc = loc

        def __call__(self):
            result = list()
            try:
                while True:
                    result.append((yield))
            except GeneratorExit:
                self.closed = True
            except TemplateException as details:
                self.exc = details
            finally:
                self.result = u"".join(result)

    class ConstructorTest(unittest.TestCase):

        def testTemplateInvalid(self):
            """Error si el template no es unicode"""
            self.assertRaises(AssertionError, Templite, 100)

        def testDelimInvalid(self):
            """Error si delim no es unicode o len() != 1"""
            self.assertRaises(AssertionError, Templite, u"", delim=u"")
            self.assertRaises(AssertionError, Templite, u"", delim=u"abc")
            self.assertRaises(AssertionError, Templite, u"", delim=100)

        def testBlockDelimInvalid(self):
            """Error si los inicio y fin de bloque no son unicode o len() != 2"""
            self.assertRaises(AssertionError, Templite, u"", start=u"abc")
            self.assertRaises(AssertionError, Templite, u"", end=u"abc")
            self.assertRaises(AssertionError, Templite, u"", start=u"")
            self.assertRaises(AssertionError, Templite, u"", end=u"")
            self.assertRaises(AssertionError, Templite, u"", start=100)
            self.assertRaises(AssertionError, Templite, u"", end=100)

        def testIndentInvalid(self):
            """Error si indent no es unicode o no es whitespace"""
            self.assertRaises(AssertionError, Templite, u"", indent=100)
            self.assertRaises(AssertionError, Templite, u"", indent=u"abc")
            self.assertRaises(AssertionError, Templite, u"", indent=u"")

        def testTemplateUnfinished(self):
            """Error si hay bloques sin cerrar"""
            template = u"""
            {{if 5 > 0:}}
                5 es mayor que 0
            """
            self.assertRaises(ParseException, Templite, template)

    class TemplateTest(unittest.TestCase):

        def buildTestCases(self, template, result):
            """Genera versiones del patron con distintos delimitadores"""
            sets = (
                ( u"{{", u"}}", u"?", u"    " ),
                ( u"${", u"}$", u"%", u"    " )
            )
            for x in sets:
                data = dict(zip(('start','end','delim','indent'), x))
                full = copy.copy(data)
                full['escaped_start'] = u"\\".join(data['start'])
                full['escaped_end'] = u"\\".join(data['end'])
                full['escaped_delim'] = data['delim'] + data['delim']
                yield (data, template % full, (result or u"") % full)

        def hookTemplite(self, templite):
            """Un hook para facilitar la evaluacion de pickle y zodb"""
            return templite

        def checkTestCases(self, template, result=None, glob=None, loc=None, exc=None):
            """Valida las distintas versiones generadas por buildTestCases"""
            consumer = None
            for d, t, r in self.buildTestCases(template, result):
                if glob is None:
                    glob = {}
                if loc is None:
                    loc = {}
                consumer = Consumer(glob, loc)
                templite = self.hookTemplite(Templite(t, **d))
                templite.render(consumer(), glob, loc)
                if result:
                    self.assertEqual(consumer.result, r)
                if not exc:
                    self.failUnless(consumer.closed == True)
                    self.failUnless(consumer.exc is None)
                else:
                    self.failUnless(consumer.closed == False)
                    self.failUnless(consumer.exc.exc_info[0] == exc)
            return consumer

        def testLiteralTemplate(self):
            """Template formado solo por literales"""
            template = u"  Hello! \n World! "
            result = template
            self.checkTestCases(template, result)

        def testWhitespaceRemoval(self):
            """Template con whitespace al inicio"""
            template = u"    \n Hello! \nWorld!  "
            result = u" Hello! \nWorld!  "
            self.checkTestCases(template, result)

        def testSimpleEval(self):
            """Un simple eval"""
            template = u"  %(delim)s 4 + 2 %(delim)s  "
            result = u"  6  "
            self.checkTestCases(template, result)

        def testEscapedDelim(self):
            """Delimitador escapado"""
            template = u" %(escaped_delim)s %(delim)s'hola!'%(delim)s"
            result = u" %(delim)s hola!"
            self.checkTestCases(template, result)

        def testSimpleBlock(self):
            """Un bloque simple"""
            template = u"\n%(start)s x = 5 %(end)s\n%(delim)s x %(delim)s"""
            result = u"5"
            self.checkTestCases(template, result)

        def testIfBlock(self):
            """Un bloque con un if"""
            template = u"\n%(start)s if 5 > 0: %(end)s\n5 es mayor que 0\n%(start)s :endif %(end)s"""
            result = u"5 es mayor que 0\n"
            self.checkTestCases(template, result)
            
        def testIfElseBlock(self):
            """Un bloque con un if"""
            template = u"\n%(start)s if 5 < 0: %(end)s\n5 es menor que 0\n%(start)s :else: %(end)s\n5 no es menor que 0\n%(start)s :endif %(end)s"""
            result = u"5 no es menor que 0\n"
            self.checkTestCases(template, result)

        def testForBlock(self):
            """Un bloque con un if"""
            template = u"\n%(start)s for i in range(4): %(end)s\n%(delim)s i %(delim)s\n%(start)s :end for %(end)s"""
            result = u"0\n1\n2\n3\n"
            self.checkTestCases(template, result)

        def testDefBlock(self):
            """Un bloque con def"""
            template = u"\n%(start)s def test(a):\n    return a %(end)s\n%(start)s :end def %(end)s\n%(delim)s test(1) %(delim)s"""
            result = u"1"
            self.checkTestCases(template, result)

        def testEscapedStart(self):
            """Un start escapado"""
            template = u"\n%(escaped_start)s %(start)s x = '%(escaped_start)s' %(end)s\n%(delim)s x %(delim)s"""
            result = u"%(start)s %(start)s"
            self.checkTestCases(template, result)
            
        def testEscapedEnd(self):
            """Un end escapado"""
            template = u"\n%(escaped_end)s %(start)s x = '%(escaped_end)s' %(end)s\n%(delim)s x %(delim)s"""
            result = u"%(end)s %(end)s"
            self.checkTestCases(template, result)

        def testException(self):
            """Lanzamiento de una excepcion"""
            template = u"\n%(start)s x = 1/0 %(end)s\n%(delim)s x %(delim)s"""
            self.checkTestCases(template, exc=ZeroDivisionError)

        def testVariable(self):
            """Los diccionarios proporcionados son accesibles"""
            template = u"%(delim)s d+1 %(delim)s"""
            result = u"6"
            self.checkTestCases(template, result, glob={'d':5})
            
        def testVariableInjection(self):
            """Las variables normales no pasan al scope global"""
            template = u"\n%(start)s x = 1 %(end)s\n%(delim)s x %(delim)s"""
            result = u"1"
            data = self.checkTestCases(template, result)
            self.failIf('x' in data.glob)
            self.failUnless('x' in data.loc)

        def testDefInjection(self):
            """Las funciones pasan al scope global"""
            template = u"\n%(start)s def test(a): return a %(end)s\n%(delim)s test(10) %(delim)s"""
            result = u"10"
            data = self.checkTestCases(template, result)
            self.failUnless('test' in data.glob)

        def testImportInjection(self):
            """Los modulos pasan al scope global"""
            template = u"\n%(start)s import os %(end)s\n%(delim)s 20 %(delim)s"""
            result = u"20"
            data = self.checkTestCases(template, result)
            self.failUnless('os' in data.glob)

        def testClassInjection(self):
            """Las clases pasan al scope global"""
            template = u"\n%(start)s class dummy(object): pass %(end)s\n%(delim)s 30 %(delim)s"""
            result = u"30"
            data = self.checkTestCases(template, result)
            self.failUnless('dummy' in data.glob)

    class PickledTemplateTest(TemplateTest):

        def hookTemplite(self, templite):
            """Hace un pickle y un unpickle"""
            loaded = pickle.loads(pickle.dumps(templite))
            self.failUnless(templite.translated == loaded.translated)
            self.failUnless(templite.timestamp == loaded.timestamp)
            return loaded

        def testVersionMismatch(self):
            """Se lanza UnpicklingError si las versiones no coinciden"""
            def hookPatch(templite):
                pickled = pickle.dumps(templite)
                templite.__class__.CURRENT = (sys.maxint, sys.version_info)
                return pickle.loads(pickled)
            self.hookTemplite = hookPatch
            template = u"  %(delim)s 4 + 2 %(delim)s  "
            result = u"  6  "
            self.assertRaises(pickle.UnpicklingError, self.checkTestCases, template, result)

    unittest.main()
