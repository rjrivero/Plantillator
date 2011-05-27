#!/usr/bin/env python
# -*- vim: expandtab tabstop=4 shiftwidth=4 smarttab autoindent

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
from itertools import chain
from traceback import print_exc, print_exception, format_exception_only

from plantillator import DataError, ParseError, TemplateError, Consumer


VERSION           = "0.5"
OPTIONS_ERRNO     = -1
FILE_ERRNO        = -2
DATA_ERRNO        = -3
PARSE_ERRNO       = -5
TRANSLATION_ERRNO = -6
UNKNOWN_ERRNO     = -7
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
parser.add_option("-s", "--shell",
        action="store_true", dest="shell", default=False,
        help="Carga los datos y entra en un interprete de comandos")
parser.add_option("-t", "--test-mode",
        action="store_true", dest="test", default=False,
        help="Itera sobre todos los posibles valores de los 'SELECT'")
parser.add_option("-x", "--ext", dest="ext", metavar=".EXT", default=".cfg",
        help="Extension del fichero resultado (por defecto, .cfg)")
parser.add_option("-l", "--lazy",
        action="store_true", dest="lazy", default=False,
        help="Demora parte del proceso de los datos CSV a tiempo de ejecucion")
parser.add_option("-w", "--warnings",
        action="store_true", dest="warnings", default=False,
        help="Continuar con la carga de datos incorrectos, generando warnings")

(options, args) = parser.parse_args()
if len(args) < 1 and not options.shell:
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


def exit_with_errors(details):
    """Sale volcando todos los mensajes de error."""
    print >> sys.stderr, str(details) 
    if options.debug:
        try:
            print_exception(*details.exc_info, file=sys.stderr)
        except AttributeError:
            print_exc(file=sys.stderr)
    sys.exit(PARSE_ERRNO)    


# y cargo a PLANTILLATOR!
plantillator = Consumer()
plantillator.path = path
plantillator.outpath = options.outpath
plantillator.collapse = options.collapse
plantillator.definitions = options.definitions or []
plantillator.inputfiles = inputfiles
plantillator.ext = options.ext
plantillator.overwrite = True
plantillator.lazy = options.lazy
plantillator.test = options.test

try:

    plantillator.prepare()
    plantillator.dump_warnings()
    if options.shell:
        local = dict(plantillator.loader.data)
        code.interact("Shell de pruebas", local=local)
        exit(0)
    if not options.test:
        plantillator.render()
    else:
        while True:
            plantillator.render()
            if plantillator.actor.exhausted:
                break

except ParseError as details:

    exit_with_errors(details)

except TemplateError as details:

    exit_with_errors(details)

except DataError as details:

    exit_with_errors(details)

except Exception as detail:

    for detail in format_exception_only(sys.exc_type, sys.exc_value):
        sys.stderr.write(str(detail))
    if options.debug:
        print_exc(file=sys.stderr)
    sys.exit(UNKNOWN_ERRNO)
