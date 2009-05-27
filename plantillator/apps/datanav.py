#!/usr/bin/env python
# -*- vim: expandtab tabstop=4 shiftwidth=4 smarttab autoindent


import re
import Tkinter as tk

try:
    from data.namedtuple import NamedTuple
except ImportError:
    import os.path
    import sys
    script_path = os.path.dirname(os.path.abspath(sys.argv[0]))
    sys.path.append(os.path.join(script_path, ".."))
    from data.namedtuple import NamedTuple


_ASSIGNMENT = re.compile(r"^\s*(?P<var>[a-zA-Z]\w*)\s*=(?P<expr>.*)$")


class DataNav(tk.Tk):

    def __init__(self, glob, data, geometry="800x600"):
        tk.Tk.__init__(self)
        self.title("DataNav")
        self.glob = glob
        self.data = data
        self.hist = list()
        self.cursor = 0
        self.hlen = 20
        # split the window in two frames
        self.frames = NamedTuple("Frames", "", top=0, bottom=1)
        self.frames.top = tk.Frame(self, borderwidth=5)
        self.frames.top.pack(side=tk.TOP, fill=tk.X)
        self.frames.bottom = tk.Frame(self)
        self.frames.bottom.pack(side=tk.BOTTOM, expand=tk.YES, fill=tk.BOTH)
        # upper frame: an entry box and an action button
        self.entry = tk.StringVar()
        entry = tk.Entry(self.frames.top, textvariable=self.entry)
        entry.pack(side=tk.LEFT, expand=tk.YES, fill=tk.BOTH)
        entry.bind("<Return>", self.clicked)
        entry.bind("<Up>", self.keyup)        entry.bind("<Down>", self.keydown)        self.button = tk.Button(self.frames.top, text="Filtrar",
                                command=self.clicked, padx=5)        self.button.pack(side=tk.RIGHT)
        # lower frame: the data canvas        self.canvas = TreeCanvas(self.frames.bottom)
        # set the geometry
        entry.focus()        self.geometry(geometry)
        self.clicked()

    def clicked(self, *skip):        name, data = self.entry.get(), self.data
        if not name:
            name = "root"
        else:
            try:
                match = _ASSIGNMENT.match(name)
                if match:
                    exec(name, self.glob, self.data)
                    name = match.group("var")
                data = eval(name, self.glob, self.data)
                if name not in self.hist:
                    self.cursor = 0
                    self.hist.append(name)
                    if len(self.hist) > self.hlen:
                        self.hist.pop(0)
            except Exception as details:
                print "Exception: %s" % str(details)
                return
        self.canvas.show(name, data)
    def keyup(self, *skip):
        if self.cursor < len(self.hist)-1:
            self.cursor += 1
            self.entry.set(self.hist[-self.cursor-1])

    def keydown(self, *skip):
        if self.cursor > 0:
            self.cursor -= 1
            self.entry.set(self.hist[-self.cursor-1])


if __name__ == "__main__":

    from data.pathfinder import PathFinder, FileSource
    from dataloader import DataLoader
    from apps.tree import Item, TreeCanvas

    finder = PathFinder()
    loader = DataLoader()
    source = FileSource(finder("../../../curro/ayto sevilla/AyuntamientoSevilla/datos/DATOS.csv"), finder)
    glob, data = loader.load(source)
    DataNav(glob, data).mainloop()
