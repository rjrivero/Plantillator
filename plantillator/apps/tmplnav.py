#!/usr/bin/env python
# -*- vim: expandtab tabstop=4 shiftwidth=4 smarttab autoindent


import os
import os.path
import sys
import logging
import glob
import re
import Tkinter as tk
from traceback import print_exc, format_exception_only
from optparse import OptionParser

try:
    from data.namedtuple import NamedTuple
except ImportError:
    import os.path
    import sys
    script_path = os.path.dirname(os.path.abspath(sys.argv[0]))
    sys.path.append(os.path.join(script_path, ".."))
    from data.namedtuple import NamedTuple

from data.pathfinder import PathFinder, FileSource
from engine.cmdtree import CommandTree
from tmpl.tmpltokenizer import TmplTokenizer
from apps.tree import TreeCanvas, Tagger


class TmplTagger(Tagger):

    def name(self, item, name, hint):
        return name or str(item) or " "

    def icon(self, item):
        if item.expandable:
            return "python" if hasattr(item.data, "token") else "folder"
        return "plusnode"

    def selicon(self, item):
        if item.expandable:
            return "python" if hasattr(item.data, "token") else "openfolder"
        return "minusnode"

    def item(self, data, name=None, hint=None):
        item = Tagger.item(self, data, name, hint)
        item.editable = not item.expandable
        return item


class TmplNav(tk.Tk):

    def __init__(self, templates, geometry="800x600"):
        tk.Tk.__init__(self)
        self.title("TemplateNav")
        self.hist = list()
        self.cursor = 0
        self.hlen = 20
        self.templates = templates
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
        entry.bind("<Up>", self.keyup)
        entry.bind("<Down>", self.keydown)
        self.button = tk.Button(self.frames.top, text="Filtrar",
                                command=self.clicked, padx=5)
        self.button.pack(side=tk.RIGHT)
        # lower frame: the data canvas
        self.canvas = TreeCanvas(self.frames.bottom, TmplTagger())
        # set the geometry
        entry.focus()
        self.geometry(geometry)
        self.clicked()
        # connect to mouse wheel
        self.bind("<MouseWheel>", self.canvas.wheel)
        self.bind("<Button-4>", self.canvas.wheel)
        self.bind("<Button-5>", self.canvas.wheel)

    def clicked(self, *skip):
        """Presenta los datos seleccionados"""
        fname = self.entry.get()
        if fname:
            try:
                source = FileSource(finder(fname), finder)
            except:
                pass
            else:
                if not source.id in self.templates:
                    self.templates[source.id] = CommandTree(
                        source, TmplTokenizer(source).tree())
        self.canvas.show("root", self.templates)

    def keyup(self, *skip):
        """Selecciona un elemento anterior en la historia"""
        if self.cursor < len(self.hist)-1:
            self.cursor += 1
            self.entry.set(self.hist[-self.cursor-1])

    def keydown(self, *skip):
        """Selecciona un elemento posterior en la historia"""
        if self.cursor > 0:
            self.cursor -= 1
            self.entry.set(self.hist[-self.cursor-1])


VERSION           = "0.1"
OPTIONS_ERRNO     = -1
FILE_ERRNO        = -2
DATA_ERRNO        = -3
TRANSLATION_ERRNO = -4
UNKNOWN_ERRNO     = -5
usage = """uso: %prog [opciones] fichero [fichero...]
Carga ficheros de datos (.csv)"""

loglevel = logging.INFO
path = ['.']

parser = OptionParser(usage=usage, version="%%prog %s"%VERSION)
parser.add_option("-p", "--path", dest="path", metavar="PATH",
        help="""Ruta donde buscar las plantillas.
La ruta se especifica al estilo del sistema operativo, por ej.:
C:\\ruta1;C:\\ruta2 (en windows)
/ruta1:/ruta2 (en linux)""")
parser.add_option("-g", "--geometry", dest="geometry", metavar="WxH+X+Y",
        help="""Geometria inicial de la ventana (ej: 800x600+0+0)""")
parser.add_option("-d", "--debug",
        action="store_true", dest="debug", default=False,
        help="Vuelca los mensajes de debug en stderr")

(options, args) = parser.parse_args()
if len(args) < 1:
    parser.print_help(sys.stderr)
    sys.exit(OPTIONS_ERRNO)

if options.debug:
    loglevel = logging.DEBUG
if options.path:
    path.extend(options.path.split(os.pathsep))
geometry = "800x600" if not options.geometry else options.geometry

logging.basicConfig(level=loglevel,
        format='%(asctime)s %(levelname)s %(message)s',
        stream=sys.stderr)

# expando los nombres, que en windows me pueden venir con wildcards
inputfiles = []
for name in args:
    globbed = glob.glob(name)
    if globbed:
        inputfiles.extend(globbed)
    else:
        inputfiles.append(name)

finder = PathFinder(path)
templates = dict()
try:
    for fname in inputfiles:
        source = FileSource(finder(fname), finder)
        templates[source.id] = CommandTree(source, TmplTokenizer(source).tree())
    TmplNav(templates, geometry).mainloop()
except Exception, detail:
    for detail in format_exception_only(sys.exc_type, sys.exc_value):
        sys.stderr.write(str(detail))
    if options.debug:
        print_exc(file=sys.stderr)
    sys.exit(UNKNOWN_ERRNO)
