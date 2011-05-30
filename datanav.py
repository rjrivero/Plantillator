#!/usr/bin/env python
# -*- vim: expandtab tabstop=4 shiftwidth=4 smarttab autoindent


import os
import os.path
import sys
import logging
import glob
import re
import Tkinter as tk

from traceback import print_exc, format_exception_only, print_exception
from optparse import OptionParser
from contextlib import contextmanager

try:
    from plantillator import ShelfLoader, DataError
    from tree import TreeCanvas
except ImportError:
    import os.path
    import sys
    sys.path.append(".")
    from plantillator import ShelfLoader, DataError
    from tree import TreeCanvas


_ASSIGNMENT = re.compile(r"^\s*(?P<var>[a-zA-Z]\w*)\s*=(?P<expr>.*)$")


class DataNav(tk.Tk):


    class Frames(object):
        def __init__(self, top=None, bottom=None):
            self.top = top
            self.bottom = bottom

    def __init__(self, data, geometry="800x600"):
        tk.Tk.__init__(self)
        self.title("DataNav")
        self.data = data
        self.hist = list()
        self.cursor = 0
        self.hlen = 20
        # split the window in two frames
        self.frames = DataNav.Frames()
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
        self.canvas = TreeCanvas(self.frames.bottom)
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
        name, data = self.entry.get(), self.data
        if not name:
            name = "root"
            self.cursor = 0
        else:
            try:
                match = _ASSIGNMENT.match(name)
                if match:
                    exec name in self.data
                    name = match.group("var")
                data = eval(name, self.data)
                if name not in self.hist:
                    self.cursor = 0
                    self.hist.append(name)
                    if len(self.hist) > self.hlen:
                        self.hist.pop(0)
            except Exception as details:
                print "Exception: %s" % str(details)
                return
        # filtro de "data" los elementos que no quiero que se vean
        if hasattr(data, 'iteritems'):
            data = dict((x, y) for (x, y) in data.iteritems()
                if not any (y.__class__.__name__.endswith(s)
                    for s in ("ANY", "NONE", "Meta")))
        self.canvas.show(name, data)

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
PARSE_ERRNO       = -3
UNKNOWN_ERRNO     = -6
usage = """uso: %prog [opciones] fichero [fichero...]
Carga ficheros de datos (.csv)"""

loglevel = logging.INFO
path = ['.']

parser = OptionParser(usage=usage, version="%%prog %s"%VERSION)
parser.add_option("-p", "--path", dest="path", metavar="PATH",
        help="""Ruta donde buscar los ficheros de datos.
La ruta se especifica al estilo del sistema operativo, por ej.:
C:\\ruta1;C:\\ruta2 (en windows)
/ruta1:/ruta2 (en linux)""")
parser.add_option("-g", "--geometry", dest="geometry", metavar="WxH+X+Y",
        help="""Geometria inicial de la ventana (ej: 800x600+0+0)""")
parser.add_option("-d", "--debug",
        action="store_true", dest="debug", default=False,
        help="Vuelca los mensajes de debug en stderr")
parser.add_option("-x", "--profile",
        action="store_true", dest="profile", default=False,
        help="Ejecutar en modo profile (solo carga datos)")
parser.add_option("-l", "--lazy",
        action="store_true", dest="lazy", default=False,
        help="Demora parte del proceso de los datos CSV a tiempo de ejecucion")
parser.add_option("-w", "--warnings",
        action="store_true", dest="warnings", default=False,
        help="Continuar con la carga de datos incorrectos, generando warnings")

(options, args) = parser.parse_args()

options.warnings = dict() if options.warnings else None
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

try:
    shelfname = inputfiles[0]
except IndexError:
    shelfname = "data.shelf"

@contextmanager
def shelf_wrapper(fname):
    loader = ShelfLoader(shelfname, bootstrap=(options.warnings is not None))
    loader.set_datapath(path, warnings=options.warnings, lazy=options.lazy)
    try:
        yield loader
    finally:
        loader.close()

def force_process(meta):
    meta.process()
    for submeta in meta.subtypes.values():
        force_process(submeta)

try:
    if options.profile and os.path.isfile(shelfname):
        os.unlink(shelfname)
    with shelf_wrapper(shelfname) as dataloader:
        dataloader.dump_warnings(options.warnings)
        data = dataloader.data
        # me aseguro de instanciar todas las sublistas, que
        # pueden no estarlo.
        if not options.profile:
            force_process(data['_meta'])
    # Cosas muy feas... no se por que, esto funciona:
    #
    # def test():
    #     v = [1, 2, 3, 4, 5]
    #     print(list(v.index(x) for x in (1, 2)))
    #
    # Pero esto no:
    #
    # def test():
    #     v = [1, 2, 3, 4, 5]
    #     exec "print(list(v.index(x) for x in (1, 2)))" in globals(), locals()
    #
    # El segundo ejemplo lanza un error de que "v no esta definido en globals",
    # ni se molesta en cogerlo de locals.
    #
    # En resumen, usar exec con globals y locals da problemillas, asi que lo que
    # he decidido de momento, al menos para el datanav, es:
    #
    # - pongo data como globals
    # - pongo un diccionario vacio como locals.
    if not options.profile:
        DataNav(data, geometry).mainloop()

except DataError as details:

    print >> sys.stderr, str(details) 
    if options.debug:
        try:
            print_exception(*details.exc_info, file=sys.stderr)
        except (AttributeError, TypeError):
            print_exc(file=sys.stderr)
    sys.exit(PARSE_ERRNO)    
    
except Exception as details:
    for detail in format_exception_only(sys.exc_type, sys.exc_value):
        sys.stderr.write(str(details))
    if options.debug:
        print_exc(file=sys.stderr)
    sys.exit(UNKNOWN_ERRNO)
