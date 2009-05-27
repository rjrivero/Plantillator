#!/usr/bin/env python
# -*- vim: expandtab tabstop=4 shiftwidth=4 smarttab autoindent


import Tkinter as tk
from idlelib.TreeWidget import TreeItem, TreeNode

class BaseItem(TreeItem):    def __init__(self, name):        self.name = name        self.expandable = self.isExpandable()
    def __cmp__(self, other):
        return cmp(self.name, other.name)
    def GetText(self):        return self.name    def isExpandable(self):        return False    def GetSubList(self):        return None    def GetIconName(self):        return "folder" if self.expandable else "minusnode"    def GetSelectedIconName(self):        return "openfolder" if self.expandable else "minusnode"
class DictItem(BaseItem):    def __init__(self, name, data=None):	self.data = data or {}	BaseItem.__init__(self, name)    def isExpandable(self):	return bool(self.data)        def GetSubList(self):        simple, compound = [], []        for name, val in self.data.iteritems():            if name.startswith("_"):                continue            if isinstance(val, dict):                compound.append(DictItem(name, val))            elif hasattr(val, "__iter__"):                compound.append(ListItem(name, val))            else:                simple.append(BaseItem(name + " = " + str(val)))        return sorted(simple) + sorted(compound)_NAMING_ATTRIBS = ["descripcion", "nombre", "host"]                              class ListItem(BaseItem):    def __init__(self, name, data=None):	self.data = data or {}	BaseItem.__init__(self, name)    def isExpandable(self):    	return bool(self.data)        def GetSubList(self):        simple, compound = [], []
        for index, val in enumerate(self.data):            name = "[%s]" % str(index)            if isinstance(val, dict):
                for attr in _NAMING_ATTRIBS:                    if attr in val:                        name = val[attr]                        break                compound.append(DictItem(name, val))            elif hasattr(val, "__iter__"):                compound.append(ListItem(name, val))            else:                simple.append(BaseItem(name + " = " + str(val)))        return sorted(simple) + sorted(compound)def Item(name, data=None):    if isinstance(data, dict):        return DictItem(name, data)    elif hasattr(data, "__iter__"):        return ListItem(name, data)    else:        return BaseItem("%s = %s" % (name, str(data)))


class TreeCanvas(tk.Canvas):

    def __init__(self, master):
        tk.Canvas.__init__(self, master)
        self.config(bg='white')
        # add scrollbar
        self.scrollbar = tk.Scrollbar(master)
        self.config(yscrollcommand=self.scrollbar.set)
        self.scrollbar.config(command=self.yview)
        # pack widgets
        self.pack(side=tk.LEFT, expand=tk.YES, fill=tk.BOTH)
        self.scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        # connect to mouse wheel
        self.bind("<MouseWheel>", self._wheel)
        self.bind("<Button-4>", self._wheel)
        self.bind("<Button-5>", self._wheel)

    def _wheel(self, event):
        if event.num == 5 or event.delta == -120:
            self.yview_scroll(2, 'units')
        if event.num == 4 or event.delta == 120:
            self.yview_scroll(-2, 'units')

    def show(self, name, data):
        node = TreeNode(self, None, Item(name, data))        node.update()        node.expand()
