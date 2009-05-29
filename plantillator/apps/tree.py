#!/usr/bin/env python
# -*- vim: expandtab tabstop=4 shiftwidth=4 smarttab autoindent


import Tkinter as tk
from idlelib.TreeWidget import TreeItem, TreeNode


class Tagger(object):

    _NAMING_ATTRIBS = ["descripcion", "nombre", "host"]

    def name(self, data, name=None, hint=None):
        """Intenta dar nombre a un item, en funcion de su tipo.
        "hint" es una pista para crear el nombre (por ejemplo, la clave si el
        item ha salido de un diccionario, el indice si el item ha salido de
        una lista)
        """
        if not name and isinstance(data, dict):
            for attr in self._NAMING_ATTRIBS:
                if attr in data:
                    return data[attr]
        elif not hasattr(data, "__iter__"):
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


class Item(TreeItem):

    def __init__(self, name, data=None, tagger=None):
        TreeItem.__init__(self)
        self.name = name
        self.data = data
        self.tagger = tagger or Tagger()
        # check properties
        self.expandable = (data is not None and hasattr(data, '__iter__'))
        self.editable = False
        if isinstance(data, dict):
            self.GetSubList = self._dict
        elif hasattr(data, '__iter__'):
            if hasattr(data, '__getitem__'):
                # no ordenamos los elementos de una lista, porque si se
                # elige una lista el orden es importante
                # (por ejemplo: la secuencia de lineas de una plantilla)
                self.GetSubList = self._list
            else:
                self.GetSubList = self._set
        else:
            self.GetSubList = lambda self: None

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

    def _list(self):
        return list(self.tagger.item(x, hint="[%d]"%index)
                      for index, x in enumerate(self.data))

    def _set(self):
        return sorted(self._list())

    def _dict(self):
        return sorted(self.tagger.item(x, name)
                      for name, x in self.data.iteritems()
                      if not name.startswith('_'))


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
        node = TreeNode(self, None, self.tagger.item(data, name))
        node.expand()
        if expanded:
            for item in node.children:
                self._expand(item)
        node.update()

    def _expand(self, node):
        node.expand()
        for item in node.children:
            self._expand(item)
