#!/usr/bin/env python
# -*- vim: expandtab tabstop=4 shiftwidth=4 smarttab autoindent


from operator import isMappingType
from idlelib.TreeWidget import TreeItem


class BaseItem(TreeItem):

    def __init__(self, name):
        self.name = name
        self.expandable = self.isExpandable()

    def GetText(self):
        return self.name

    def isExpandable(self):
        return False

    def GetSubList(self):
        return None

    def GetIconName(self):
        return "folder" if self.expandable else "minusnode"

    def GetSelectedIconName(self):
        return "openfolder" if self.expandable else "minusnode"


class DictItem(BaseItem):

    def __init__(self, name, data=None):
	self.data = data or {}
	BaseItem.__init__(self, name)

    def isExpandable(self):
	return bool(self.data)
    
    def GetSubList(self):
        simple, compound = [], []
        for name, val in self.data.iteritems():
            if name.startswith("_"):
                continue
            if isinstance(val, dict):
                compound.append(DictItem(name, val))
            elif hasattr(val, "__iter__"):
                compound.append(ListItem(name, val))
            else:
                simple.append(BaseItem(name + " = " + str(val)))
        return simple + compound


_NAMING_ATTRIBS = ["descripcion", "nombre", "host"]
                              
class ListItem(BaseItem):

    def __init__(self, name, data=None):
	self.data = data or {}
	BaseItem.__init__(self, name)

    def isExpandable(self):
	return bool(self.data)
    
    def GetSubList(self):
        simple, compound = [], []
        for index, val in enumerate(self.data):
            name = "[%s]" % str(index)
            if isinstance(val, dict):
                for attr in _NAMING_ATTRIBS:
                    if attr in val:
                        name = val[attr]
                        break
                compound.append(DictItem(name, val))
            elif hasattr(val, "__iter__"):
                compound.append(ListItem(name, val))
            else:
                simple.append(BaseItem(name + " = " + str(val)))
        return simple + compound


def Item(name, data=None):
    if isinstance(data, dict):
        return DictItem(name, data)
    elif hasattr(data, "__iter__"):
        return ListItem(name, data)
    else:
        return BaseItem("%s = %s" % (name, str(data)))
