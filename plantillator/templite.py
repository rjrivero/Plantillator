#!/usr/bin/env python


import sys, re, copy, traceback, ast
from collections import namedtuple
from itertools import izip, cycle, chain

try:
    import cPickle as pickle
except ImportError:
    import pickle


class ParseError(Exception):

    """
    Encapsula las excepciones lanzadas durante la compilacion de un template.

    - self.template: plantilla (sin procesar) que ha provocado la excepcion
    - self.exc_info: tupla (tipo, excepcion, traceback)
    """

    def __init__(self, template):
        super(ParseError, self).__init__()
        self.template = template
        self.exc_info = sys.exc_info()

    def __str__(self):
        return "".join(traceback.format_exception(*(self.exc_info)))

    def __repr__(self):
        return "ParseError(%s, %s)" % (repr(self.template), repr(self.exc_info))


class TemplateError(Exception):

    """
    Encapsula las excepciones lanzadas durante la ejecucion de un template.

    - self.template: plantilla (procesada) que ha provocado la excepcion
    - self.local: diccionario con las variables locales de la plantilla en el
                  momento de la excepcion.
    - self.exc_info: tupla (tipo, excepcion, traceback)
    """

    def __init__(self, template, local):
        super(TemplateError, self).__init__()
        self.template = template
        self.local = local
        self.exc_info = sys.exc_info()

    def __str__(self):
        return "".join(traceback.format_exception(*(self.exc_info)))

    def __repr__(self):
        return "TemplateError(%s, %s, %s)" % (repr(self.template), repr(self.local), repr(self.exc_info))


class Accumulator(object):

    """Acumulador de cadenas de texto.

    Hace buffering de los bloques, para que se puedan filtrar. El texto en
    el primer nivel se guarda en un buffer; cuando aparece un bloque, el texto
    acumulado se manda al consumidor y se empieza a hacer buffering del
    nuevo bloque, en dos niveles:

     - una lista interna, con el texto generado por el cuerpo del bloque.
     - una lista externa, con el texto generado en cada pasada del bloque
         (por si era un bucle: cada pasada se guardaria aparte).
    """

    def __init__(self, consumer):
        self.stack, self.current = list(), list()
        self.group = None
        self.consumer = consumer

    def push(self):
        """Empujamos el bloque actual"""
        if self.group is None:
            # Puedo haber estado acumulando cosas en self.current, las despacho
            if self.current:
                self.consumer.send("".join(self.current))
        else:
            self.group.append(self.current)
            self.stack.append(self.group)
        self.group = list()
        self.current = list()
        
    def refresh(self):
        """Refrescamos el bloque actual"""
        if self.group is None:
            self.consumer.send("".join(self.current))
        else:
            self.group.append(self.current)
        self.current = list()

    def collect(self):
        """Obtiene el grupo actual de datos"""
        if self.group is None:
            return tuple("".join(self.current),)
        group = ("".join(x) for x in self.group if x)
        if self.current:
            group = chain(group, ("".join(self.current),))
        # Instancio el iterador porque esto generalmente se invoca antes
        # de llamar a pop(), y no quiero problemas de que llamen a pop y
        # luego se itere sobre algo equivocado.
        return tuple(group)

    def pop(self):
        """Da por concluido el bloque y vuelve al buffer anterior"""
        if self.group is None:
            raise NotImplemented("_idle_pop")
        result = self.collect()
        if self.stack:
            # Si habia algo en la pila, lo sacamos
            self.group = self.stack.pop()
            self.current = self.group.pop()
        else:
            self.current = list()
            self.group = None
        return result

    def add(self, string):
        """manda la cadena al buffer actual"""
        if string:
            self.current.append(string)


def SORT(strings):
    """Ordena los items"""
    return sorted(strings)


def REVERSE(strings):
    """Invierte el orden de los items"""
    return reversed(strings)


def UNIQ(strings):
    """Filtra los items y devuelve solo los unicos"""
    return sorted(set(strings))


class Templite(object):

    """
    Evaluador de plantillas.

    Permite procesar y evaluar plantillas con practicamente todo
    el poder expresivo de python.

    Las plantillas son documentos de texto que pueden contener
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
            se ignora a menos que sea un :else:,  :elif:, :default: ...
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

    Tambien se admite el uso de filtros, que son funciones que permiten
    pos-procesar la salida de un bloque.
    
        - Los filtros reciben como parametro una lista con todas las cadenas
            que se han generado en el bloque

        - Deben devolver una lista de cadenas de texto (para poder encadenar
            filtros)

        - Los filtros se indican en el bloque de cierre, detras de ">>"

    Por ejemplo:

    {{  # Ordena los resultados
        def SORT(strings):
            return sorted(strings)

        # Invierte el orden de los resultados
        def REVERSE(strings):
            return reversed(strings)
    }}
    {{nombres = ("Rosa", "Marta", "Pedro", "Luis", "Rosa")}}
    {{for nombre in nombres:}}
        Hola, ?nombre?
    {{:endfor >> SORT >> REVERSE}}

    Los filtros SORT, UNIQ (como SORT, pero eliminando duplicados)
    y REVERSE estan predefinidos.

    Las plantillas se compilan y se ejecutan mediante el paso de
    mensajes a un consumidor. Un consumidor es una corutina, es decir,
    un generador que acepta los metodos "send" y "close". Los
    mensajes que se envian al consumidor son cadenas de texto,
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
            first = part.find("\n")
            if first >= 0:
                if part[:(first+1)].isspace():
                    part = part[(first+1):]
            self.parts = list()
            actions, accum = cycle((self.odd, self.even)), ""
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
            return ""

        def __iter__(self):
            return iter(self.parts)

    class Block(object):

        """
        Procesador de un bloque de una plantilla.

        Procesa un trozo de plantilla encerrado en un bloque. Genera
        consecutivamente offsets y listas de comandos.
        """

        def __init__(self, part, start, end, TAB_WIDTH=" "*8):
            first, offset, body, filt = part.strip(), 0, 0, ""
            # si el primer caracter no espacio es ":", es un bloque de
            # continuacion
            if first.startswith(":"):
                first = first[1:]
                offset = -1
            lines = (l for l in first.splitlines() if not l.isspace())
            # Evito mezclar espacios con tabs
            lines = tuple(l.replace("\t", TAB_WIDTH) for l in lines)
            first = lines[0].strip()
            # Si la primera linea termina en ":", el cuerpo se indenta
            # un nivel adicional respecto a ella.
            if first.endswith(":"):
                body = 1
            elif offset < 0:
                # Un fin de bloque que no inicie otro, se descarta
                # Eso si, comprobamos si tiene un filtro
                parts = list(first.split(">>")[1:])
                parts.append('"".join')
                # Los filtros se aplican en orden inverso
                filt = "".join("%s(" % x.strip() for x in reversed(parts))
                filt += "_accumulator.pop()" + ")" * len(parts)
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
            """Genera una secuencia de offsets y ordenes"""
            # Tenemos cuatro posibles tipos de bloque:
            # (a) {{xxxx}}   --> offset  0, body 0
            # (b) {{xxxx:}}  --> offset  0, body 1
            # (c) {{:xxxx}}  --> offset -1, body 0
            # (d) {{:xxxx:}} --> offset -1, body 1
            # - Caso (a): no modificamos nada del buffering.
            # - Caso (b): Estamos abriendo un nuevo bloque, asi que
            #             queremos salvar el output que llevamos hasta ahora,
            #             y empezar a meter el output del bloque en una
            #             nueva lista.
            # - Caso (c): Cerramos el bloque, queremos consumir el output
            #             que haya generado y recuperar lo que habiamos
            #             salvado.
            # - Caso (d): Cerramos un bloque y abrimos otro enlazado (como
            #             un "if" y un "else", un "for" y un "default", etc).
            #             queremos conservar la misma lista externa, pero usar
            #             una lista interna diferente.
            if self.offset == 0 and self.body == 1:
                yield 0
                yield ("_accumulator.push()",)
            yield self.offset
            if self.first:
                yield (self.first,)
                # Incluyo if y try en las construcciones que refrescan el
                # accumulator porque de todas formas, los :else:, :elif:
                # o :except: tambien lo van a refrescar
                is_loop = any(self.first.startswith(x)
                    for x in ("for", "while", "if", "try"))
                if self.body == 1 and (self.offset == -1 or is_loop):
                    self.lines = tuple(chain((
                            "_accumulator.refresh()",
                        ), self.lines or tuple()))
                yield self.body
                if self.lines:
                    yield self.lines
            else:
                # El filtro por defecto es '"".join(_accumulator.pop())'
                yield ("_accumulator.add(%s)" % self.filt,)

    def do_literal(self, part, start, end, delim, indent):
        """Procesa un trozo de plantilla fuera de bloques"""
        indent = self.offset * indent
        def odd(subpart):
            return indent + ("_accumulator.add(%s)" % repr(subpart))
        def even(subpart):
            return indent + ("_accumulator.add(str(%s))" % subpart)
        actions = cycle((odd, even))
        for subpart in Templite.Literal(part, delim):
            yield actions.next()(subpart)

    def do_block(self, part, start, end, delim, indent):
        """Procesa un trozo de plantilla dentro de un bloque."""
        def odd(offset, dummy=[]):
            # Los elementos impares son cambios en el offset: (-1, 0, 1)
            self.offset += offset
            if self.offset < 0:
                raise SyntaxError("No block statement to terminate: ${%s}$" % part)
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
        delimiter = re.compile(r'%s(.*?)%s' % (re.escape(start), re.escape(end)), re.DOTALL)
        actions = cycle((self.do_literal, self.do_block))
        for subpart in delimiter.split(template):
            subpart = subpart.replace("\\".join(start), start)
            subpart = subpart.replace("\\".join(end), end)
            for block in actions.next()(subpart, start, end, delim, indent):
                yield block

    CURRENT = (1, sys.version_info)
    @classmethod
    def State(cls, tmplid, timestamp, template, ast):
        return {
            'tmplid': tmplid,
            'version': cls.CURRENT,
            'timestamp': timestamp, 
            'template': template,
            'ast': ast,
        }

    def parse_template(self, tmplid, template, start, end, delim, indent, timestamp):
        try:
            self.offset = 0
            translated = "\n".join(self.do_template(template, start, end, delim, indent))
            if self.offset:
                raise SyntaxError("%i block statement(s) not terminated" % self.offset)
            tree = ast.parse(translated, tmplid, 'exec')
            return Templite.State(tmplid, timestamp, translated, tree)
        except Exception as details:
            raise ParseError(template)

    # ----------------
    # Parte "publica"
    # ----------------

    def __init__(self, tmplid, template="", start="{{", end="}}", delim="?", indent=" "*4, timestamp=None):
        """Analiza, valida y construye el template.

        En caso de error durante el proceso, lanza una ParseError con
        los detalles del problema.
        """
        assert(isinstance(tmplid, basestring))
        assert(isinstance(template, basestring))
        assert(isinstance(start, basestring))
        assert(isinstance(end, basestring))
        assert(isinstance(delim, basestring))
        assert(isinstance(indent, basestring))
        assert(len(start) == 2 and len(end) == 2)
        assert(len(delim) == 1)
        assert(indent.isspace())
        self.__setstate__(self.parse_template(tmplid, template, start, end, delim, indent, timestamp))

    def __getstate__(self):
        """Devuelve el estado del objeto, para 'pickle'."""
        return Templite.State(self.tmplid, self.timestamp, self.translated, self.ast)

    def __setstate__(self, state):
        """Restablece el estado del objeto desde un 'pickle'."""
        if state['version'] != self.__class__.CURRENT:
            raise pickle.UnpicklingError("Versions do not match: %s != %s" % (str(state['version']), str(self.__class__.CURRENT)))
        self.tmplid = state['tmplid']
        self.timestamp = state['timestamp']
        self.translated = state['template']
        self.ast = state['ast']
        self.code = compile(self.ast, self.tmplid, 'exec')

    def render(self, consumer, glob=None, loc=None):
        """Ejecuta la plantilla con el consumidor y datos dados.

        El consumidor es una corutina. Cada vez que la plantilla genera
        un trozo de texto (bien por tener texto literal, o por una
        expresion), ese texto se acumula. Una vez acumulada una seccion de
        la plantilla, se le envia al consumidor a traves del metodo
        "send". Por ejemplo, la plantilla:

            {{nombre = "Pedro"}}
            Hola, ?nombre? !

        Se convierte (aproximadamente) en la siguiente secuencia de llamadas:

            consumer.next()
            accumulator.add("Hola, ")
            accumulator.add("Pedro")
            accumulator.add(" !")
            consumer.send("".join(accumulator))
            consumer.close()

        Al terminar la ejecucion, el scope local se analiza y se traspasan
        al global todos los elementos que cumplan alguna de las
        siguientes condiciones:

        - son invocables (tienen el atributo "__call__")
        - son clases
        - son modulos

        Si se produce alguna excepcion durante la ejecucion de la plantilla,
        se le traslada al consumidor envuelta en un TemplateError, y se
        aborta la ejecucion del template.
        """
        if glob is None:
            glob = dict()
        if loc is None:
            loc = dict()
        glob["_consumer"] = consumer
        glob["_accumulator"] = Accumulator(consumer)
        glob["UNIQ"] = UNIQ
        glob["SORT"] = SORT
        glob["REVERSE"] = REVERSE
        consumer.next()
        if self.embed(consumer, glob, loc):
            result = "".join(glob["_accumulator"].collect())
            if result:
                consumer.send(result)
            consumer.close()

    def embed(self, consumer, glob, loc):
        """Ejecuta una plantilla embebida.

        Es como "render", pero considera que el consumidor y los datos
        ya estan inicializados.
        """
        try:
            exec self.code in glob, loc
            return True
        except:
            try:
                consumer.throw(TemplateError(self.translated, loc))
            except StopIteration:
                # No tengo ni idea de por que me lanza un StopIteration
                # despues de hacer el throw... me parece una tonteria, pero
                # bueno, lo capturo.
                pass
        finally:
            # paso al scope global las variables locales aceptadas.
            self._promote(glob, loc)

    def _promote(self, glob, loc):
        """Pasa a scope global ciertas variables del scope local"""
        promoted = list()
        for key, value in loc.iteritems():
            if hasattr(value, '__call__') or type(value).__name__ in ('classobj', 'module'):
                glob[key] = value
                promoted.append(key)
        for key in promoted:
            del(loc[key])


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
            except TemplateError as details:
                self.exc = details
            finally:
                self.result = "".join(result)

    class ConstructorTest(unittest.TestCase):

        def testTemplateInvalid(self):
            """Error si el template no es str"""
            self.assertRaises(AssertionError, Templite, "test", 100)

        def testDelimInvalid(self):
            """Error si delim no es str o len() != 1"""
            self.assertRaises(AssertionError, Templite, "test", "", delim="")
            self.assertRaises(AssertionError, Templite, "test", "", delim="abc")
            self.assertRaises(AssertionError, Templite, "test", "", delim=100)

        def testBlockDelimInvalid(self):
            """Error si los inicio y fin de bloque no son str o len() != 2"""
            self.assertRaises(AssertionError, Templite, "test", "", start="abc")
            self.assertRaises(AssertionError, Templite, "test", "", end="abc")
            self.assertRaises(AssertionError, Templite, "test", "", start="")
            self.assertRaises(AssertionError, Templite, "test", "", end="")
            self.assertRaises(AssertionError, Templite, "test", "", start=100)
            self.assertRaises(AssertionError, Templite, "test", "", end=100)

        def testIndentInvalid(self):
            """Error si indent no es str o no es whitespace"""
            self.assertRaises(AssertionError, Templite, "test", "", indent=100)
            self.assertRaises(AssertionError, Templite, "test", "", indent="abc")
            self.assertRaises(AssertionError, Templite, "test", "", indent="")

        def testTemplateUnfinished(self):
            """Error si hay bloques sin cerrar"""
            template = """
            {{if 5 > 0:}}
                5 es mayor que 0
            """
            self.assertRaises(ParseError, Templite, "test", template)

    class TemplateTest(unittest.TestCase):

        def buildTestCases(self, template, result):
            """Genera versiones del patron con distintos delimitadores"""
            sets = (
                ( "{{", "}}", "?", "    " ),
                ( "${", "}$", "%", "    " )
            )
            for x in sets:
                data = dict(zip(('start','end','delim','indent'), x))
                full = copy.copy(data)
                full['escaped_start'] = "\\".join(data['start'])
                full['escaped_end'] = "\\".join(data['end'])
                full['escaped_delim'] = data['delim'] + data['delim']
                yield (data, template % full, (result or "") % full)

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
                templite = self.hookTemplite(Templite("test", t, **d))
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
            template = "  Hello! \n World! "
            result = template
            self.checkTestCases(template, result)

        def testWhitespaceRemoval(self):
            """Template con whitespace al inicio"""
            template = "    \n Hello! \nWorld!  "
            result = " Hello! \nWorld!  "
            self.checkTestCases(template, result)

        def testSimpleEval(self):
            """Un simple eval"""
            template = "  %(delim)s 4 + 2 %(delim)s  "
            result = "  6  "
            self.checkTestCases(template, result)

        def testEscapedDelim(self):
            """Delimitador escapado"""
            template = " %(escaped_delim)s %(delim)s'hola!'%(delim)s"
            result = " %(delim)s hola!"
            self.checkTestCases(template, result)

        def testSimpleBlock(self):
            """Un bloque simple"""
            template = "\n%(start)s x = 5 %(end)s\n%(delim)s x %(delim)s"""
            result = "5"
            self.checkTestCases(template, result)

        def testIfBlock(self):
            """Un bloque con un if"""
            template = "\n%(start)s if 5 > 0: %(end)s\n5 es mayor que 0\n%(start)s :endif %(end)s"""
            result = "5 es mayor que 0\n"
            self.checkTestCases(template, result)
            
        def testIfElseBlock(self):
            """Un bloque con un if"""
            template = "\n%(start)s if 5 < 0: %(end)s\n5 es menor que 0\n%(start)s :else: %(end)s\n5 no es menor que 0\n%(start)s :endif %(end)s"""
            result = "5 no es menor que 0\n"
            self.checkTestCases(template, result)

        def testForBlock(self):
            """Un bloque con un if"""
            template = "\n%(start)s for i in range(4): %(end)s\n%(delim)s i %(delim)s\n%(start)s :end for %(end)s"""
            result = "0\n1\n2\n3\n"
            self.checkTestCases(template, result)

        def testDefBlock(self):
            """Un bloque con def"""
            template = "\n%(start)s def test(a):\n    return a %(end)s\n%(start)s :end def %(end)s\n%(delim)s test(1) %(delim)s"""
            result = "1"
            self.checkTestCases(template, result)

        def testEscapedStart(self):
            """Un start escapado"""
            template = "\n%(escaped_start)s %(start)s x = '%(escaped_start)s' %(end)s\n%(delim)s x %(delim)s"""
            result = "%(start)s %(start)s"
            self.checkTestCases(template, result)
            
        def testEscapedEnd(self):
            """Un end escapado"""
            template = "\n%(escaped_end)s %(start)s x = '%(escaped_end)s' %(end)s\n%(delim)s x %(delim)s"""
            result = "%(end)s %(end)s"
            self.checkTestCases(template, result)

        def testException(self):
            """Lanzamiento de una excepcion"""
            template = "\n%(start)s x = 1/0 %(end)s\n%(delim)s x %(delim)s"""
            self.checkTestCases(template, exc=ZeroDivisionError)

        def testVariable(self):
            """Los diccionarios proporcionados son accesibles"""
            template = "%(delim)s d+1 %(delim)s"""
            result = "6"
            self.checkTestCases(template, result, glob={'d':5})
            
        def testVariableInjection(self):
            """Las variables normales no pasan al scope global"""
            template = "\n%(start)s x = 1 %(end)s\n%(delim)s x %(delim)s"""
            result = "1"
            data = self.checkTestCases(template, result)
            self.failIf('x' in data.glob)
            self.failUnless('x' in data.loc)

        def testDefInjection(self):
            """Las funciones pasan al scope global"""
            template = "\n%(start)s def test(a): return a %(end)s\n%(delim)s test(10) %(delim)s"""
            result = "10"
            data = self.checkTestCases(template, result)
            self.failUnless('test' in data.glob)

        def testImportInjection(self):
            """Los modulos pasan al scope global"""
            template = "\n%(start)s import os %(end)s\n%(delim)s 20 %(delim)s"""
            result = "20"
            data = self.checkTestCases(template, result)
            self.failUnless('os' in data.glob)

        def testClassInjection(self):
            """Las clases pasan al scope global"""
            template = "\n%(start)s class dummy(object): pass %(end)s\n%(delim)s 30 %(delim)s"""
            result = "30"
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
            template = "  %(delim)s 4 + 2 %(delim)s  "
            result = "  6  "
            self.assertRaises(pickle.UnpicklingError, self.checkTestCases, template, result)

    unittest.main()
