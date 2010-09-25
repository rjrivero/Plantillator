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
from traceback import print_exc, format_exception_only, extract_tb, format_list

#from plantillator.engine import ParseError, CommandError
#from plantillator import ParseError as NewParseError
#from plantillator import DataError, TemplateError, Plantillator, Consumer

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
parser.add_option("-k", "--keep_comments",
        action="store_true", dest="keep_comments", default=False,
        help="Conserva los comentarios de la plantilla")
parser.add_option("-l", "--lazy",
        action="store_true", dest="lazy", default=False,
        help="Demora parte del proceso de los datos CSV a tiempo de ejecucion")
#parser.add_option("-n", "--new-engine",
#        action="store_true", dest="new_engine", default=False,
#        help="Activa el nuevo motor de plantillas")

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

# manejadores para los eventos definidos
def select_handler(opcode, command, glob, data):
    """Gestiona el comando 'select'"""
    var = command.var
    art = command.art
    itemlist = list((str(item), item) for item in command.pick)
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


def break_handler(opcode, command, glob, data):
    if options.debug and not options.test:
        code.interact("Breakpoint %s" % (command.breakpoint or "<>"),
                      local={'glob': glob, 'data':data})


# manejador para el caso de loop

WASTED, PICKS = dict(), list()

def loop_select(opcode, command, glob, data):
    """Gestiona el comando 'select' en un bucle"""
    global WASTED, PICKS
    var = command.var
    # busco un elemento que no este totalmente usado.
    hit, hitcount = False, 0
    for current in sorted(command.pick, cmp=lambda a, b: cmp(str(a), str(b))):
        if str(current) not in WASTED:
            hitcount += 1
            hit = current
            # recorro toda la lista porque en cada iteracion puede estar
            # ordenada de una forma distinta, si no la recorro no me entero
            # de si todos los elementos estan wasted o no.
    if hit:
        print "AUTO-SELECCIONADO ELEMENTO %s" % str(hit)
        data[var] = hit
        PICKS.append((hitcount, str(hit)))
    # si he agotado la lista, marco como usado el elemento
    # que se haya seleccionado en el ultimo select anterior a este.


def handle(item):
    """Gestiona los comandos lanzados por el proceso de rendering"""
    global options
    handlers = {
            "SELECT": select_handler if not options.test else loop_select,
            "BREAK": break_handler,
    }
    handler = handlers.get(item.opcode, None)
    if handler:
        handler(*item)
    else:
        print "NO SE RECONOCE COMANDO %s" % item.opcode


def exit_with_errors(details):
    """Sale volcando todos los mensajes de error."""
    print >> sys.stderr, str(details) 
    if options.debug:
        print_exc(file=sys.stderr)
    sys.exit(PARSE_ERRNO)    


# y cargo a PLANTILLATOR!
# plantillator = Plantillator() if not options.new_engine else Consumer()
plantillator = Consumer()
plantillator.path = path
plantillator.outpath = options.outpath
plantillator.collapse = options.collapse
plantillator.definitions = options.definitions or []
plantillator.inputfiles = inputfiles
plantillator.ext = options.ext
plantillator.overwrite = True
plantillator.keep_comments = options.keep_comments

try:

    plantillator.prepare()
    if options.shell:
        local = dict(plantillator.loader.glob)
        code.interact("Shell de pruebas", local=local)
        exit(0)
    if not options.test:
        for item in plantillator.render():
            handle(item)
    else:
        while True:
            PICKS = list()
            for item in plantillator.render():
                handle(item)
            plantillator.overwrite = False
            if not PICKS:
                break
            hitcount, hitstr = PICKS.pop()
            WASTED[hitstr] = True
            while hitcount <= 1 and PICKS:
                hitcount, hitstr = PICKS.pop()
                WASTED[hitstr] = True
            if hitcount <= 1:
                break

#except CommandError as detail:

    #for msg in format_exception_only(sys.exc_type, sys.exc_value):
        #sys.stderr.write(str(msg))
    #if options.debug:
        #print_exc(file=sys.stderr)
        #detail.data['error'] = detail
        #code.interact("Consola de depuracion", local={'data':detail.data})
    #sys.exit(TRANSLATION_ERRNO)

#except NewParseError as details:
except ParseError as details:

    exit_with_errors(details)

except TemplateError as details:

    exit_with_errors(details)

#except (ParseError, TemplateError, DataError) as detail:
except DataError as detail:

    for msg in format_exception_only(sys.exc_type, sys.exc_value):
        sys.stderr.write(str(msg))
    if options.debug:
        print_exc(file=sys.stderr)
    sys.exit(PARSE_ERRNO)

except Exception as detail:

    for detail in format_exception_only(sys.exc_type, sys.exc_value):
        sys.stderr.write(str(detail))
    if options.debug:
        print_exc(file=sys.stderr)
    sys.exit(UNKNOWN_ERRNO)

