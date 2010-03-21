#!/usr/bin/env python
# -*- vim: expandtab tabstop=4 shiftwidth=4 smarttab autoindent


import Tkinter as tk
from idlelib.TreeWidget import TreeItem, TreeNode
from itertools import chain


_NAMING_ATTRIBS = ['id', 'nombre', 'descripcion']


class Tagger(object):

    def name(self, data, name=None, hint=None):
        """Intenta dar nombre a un item, en funcion de su tipo.
        "hint" es una pista para crear el nombre (por ejemplo, la clave si el
        item ha salido de un diccionario, el indice si el item ha salido de
        una lista)
        """
        #if not name and hasattr(data, 'iteritems'):
        #    return ", ".join(str(data.get(x,"")) for x in _NAMING_ATTRIBS)
        if not name:
            # es un elemento de una lista: lo convierto a string y, si viene
            # con una "cuenta de repeticiones", la incluyo.
            return "%s (%d)" % (str(data), hint) if hint is not None else str(data)
        elif not hasattr(data, "__iter__"):
            # Es un atributo de un objeto, un elemento de diccionario.
            # indico su nombre y su valor.
            return "%s = %s" % (name, str(data)) if name else str(data)
        return name or hint or "<>"

    def icon(self, item):
        """Devuelve el nombre del icono a usar"""
        return "folder" if item.expandable else "plusnode"

    def selicon(self, item):
        """Devuelve el nombre del icono a usar cuando el item se abre"""
        return "openfolder" if item.expandable else "minusnode"

    def item(self, data, name=None, hint=None):
        return Item(self.name(data, name, hint), data, self)

    def filter_dict(self, data):
        """Itera sobre los elementos del dict, devolviendo clave y valor"""
        try:
            children = data._type._DOMD.descendants
        except (AttributeError, KeyError):
            return data.iteritems()
        else:
            items = ((child, data.get(child)) for child in children)
            items = (x for x in items if x[1])
            return chain(data.iteritems(), items)

    def filter_list(self, data):
        """Itera sobre los elementos de la lista/set, devolviendo indice y valor"""
        try:
            return enumerate(sorted(data))
        except TypeError:
            # la lista tiene elementos de distintos tipos, no se puede ordenar
            return enumerate(data)

    def filter_orderedset(self, data):
        """Itera sobre los elementos del orderedset, devolviendo valor y repeticiones"""
        return data.itercounts()


class Item(TreeItem):

    def __init__(self, name, data=None, tagger=None):
        TreeItem.__init__(self)
        self.name = name
        self.data = data
        self.tagger = tagger or Tagger()
        # check properties
        self.expandable = True
        self.editable = False
        if hasattr(data, 'itercounts'):
            self.GetSubList = self._orderedset
        elif hasattr(data, 'iteritems'):
            self.GetSubList = self._dict
        elif hasattr(data, '__iter__'):
            self.GetSubList = self._list
        else:
            self.expandable = False
            #self.GetSubList = lambda self: None

    def __cmp__(self, other):
        # not expandable items first, then alphabetical order
        retval = cmp(self.expandable, other.expandable)
        return retval if retval != 0 else cmp(self.name, other.name)

    def GetText(self):
        return self.name

    def isExpandable(self):
        return self.expandable

    def isEditable(self):
        return self.editable

    def GetIconName(self):
        return self.tagger.icon(self)

    def GetSelectedIconName(self):
        return self.tagger.selicon(self)

    def _orderedset(self):
        return list(self.tagger.item(x, hint=count)
                      for x, count in self.tagger.filter_orderedset(self.data))

    def _list(self):
        return list(self.tagger.item(x)
                      for index, x in self.tagger.filter_list(self.data))

    def _dict(self):
        return sorted(self.tagger.item(x, name)
                      for name, x in self.tagger.filter_dict(self.data))


class TreeCanvas(tk.Canvas):

    def __init__(self, master, tagger=None):
        tk.Canvas.__init__(self, master)
        self.tagger = tagger or Tagger()
        self.config(bg='white')
        # add scrollbar
        self.scrollbar = tk.Scrollbar(master)
        self.config(yscrollcommand=self.scrollbar.set)
        self.scrollbar.config(command=self.yview)
        # pack widgets
        self.pack(side=tk.LEFT, expand=tk.YES, fill=tk.BOTH)
        self.scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

    def wheel(self, event):
        if event.num == 5 or event.delta <= -120:
            self.yview_scroll(2, 'units')
        if event.num == 4 or event.delta >= 120:
            self.yview_scroll(-2, 'units')

    def show(self, name, data, expanded=False):
        self.node = TreeNode(self, None, self.tagger.item(data, name))
        self.node.expand()
        if expanded:
            for item in self.node.children:
                self._expand(item)
        self.node.update()

    def _expand(self, node):
        node.expand()
        for item in node.children:
            self._expand(item)
