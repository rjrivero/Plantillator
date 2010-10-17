#!/usr/bin/env python


from itertools import chain
from copy import deepcopy

from .builder import BuilderHelper, SpecBuilder, TagBuilder


x = BuilderHelper()

TableHelper = (x.table << [
    """
    Especificacion de una tabla de documentacion.

    Las tablas estan compuestas por:

    - Una cabecera (head), con varias columnas (col). Cada columna
      tiene un titulo y una funcion que extrae de los objetos fila
      (row) el valor del campo correspondiente a esa columna.
      
    - Un cuerpo (body), dividido en grupos (group). Cada grupo es una
      mini-cabecera, un colspan que abarca todas las celdas de la fila.
      Los grupos tienen una o varias filas (row).
    """,
    x.head(num=1, args="titulo o None") << [
        x.col(args="colname") << """getter function.
            A function that receives a row object and must return a value.
            """
    ],
    x.body(num=1) << [
        x.rows(title="titulo o None") << "row object list",
    ]
]).build(SpecBuilder())


class Toggle(object):

    """Objeto que va altenando entre dos valores"""

    def __init__(self, even, odd):
        self.index = 1
        self.values = (even, odd)

    def next(self):
        self.index = 1 - self.index
        return self.values[self.index]

    def reset(self):
        self.index = 0


class TableBuilder(object):

    STYLE = {
        'table':   {'width': '100%', 'cellspacing': '0', 'class' : 'htable'},
        'head':    {'class': 'head'},
        'body':    {'class': 'body'},
        'titletr': {'class': 'title'},
        'titletd': {'class': 'title'},
        'eventr':  {'class': 'even'},
        'oddtr':   {'class': 'odd'},
        'firstd':  {'class': 'first'},
        'eventd':  {'class': 'even'},
        'oddtd':   {'class': 'odd'},
        'eventh':  {'class': 'even'},
        'oddth':   {'class': 'odd'},
    }

    def __init__(self, style=None, vertical=False, repeat=False):
        """Construye una tabla a partir de los datos dados.
        
        Construye una tabla HTML. Puede recibir un diccionario con
        atributos para los siguientes elementos:
        
        'table':   <table>.      Por defecto, {'width': '100%', 'cellspacing': '0', 'class' : 'htable'},
        'head':    <thead><tr>.  Por defecto, {'class': 'head'},
        'body':    <tbody>.      Por defecto, {'class': 'body'},
        'titletr': <tbody><tr>.  Por defecto, {'class': 'title'},
        'titletd': <tbody><tr>.  Por defecto, {'class': 'title'},
        'eventr':  <tr> pares.   Por defecto, {'class': 'even'},
        'oddtr':   <tr> impares. Por defecto, {'class': 'odd'},
        'firstd':  <td> primera. Por defecto, {'class': 'first'},
        'eventd':  <td> pares.   Por defecto, {'class': 'even'},
        'oddtd':   <td> impares. Por defecto, {'class': 'odd'},
        'eventh':  <th> pares.   Por defecto, {'class': 'even'},
        'oddth':   <th> impares. Por defecto, {'class': 'odd'},

        El estilo por defecto de la tabla es "htable" si la tabla
        tiene layout horizontal, y "vtable" si tiene layout vertical.

        El layout de la tabla por defecto es horizontal: hay un thead
        con los datos de las columnas, y un tbody con una fila por cada
        fila de datos. El titulo del grupo de filas, si se ha
        especificado, se incrusta en un tr/td con un colspan extendido
        a todas las columnas.
        
        Se puede hacer que el layout sea vertical, con una primera
        columna con los titulos y una segunda con los valores, uno por
        cada elemento de la tabla. Para eso, hay que pasar el parametro
        "vertical" = True. En ese caso, el titulo especificado para
        el grupo de columnas se usa como cabecera de esas columnas.
        
        Si repeat=True, se repite la cabecera en cada grupo de filas.
        """
        self._style = deepcopy(TableBuilder.STYLE)
        if vertical:
            self._style['table']['class'] = 'vtable'
        if style:
            self._style.update(style)
        self._table  = None
        self._trcss = Toggle("eventr", "oddtr")
        self._thcss = Toggle("eventh", "oddth")
        self._vertical = vertical
        self._repeat = repeat

    def table(self, parent, x=BuilderHelper()):
        """Crea un nodo de tipo "table", top level"""
        self._table = x.table(**self._style['table'])
        self._header = list()
        self._body   = list()
        self._htitle = None
        builder = TagBuilder()
        yield (builder, None)
        if not self._vertical:
            self._layout_horizontal()
        else:
            self._layout_vertical()
        self._table.build(builder)

    def _layout_horizontal(self, x=BuilderHelper()):
        style, colspan = self._style, len(self._header)
        self._table << (
            x.thead << x.tr(**style['head']) << (
                (x.th(**style[self._thcss.next()]) << colname)
                for (colname, getter) in self._header
            ),
            x.tbody(**style['body']) << (
                self._layout_horizontal_row(group, rows, colspan)
                for (group, rows) in self._body
            )
        )

    def _layout_horizontal_row(self, group, rows, colspan,
                               tdtoggle=Toggle("eventd", "oddtd"),
                               x=BuilderHelper()):
        trtoggle, style = self._trcss, self._style
        if group:
            trtoggle.reset()
            yield x.tr(**style['titletr']) << (
                x.td(colspan=colspan, **style['titletd']) << group
            )
        if self._repeat:
            thtoggle = self._thcss
            thtoggle.reset()
            yield x.tr(**style['head']) << (
                (x.th(**style[thtoggle.next()]) << colname)
                for (colname, getter) in self._header
            )
        for row in rows:
            tdtoggle.reset()
            firstgetter = self._header[0][1]
            othergetter = self._header[1:]
            yield x.tr(**style[trtoggle.next()]) << (
                x.td(**style['firstd']) << firstgetter(row),
                ((x.td(**style[tdtoggle.next()]) << getter(row))
                for (label, getter) in othergetter)
            )

    def _layout_vertical(self, x=BuilderHelper()):
        style, thtoggle = self._style, self._thcss
        if self._htitle or any(group for (group, rows) in self._body):
            self._table << x.thead << x.tr(**style['head']) << (
                x.th(**style[thtoggle.next()]) << self._htitle,
                ((x.th(colspan=len(rows), **style[thtoggle.next()]) << group)
                 for (group, rows) in self._body
                )
            )
        self._table << x.tbody(**style['body']) << (
            self._layout_vertical_col(colname, getter)
            for (colname, getter) in self._header
        )

    def _layout_vertical_col(self, colname, getter,
                               tdtoggle=Toggle("eventd", "oddtd"),
                               x=BuilderHelper()):
        trtoggle, style = self._trcss, self._style
        tdtoggle.reset()
        yield x.tr(**style[trtoggle.next()]) << (
            x.th(**style['eventh']) << colname,
            ((x.td(**style[tdtoggle.next()]) << getter(row))
                for row in chain(*(rows for (group, rows) in self._body))
            )
        )

    def head(self, parent, title=None):
        self._title = title
        yield (None, None)

    def col(self, parent, colname):
        """Crea una columna de cabecera. Debe indicarse el nombre."""
        def append(getter):
            self._header.append((colname, getter))
        yield (None, append)

    def body(self, parent):
        """Crea un nodo 'body'"""
        yield (None, None)

    def rows(self, parent, title=None):
        items = list()
        yield (None, (lambda it: items.append(it)))
        self._body.append((title, items))
