#!/usr/bin/env python


import operator, os, os.path, sys, logging, glob
import cherrypy

from traceback import print_exc, format_exception_only
from optparse import OptionParser
from contextlib import contextmanager
from itertools import chain
from genshi.template import TemplateLoader

try:
    import cPickle as pickle
except ImportError:
    import pickle

try:
    from plantillator import ShelfLoader, DataError
except ImportError:
    import os.path
    import sys
    sys.path.append(".")
    from plantillator import ShelfLoader, DataError


class Renderer(object):

    def __init__(self, tmpl, filters=None):
        self.tmpl = tmpl
        self.filters = filters if filters is not None else tuple()

    def __call__(self, **kw):
        partial = self.tmpl.generate(**kw)
        for filter in self.filters:
            partial = partial | filter
        return partial.render("html", doctype="html")

    def __getitem__(self, item):
        return Renderer(self.tmpl, tuple(chain(self.filters, (item,))))


class Cache(dict):

    def __init__(self):
        super(Cache, self).__init__()
        self.loader = TemplateLoader(
            os.path.join(os.path.dirname(__file__), 'wizard'),
            auto_reload=True
        )

    def __getattr__(self, attr):
        if attr.startswith("_"):
            raise AttributeError(attr)
        render = self.get(attr)
        if not render:
            render = Renderer(self.loader.load("%s.html" % attr))
            self[attr] = render
        return render


class Root(object):

    def __init__(self, root):
        self.root = root
        self.meta = root["_meta"]
        self.tmpl = Cache()
        self.keys = dict()

    @cherrypy.expose
    def index(self):
        return self.tmpl.index(title="Test")

    def traverse(self, path):
        meta, data = self.meta, self.root
        try:
            if not path:
                data = (data,)
            else:
                for item in path:
                    meta = meta.fields[item].meta
                    data = data.get(item)
        except (IndexError, KeyError, AttributeError):
            meta, data = self.meta, (self.data,)
        return (meta, data)

    @cherrypy.expose
    def table(self, *path, **params):
        parent, crumbs = None, list()
        # Si me pasan un ID, es el del penultimo elemento en el path
        if (len(path) > 1) and ("id" in params):
            parent = self.keys.get(params["id"], None)
            if not parent:
                meta, values = self.traverse(path[:-1])
                values = values(PK=int(params["id"]))
                if len(values) == 1:
                    parent = +values
                    self.keys[parent.PK] = parent
            if parent:
                values = parent.get(path[-1])
                meta = values._meta
        else:
            meta, values = self.traverse(path)
        crumbs.append(("root", "", "table/"))
        for item in xrange(1, len(path)):
            subpath = "table/" + "/".join(path[:item])
            crumbs.append((path[item], "", subpath))
        fields, subfields = set(), set()
        for key, val in meta.fields.iteritems():
            if hasattr(val, "meta") and key != "up":
                subfields.add(key)
            elif key not in ("up", "PK"):
                fields.add(key)
        if path:
            for item in values:
                self.keys[item.PK] = item
        path = "/".join(chain(("table",), path))
        params = {
            "fields": fields,
            "subfields": subfields,
            "values": values,
            "path": path,
            "crumbs": crumbs,
        }
        return self.tmpl.table(**params)


def navigate(data):

    #if hasattr(cherrypy.engine, "subscribe"):
    #    cherrypy.engine.subscribe("stop", save_data)
    #else:
    #    cherrypy.engine.on_stop_engine_list.append(save_data)

    cherrypy.config.update({
        'server.socket_host': '0.0.0.0',
        'tools.encode.on': True, 'tools.encode.encoding': 'utf-8',
        'tools.decode.on': True,
        'tools.trailing_slash.on': True,
        'tools.staticdir.root': os.path.abspath(os.path.dirname(__file__)),
    })

    cherrypy.quickstart(Root(data), '/', {
        '/media': {
            'tools.staticdir.on': True,
            'tools.staticdir.dir': 'static'
        }
    })


VERSION           = "0.1"
OPTIONS_ERRNO     = -1
FILE_ERRNO        = -2
DATA_ERRNO        = -3
TRANSLATION_ERRNO = -4
UNKNOWN_ERRNO     = -5
usage = """uso: %prog [opciones] fichero [fichero...]
Navega por un fichero de datos (pickle)"""

loglevel = logging.INFO
path = ['.']

parser = OptionParser(usage=usage, version="%%prog %s"%VERSION)
parser.add_option("-p", "--path", dest="path", metavar="PATH",
        help="""Ruta donde buscar los ficheros de datos.
La ruta se especifica al estilo del sistema operativo, por ej.:
C:\\ruta1;C:\\ruta2 (en windows)
/ruta1:/ruta2 (en linux)""")
parser.add_option("-d", "--debug",
        action="store_true", dest="debug", default=False,
        help="Vuelca los mensajes de debug en stderr")
parser.add_option("-x", "--profile",
        action="store_true", dest="profile", default=False,
        help="Ejecutar en modo profile (solo carga datos)")
parser.add_option("-l", "--lazy",
        action="store_true", dest="lazy", default=False,
        help="Demora parte del proceso de los datos CSV a tiempo de ejecucion")

(options, args) = parser.parse_args()

if options.debug:
    loglevel = logging.DEBUG
if options.path:
    path.extend(options.path.split(os.pathsep))

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
    loader = ShelfLoader(shelfname)
    loader.set_datapath(path, options.lazy)
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
        data = dataloader.data
        # me aseguro de instanciar todas las sublistas, que
        # pueden no estarlo.
        if not options.profile:
            force_process(data['_meta'])
        navigate(data)

except DataError as details:

    print >> sys.stderr, str(details) 
    if options.debug:
        try:
            print_exception(*details.exc_info, file=sys.stderr)
        except AttributeError:
            print_exc(file=sys.stderr)
    sys.exit(PARSE_ERRNO)    
    
except Exception as details:
    for detail in format_exception_only(sys.exc_type, sys.exc_value):
        sys.stderr.write(str(details))
    if options.debug:
        print_exc(file=sys.stderr)
    sys.exit(UNKNOWN_ERRNO)

