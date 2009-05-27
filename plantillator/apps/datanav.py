#!/usr/bin/env python
# -*- vim: expandtab tabstop=4 shiftwidth=4 smarttab autoindent


from Tkinter import *
from idlelib.TreeWidget import TreeItem, TreeNode
import sys
sys.path.append(".")
from data.pathfinder import PathFinder, FileSource
from dataloader import DataLoader
from apps.tree import Item

def filtrar():
    globals()["FILTRO"]()

root = Tk()
topFrame = Frame(root, borderwidth=5)
topFrame.pack(side=TOP, fill=X)
bottomFrame = Frame(root)
bottomFrame.pack(side=BOTTOM, expand=YES, fill=BOTH)
canvas = Canvas(bottomFrame)
canvas.config(bg='white')
canvas.pack(side=LEFT, expand=YES,fill=BOTH)
scrollbar = Scrollbar(bottomFrame)
scrollbar.pack(side=RIGHT, fill=Y)
canvas.config(yscrollcommand=scrollbar.set)
scrollbar.config(command=canvas.yview)
entry = Entry(topFrame)
entry.pack(side=LEFT,expand=YES, fill=BOTH)
button = Button(topFrame, text="Filtrar", command=filtrar, padx=5)
button.pack(side=RIGHT)

finder = PathFinder()
loader = DataLoader()
source = FileSource(finder("../../AyuntamientoSevilla/Datos/DATOS.csv"), finder)
glob, data = loader.load(source)

node = TreeNode(canvas, None, Item("root", data))
node.update()
node.expand()

def FILTRO():
    if not entry.get():
        d = data
    else:
        try:
            d = eval(entry.get(), glob, data)
        except Exception as detail:
            print str(detail)
            return
    node = TreeNode(canvas, None, Item("root", d))
    node.update()
    node.expand()

root.mainloop()
