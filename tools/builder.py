#!/usr/bin/env python


import cgi

from copy import copy


class NodeDescriptor(dict):

    """Descriptor de nodo de un arbol.
    
    Describe las caracteristicas que debe cumplir el nodo: cuantas
    instancias de este nodo puede haber, que subnodos puede tener, que
    atributos, etc.
    """

    def __init__(self, name, num, args=None, kwargs=None):
        super(NodeDescriptor, self).__init__()
        if hasattr(num, '__iter__'):
            self.min , self.max = num
        else:
            self.min = self.max = num
        self.name   = name
        self.args   = len(args.split(",")) if args else 0
        self.kwargs = list(x.strip() for x in kwargs.split(",")) if kwargs else None

    def validate(self, objentry):
        return self.get(objentry.name, None)


class BuilderHelper(object):

    """
    Facilita la construccion de objetos que usan el patron builder.
    
    Forma de uso: con un ejemplo.
    
    headers = ["Nombre", "Instrumento"]
    data    = [
                ("Bruce Dickinson", "Cantante"),
                ("Steve Harris", "Bajo"),
                ("Dave Murray", "Guitarra"),
                ("Janick Guers", "Guitarra"),
                ("Adrian Smith", "Guitarra"),
                ("Nicko McBrain", "Bateria"),
              ]

    x = BuilderHelper()
    html = x.html << [
        x.head << x.title << "Miembros de Iron Maiden",
        x.body << [
            x.h1 << "Miembros de Iron Maiden",
            x.div(align="center") << x.table(width="80%") << [
                x.thead << x.tr << (x.th << h for h in headers),
                x.tbody << (
                    x.tr << (
                        x.td << item for item in row
                    ) for row in data
                )
            ]
        ]
    ]

    print(html.build(TagBuilder()))
    
    El BuilderHelper construye la estructura del arbol de objetos en memoria.
    
    A la estructura construida se le pasa un objeto Builder, que lleva a cabo
    la construccion del objeto.
    
    Se puede reutilizar la misma estructura con varios objetos Builder.
    """
    
    class ObjEntry(object):

        """Constructor de objetos"""

        def __init__(self, name, arg=None, kw=None):
            self.name       = name
            self.arg        = list(arg) if arg else []
            self.kw         = kw or dict()
            self.nested     = list()
            self.tail       = None
            # El descriptor raiz lo meto aqui como ayuda para el SpecBuilder.
            # Ya se que no deberia acoplar tanto las clases, pero asi es
            # mucho mas facil hacerlo funcionar.
            self.descriptor = None

        def flatten(self, items):
            """Aplasta una lista compuesta por objetos y sublistas"""
            # Ya no acepto callables como shortcuts para generar sublistas.
            # Mucho mejor usar list comprehensions en ese caso.
            if not hasattr(items, '__iter__') or hasattr(items, 'iteritems'):
                # No son varios items, es uno solo.
                if self.descriptor:
                    self._propagate(self.descriptor.validate, (items,))
                self.nested.append(items)
                return
            for item in items:
                self.flatten(item)

        def _propagate(self, validate, items, has=hasattr):
            """Propaga la actualizacion del descriptor a todos los elementos"""
            for item in (x for x in items if has(x, '_set_descriptor')):
                subdesc = validate(item)
                assert(subdesc is not None)
                item._set_descriptor(subdesc)

        def _set_descriptor(self, descriptor):
            """Actualiza el descriptor y valida la estructura"""
            if self.descriptor:
                assert(descriptor == self.descriptor)
            else:
                self.descriptor = descriptor
                self._propagate(descriptor.validate, self.nested)

        def build(self, builder, parent=None):
            """Construye el objeto usando el builder especificado"""
            context = getattr(builder, self.name, None)
            if context is not None:
                # Si el builder define una funcion especializada para el
                # nodo, la utilizo.
                context = context(parent, *self.arg, **self.kw)
            else:
                # Si no, utilizo la funcion generica "__call__"
                context = builder(parent, self.name, self.arg, self.kw)
            obj, append = context.next()
            if not append:
                append = lambda item: None
            for item in self.nested:
                if not hasattr(item, 'build'):
                    append(item)
                else:
                    item.build(builder, obj)
            try:
                # Termino el manejador.
                context.next()
            except StopIteration:
                pass
            return obj

        def __lshift__(self, other):
            """Agrega subobjetos al objeto"""
            #
            # Hago un truquito para hacer que el operador permita encadenar
            # objetos con facilidad. Si se aplica a otro ObjEntry, lo que
            # devuelve es una copia de si mismo pero con un puntero al otro
            # objeto (tail).
            # 
            # Todos mis campos son constantes o diccionarios / listas que se
            # modifican in-place, asi que el objeto devuelto es a todos los
            # efectos practicos este mismo. La unica diferencia es que el
            # operador agrega los nuevos elementos al ultimo objeto interno,
            # no directamente a este. Ejemplo
            #
            # x.html << [
            #     x.head << x.title << "Mi titulo",
            # ]
            #
            # Sin "tail", head << title << "mi titulo" seria como:
            #
            # ((head << title) << "mi_titulo")
            #                ^-- head << "mi titulo"
            #
            # Para poder librarnos de este truco, tendriamos que usar un
            # operador con asociatividad hacia la derecha, y el unico que hay
            # en python es "pow" (**), que no queda muy bonito:
            #
            # head ** title ** "Mi titulo"
            #
            # Otra opcion seria implementar __setattr__ en el BuilderHelper,
            # porque el operador "=" si asocia a la derecha:
            #
            # x.head = x.title = "Mi titulo"
            #
            # Pero el problema es que una llamada a funcion no puede ser
            # un lvalue:
            #
            # x.head = x.title(align="left") = "Mi titulo"
            #
            (self.tail or self).flatten(other)
            if hasattr(other, "flatten"):
                if not self.tail:
                    self = copy(self)
                self.tail = other
            return self

        def __call__(self, *arg, **kw):
            """Agrega atributos al objeto"""
            self.kw.update(kw)
            self.arg.extend(arg)
            return self

    def __getattr__(self, name):
        """Devuelve un ObjEntry"""
        return BuilderHelper.ObjEntry(name)


def escape(item, escape=cgi.escape, unicode=unicode):
    if item is None:
        return "&nbsp;"
    if not isinstance(item, unicode):
        item = str(item).decode("utf-8")
    return escape(item, quote=True).encode('ascii', 'xmlcharrefreplace')


class IndentList(list):

    def __init__(self, indent="  ", values=None):
        super(IndentList, self).__init__(values or tuple())
        self._offset = 0
        self._indent = indent

    def append(self, item):
        item = self._indent * self._offset + item
        return super(IndentList, self).append(item)

    def indent(self):
        self._offset += 1

    def dedent(self):
        self._offset -= 1

    def __str__(self):
        return "\n".join(self)


class TagBuilder(object):

    """Objeto que implementa el patron Builder.

    Un Builder implementa una funcion por cada tipo de nodo que pueda haber
    en el objeto. Dichas funciones deben funcionar de forma parecida a un
    ContextManager (deben ser iteradores que generen un solo objeto), pero no
    hay que decorarlas con @contextmanager.
    
    Las funciones recibiran un parametro fijo "parent", y los parametros
    posicionales y nombrados que se hayan usado en el Helper.
    
        Node parent, [*args], [**kw]

    El objeto que debe devolver (lanzar, yield) la funcion es una tupla:
    
        (Objeto construido, funcion para agregarle elementos al objeto)

    Si un Helper tiene un nodo para el que no haya una funcion en el Builder,
    utiliza la funcion __call__.  En este caso, los parametros que se le pasan
    al Builder son distintos: se le pasa el parent, el nombre del nodo, una
    tupla con los argumentos posicionales, y un dict con los argumentos
    nombrados.

        Node parent, String name, Tuple arg, Dict kw

    Por ejemplo:

    class HtmlBuilder(object):
    
        def __init__(self):
            self._result = []

        def print_tag(self, tag, func=None):
            self._result.append("<%s>"  % tag)
            yield (tag, func)
            self._result.append("</%s>"  % tag)

        def html(self, parent):
            # La funcion siempre recibe "parent", y puede recibir o no
            # otros parametros. El SpecBuilder se encarga de desempaquetar
            # los parametros que se hayan asignado con el BuilderHelper.
            return self.print_tag("html")
    
        def head(self, parent):
            return self.print_tag("head")

        def title(self, parent):
            return self.print_tag("title")

        def body(self, parent):
            return self.print_tag("body")

        def p(self, parent):
            return self.print_tag("p", lambda x: self._result.append(str(x)))

        def __call__(self, parent, name, arg, kw):
            print "TAG NO RECONOCIDA! %s" % name
            return self.print_tag(name)

        def __str__(self):
            return "\n".join(self._result)
    """

    def __init__(self):
        self._result = IndentList()

    def __call__(self, parent, name, arg, kw, escape=escape):
        tag = name
        if arg:
            comments = " ".join(escape(v) for v in arg)
            self._result.append("<!-- %s -->" % comments)
        if kw:
            attribs = ('%s="%s"' % (k, escape(v)) for k, v in kw.iteritems())
            tag = "%s %s" % (name, " ".join(attribs))
        self._result.append("<%s>" % tag)
        self._result.indent()
        def append(literal, result=self._result):
            result.append("%s" % escape(literal))
        yield(self._result, append)
        self._result.dedent()
        self._result.append("</%s>" % name)

    def __str__(self):
        return str(self._result)


class SpecBuilder(object):
    
    """Constructor de Helpers.
    
    Analiza un helper y genera una clase Helper adaptada a la estructura
    de ese helper.
    
    Para construir un Helper basado en una especificacion, el proceso es el
    siguiente:
    
    1.- Se construye la especificacion, con un BuilderHelper normal:
    
    x = BuilderHelper()
    
    HtmlSpec = x.html << [
        x.head(num=1) << x.title << "Titulo del documento",
        x.body(num=1) << [
            x.p << "Parrafos del texto"
        ]
    ]
    
    2.- Se crea el Helper especializado
    
    HtmlHelper = HtmlSpec.build(SpecBuilder())
    
    3.- Ya se puede usar el nuevo Helper para crear estructuras. El helper
    comprobara durante la construccion que la estructura cumple los requisitos
    especificados con el primer helper.
    
    x = HtmlHelper()
    
    x.html << [
        x.head << x.p << 'Esto da error: "p" no es un subobjeto de 'head'"
    ]
    """

    def make_class(self, rootname):
        """Construye una clase Builder"""
        self._last = NodeDescriptor(rootname, 1)
        ObjEntry   = BuilderHelper.ObjEntry
        def get(self, attr, ROOTDESC=self._last):
            obj = ObjEntry(attr)
            if attr == rootname:
                obj.descriptor = ROOTDESC
            return obj
        return type(rootname, (object,), { '__getattr__': get })

    def __call__(self, parent, name, arg, kw):
        if parent is None:
            # Construyo la clase Helper
            yield (self.make_class(name), None)
        else:
            # Extraigo los parametros que utilizo.
            args   = kw.get("args", 0)
            kwargs = kw.get("kwargs", 0)
            num    = kw.get("num", 0)
            # Anoto la dependencia.
            anew = NodeDescriptor(name, num, args, kwargs)
            self._last[name] = anew
            # Proceso el nuevo nodo
            prev, self._last = self._last, anew
            yield (parent, None)
            # Y restauro el estado anterior.
            self._last = prev


if __name__ == "__main__":
    
    import sys

    headers = ["Nombre", "Instrumento"]
    data    = [
                ("Bruce Dickinson", "Cantante"),
                ("Steve Harris", "Bajo"),
                ("Dave Murray", "Guitarra"),
                ("Janick Guers", "Guitarra"),
                ("Adrian Smith", "Guitarra"),
                ("Nicko McBrain", "Bateria"),
              ]

    x = BuilderHelper()

    # Una especificacion de tabla HTML.

    HtmlSpec = x.html << [
        x.head(num=1) << x.title(num=1) << "Titulo del documento",
        x.body(num=1) << [
            x.h1  << "Cabecera",
            x.div << x.table(num=1) << [
                x.thead(num=1) << x.tr(num=1) << x.th << "Titulos de las Columnas",
                x.tbody(num=1) << [
                    x.tr << [
                        x.td << "Contenido de las celdas"
                    ]
                ]
            ]
        ]
    ]

    # Muestro la especificacion

    tb = TagBuilder()
    HtmlSpec.build(tb)
    print(str(tb))

    # Un Helper que utiliza esa especificacion

    HtmlHelper = HtmlSpec.build(SpecBuilder())
    x = HtmlHelper()

    # Una tabla HTML

    html = x.html << [
        x.head << x.title << "Miembros de Iron Maiden",
        x.body << [
            x.h1 << "Miembros de Iron Maiden",
            x.div(align="center") << x.table(width="80%") << [
                x.thead << x.tr << (x.th << h for h in headers),
                x.tbody << (
                    x.tr << (
                        x.td << item for item in row
                    ) for row in data
                )
            ]
        ]
    ]

    print html.build(TagBuilder())

    if len(sys.argv) > 1 and "-d" in sys.argv[1:]:
        print "\n\n\n*** DEBUG: ***\n\n\n"
        print(html.build(Builder()))
