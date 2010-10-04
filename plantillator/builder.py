#!/usr/bin/env python


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

        __slots__ = ("name", "attr", "nested", "tail")

        def __init__(self, name, attr=None):
            self.name = name
            self.attr = attr or dict()
            self.nested = list()
            self.tail = None

        def flatten(self, nested):
            """Aplasta una lista compuesta por objetos, callables y sublistas"""
            if hasattr(nested, '__call__'):
                nested = nested()
            if not hasattr(nested, '__iter__'):
                self.nested.append(nested)
                return
            for item in nested:
                self.flatten(item)
            
        def build(self, builder, parent=None):
            """Construye el objeto usando el builder especificado"""
            obj    = builder.create_node(parent, self.name, self.attr)
            nested = (item if not hasattr(item, 'build')
                           else item.build(builder, obj)
                           for item in self.nested)
            for item in nested:
                builder.add_content(obj, item)
            builder.node_completed(self.name, obj)
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

        def __call__(self, **kw):
            """Agrega atributos al objeto"""
            self.attr.update(kw)
            return self

    def __getattr__(self, name):
        """Devuelve un ObjEntry"""
        return BuilderHelper.ObjEntry(name)


class Builder(object):

    """Objeto que implementa el patron Builder.
    
    Tiene tres metodos:
    
    - create_node(Node parent, String name, Dict kw):
        Crea el nodo con el nombre, ancestro y atributos especificados.

    - add_content(Node obj, <variable> data):
        Agrega el objeto o dato "data" al nodo "obj".

    - node_completed(String name, Node obj):
        Marca el fin de la construccion del objeto.

    El Builder por defecto es un objeto de depuracion, muestra las
    secuencias de llamadas a los nodos.
    """

    def __init__(self):
        self._result = []
        self._indent = 0

    def create_node(self, parent, name, kw):
        """Crea un nodo con el parent, name y atributos especificados"""
        self._result.append("  "*self._indent + "create_node(parent:%s, name:%s, kw:%s)"
                                              % (repr(parent), repr(name), repr(kw)))
        self._indent += 1
        return name if parent else self

    def add_content(self, node, content):
        """Agrega contenido al nodo.
        
        El contenido puede ser:
            - Un valor literal
            - Un sub-objeto
        """
        self._result.append("  "*self._indent + "add_content(node:%s, content:%s)"
                                              % (repr(node), repr(content)))

    def node_completed(self, name, node):
        """Marca el nodo como finalizado"""
        self._indent -= 1
        self._result.append("  "*self._indent + "node_completed(name:%s, node:%s)"
                                              % (repr(name), repr(node)))

    def __str__(self):
        return "\n".join(self._result)

    def __repr__(self):
        return "<DebugBuilder>"


class TagBuilder(object):

    """Builder de ejemplo para arboles de etiquetas (como HTML)"""

    def __init__(self):
        self._result = []
        self._indent = 0

    def create_node(self, parent, name, kw):
        attribs = " ".join('%s="%s"' % (k, v) for k, v in kw.iteritems())
        if attribs:
            attribs = " " + attribs
        self._result.append("  "*self._indent + "<" + name + attribs + ">")
        self._indent += 1
        return self

    def add_content(self, node, content):
        if content is not self:
            self._result.append("  "*self._indent + str(content))

    def node_completed(self, name, node):
        self._indent -= 1
        self._result.append("  "*self._indent + "</" + name + ">")

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
