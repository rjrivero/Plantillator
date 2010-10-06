#!/usr/bin/env python


import cgi
from contextlib import contextmanager


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
            self.name   = name
            self.arg    = list(arg) if arg else []
            self.kw     = kw or dict()
            self.nested = list()
            self.tail   = None

        def flatten(self, nested):
            """Aplasta una lista compuesta por objetos y sublistas"""
            # Ya no acepto callables como shortcuts para generar sublistas.
            # Mucho mejor usar list comprehensions en ese caso.
            if not hasattr(nested, '__iter__') or hasattr(nested, 'iteritems'):
                self.nested.append(nested)
                return
            for item in nested:
                self.flatten(item)

        def build(self, builder, parent=None):
            """Construye el objeto usando el builder especificado"""
            with builder(parent, self.name, self.arg, self.kw) as (obj, append):
                if not append:
                    append = lambda item: None
                for item in self.nested:
                    if not hasattr(item, 'build'):
                        append(item)
                    else:
                        item.build(builder, obj)
            return obj

        def __lshift__(self, other):
            """Agrega subobjetos al objeto"""
            #
            # Utilizo un objeto "tail" que marca el ultimo sub-objeto
            # que he agregado directamente a este. Asi puedo simplificar
            # la creacion de objetos que tienen un solo subobjeto:
            #
            # html << [
            #     head << title << "Mi titulo",
            #     body << h1 << "Mi cabecera!"
            # ]
            #
            (self.tail or self).flatten(other)
            if hasattr(other, "flatten"):
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
    if not isinstance(item, unicode):
        item = str(item).decode("utf-8")
    return escape(item, quote=True).encode('ascii', 'xmlcharrefreplace')


class TagBuilder(object):

    """Objeto que implementa el patron Builder.
    
    Se puede utilizar como un contextmanager, pasandole los siguientes
    parametros:
    
        Node parent, String name, Tuple arg, Dict kw

    Al utilizarlo devuelve dos elementos:
    
        - Un objeto que se puede usar como parent para todos los objetos
          anidados
        - Una funcion que sirve para procesar elementos anidados que no
          sean objetos.
    """

    def __init__(self):
        self._result = []
        self._indent = 0

    @contextmanager
    def __call__(self, parent, name, arg, kw, escape=escape):
        tag, indent = name, "  " * self._indent
        if arg:
            comments = " ".join(escape(v) for v in arg)
            self._result.append("%s<!-- %s -->" % (indent, comments))
        if kw:
            attribs = ('%s="%s"' % (k, escape(v)) for k, v in kw.iteritems())
            tag = "%s %s" % (name, " ".join(attribs))
        self._result.append("%s<%s>" % (indent, tag))
        self._indent += 1
        def append(literal, indent="  "*self._indent, result=self._result):
            result.append("%s%s" % (indent, escape(literal)))
        yield(name, append)
        self._indent -= 1
        self._result.append("%s</%s>" % (indent, name))

    def __str__(self):
        return "\n".join(self._result)


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
    
    if len(sys.argv) > 1 and "-d" in sys.argv[1:]:
        print "\n\n\n*** DEBUG: ***\n\n\n"
        print(html.build(Builder()))
