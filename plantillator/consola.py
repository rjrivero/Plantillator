#!/usr/bin/env python
# -*- vim: expandtab tabstop=4 shiftwidth=4 smarttab autoindent encoding=utf-8

from __future__ import with_statement
import os
import os.path
import sys
import logging
import re
import glob # pa windows, que no expande nombres
import code
from operator import itemgetter

from optparse import OptionParser
from traceback import print_exc, format_exception_only
from mycommands import CommandEngine
from tmplparser import CommandError
from plantillator import Plantillator

VERSION           = "0.2"
OPTIONS_ERRNO     = -1
FILE_ERRNO        = -2
DATA_ERRNO        = -3
TRANSLATION_ERRNO = -4
UNKNOWN_ERRNO     = -5
usage = """uso: %prog [opciones] fichero [fichero...]
Aplica los patrones (.txt) a los ficheros de datos (.csv)"""

loglevel = logging.INFO
path = ['.']

parser = OptionParser(usage=usage, version="%%prog %s"%VERSION)
parser.add_option("-p", "--path", dest="path", metavar="PATH",
        help="""Ruta donde buscar los ficheros de datos y patrones.
        La ruta se especifica al estilo del sistema operativo, por ej.:
        C:\\ruta1;C:\\ruta2 (en windows)
        /ruta1:/ruta2 (en linux)""")
parser.add_option("-o", "--output", dest="outpath", metavar="OUTPATH",
        help="""Ruta donde guardar los ficheros de resultado.
        por cada patron, crea en el directorio especificado un fichero con el mismo nombre, terminado en .cfg""")
parser.add_option("-O", "--onefile",
        action="store_true", dest="collapse", default=False,
        help="""Vuelca el resultado de todos los patrones en un fichero unico.
        Si se usa esta opcion, debe utilizarse tambien -o para especificar el
        nombre del fichero de salida.""")
parser.add_option("-D", "--define",
        action="append", dest="definitions", metavar="VAR=EXPR",
        help="""Define una variable para la ejecucion del patron""")
parser.add_option("-d", "--debug",
        action="store_true", dest="debug", default=False,
        help="Vuelca los mensajes de debug en stderr")

(options, args) = parser.parse_args()
if len(args) < 2:
    parser.print_help(sys.stderr)
    sys.exit(OPTIONS_ERRNO)

if options.debug:
    loglevel = logging.DEBUG
if options.path:
    path.extend(options.path.split(os.pathsep))
if options.collapse and not options.outpath:
    parser.print_help(sys.stderr)
    sys.exit(OPTIONS_ERRNO)

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

# manejadores para los eventos definidos
def select_handler(command, var, art, expr, data):
    """Gestiona el comando 'select'"""
    itemlist = []
    for index, item in enumerate(expr):
        # de los diccionarios, solo sacamos la clave primaria
        rep = item
        try:
            key = item._type.pkey
            rep = item[key]
            details = set(("nombre", "descripcion", "detalles"))
            details = details.difference(key)
            for detail in details:
                det = item.get(detail, None)
                if det:
                    rep = "%s, %s" % (rep, det)
        except AttributeError:
            pass
        itemlist.append((rep, item))
    if len(itemlist) == 1:
        item = itemlist[0]
        print "** SE SELECCIONA %s = %s" % (var, item[0])
        data[var] = item[1]
    elif len(itemlist) > 1:
        print "****"
        print "Selecciona %s %s de la siguiente lista:\n" % (art, var)
        itemlist.sort()
        for index, item in enumerate(itemlist):
            print "  %s.- %s" % (index+1, item[0])
        print ""
        chosen = 0
        while chosen < 1 or chosen > len(itemlist):
            userdata = input("Seleccione [1-%d]: " % len(itemlist))
            if type(userdata) == int:
                chosen = userdata
        data[var] = itemlist[chosen-1][1]


def handle(item):
    """Gestiona los comandos lanzados por el proceso de rendering"""
    handlers = {
            "select": select_handler,
    }
    handler = handlers.get(item[0], None)
    if handler:
        handler(*item)

# y cargo a PLANTILLATOR!
engine = CommandEngine()
plantillator = Plantillator()
plantillator.path = path
plantillator.outpath = options.outpath
plantillator.collapse = options.collapse
plantillator.definitions = options.definitions or []
plantillator.inputfiles = inputfiles
try:
    for item in plantillator.render(engine):
        handle(item)

except CommandError, detail:
    for msg in format_exception_only(sys.exc_type, sys.exc_value):
        sys.stderr.write(str(msg))
    if options.debug:
        print_exc(file=sys.stderr)
        detail.data['block'] = detail.block
        detail.data['data'] = detail.data
        code.interact("Consola de depuracion", local=detail.data)
    sys.exit(TRANSLATION_ERRNO)
except Exception, detail:
    for detail in format_exception_only(sys.exc_type, sys.exc_value):
        sys.stderr.write(str(detail))
    if options.debug:
        print_exc(file=sys.stderr)
    sys.exit(UNKNOWN_ERRNO)

