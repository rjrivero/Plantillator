#!/usr/bin/env python
# -*- vim: expandtab tabstop=4 shiftwidth=4 smarttab autoindent

from __future__ import with_statement
import os
import os.path
import sys
import logging
import glob # pa windows, que no expande nombres
import re

from collections import OrderedDict
from operator import itemgetter
from optparse import OptionParser
from itertools import chain
from traceback import print_exc, print_exception, format_exception_only

from cuac.libs.pathfinder import FileSource
from cuac.libs.iotools import ContextMaker


VERSION           = "0.5"
OPTIONS_ERRNO     = -1
FILE_ERRNO        = -2
DATA_ERRNO        = -3
PARSE_ERRNO       = -5
TRANSLATION_ERRNO = -6
UNKNOWN_ERRNO     = -7
usage = """uso: %prog [opciones] fichero [fichero...]
Lee un fichero .csv normal (como los exportados por un Call Manager),
y le da formato para hacerlo compatible con cuac:

  - Agrega la fila de cabecera con los tipos de datos.
  - Modifica los nombres de columna para eliminar espacios.
  - Agrega la columna de nombre de tabla.
  - Calcula relaciones entre columnas y tablas (formato Call Manager)

Reconoce la etiqueta "Entity:<objeto>" que a veces pone el Call Manager
cuando se exportan objetos complejos (por ejemplo: la lista de gateways con
diferentes tipos -H.323, MGCP-, PRIs, etc).
"""

loglevel = logging.INFO
path = ['.']

parser = OptionParser(usage=usage, version="%%prog %s"%VERSION)
parser.add_option("-o", "--output", dest="outpath", metavar="OUTPATH",
        help="""Ruta donde guardar los ficheros de resultado.
Por cada fichero de entrada, crea en el directorio especificado un fichero con el mismo nombre, terminado en .auto.csv""")
parser.add_option("-O", "--onefile",
        action="store_true", dest="collapse", default=False,
        help="""Vuelca el resultado de todos los ficheros en una salida unica.
Si se usa esta opcion, debe utilizarse tambien -o para especificar el
nombre del fichero de salida.""")
parser.add_option("-d", "--debug",
        action="store_true", dest="debug", default=False,
        help="Vuelca los mensajes de debug en stderr")
parser.add_option("-e", "--excel",
        action="store_true", dest="excel", default=False,
        help="Cambia el separador de campos por ';' en lugar de ','")
parser.add_option("-x", "--ext", dest="ext", metavar=".EXT", default=".csv",
        help="Extension del fichero resultado (por defecto, .auto)")

(options, args) = parser.parse_args()
if len(args) < 1:
    parser.print_help(sys.stderr)
    sys.exit(OPTIONS_ERRNO)

if options.debug:
    loglevel = logging.DEBUG
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
        if hasattr(details, 'exc_info') and details.exc_info:
            print_exception(*details.exc_info, file=sys.stderr)
        else:
            print_exc(file=sys.stderr)
    sys.exit(PARSE_ERRNO)    


def adapt(inname, outfile):
    lines = iter(FileSource(inname).read().split("\n"))
    blkno = 0
    try:
        while True:
            line = lines.next()
            if not line.strip():
                continue
            addblock(inname, blkno, lines, line, outfile)
            blkno += 1
    except StopIteration:
        pass


def addblock(inname, blkno, lines, line, outfile, prefix=[0], key=[0], match=re.compile("[^a-zA-Z0-9]")):
    # "line" es la primera linea no vacia de un bloque, debe
    # contener la cabecera, Lo que hago es:
    # - Averiguar el separador de columnas
    # - Averiguar cuantos campos tiene la cabecera
    # - Ponerle a la linea un nombre.
    # - Insertar un campo vacio al inicio del resto de lineas.
    #
    # Para tablas encadenadas (como GATEWAY, GATEWAY_PRI, GATEWAY_SLOT)
    # Intenta enlazar automaticamente unas con otras relacionando el
    # primer campo de la tabla encadenada con el primer campo de la tabla
    # "padre".
    #
    # Si hay columnas cuyos nombres coincidan excepto en la parte final
    # (terminando con un digito), convierte esas columnas en una lista.
    #
    # 1.- Obtener el nombre a partir del fichero, o de la etiqueta "Entity:"
    global options
    if line.startswith("Entity:"):
        name = line.split(":")[1]
        line = lines.next()
    else:
        name = os.path.splitext(os.path.basename(inname))[0]
        name = "%s%d" % (name, blkno) if blkno > 0 else name
    name = name.lower()
    # 2.- Acondicionar la lista de campos
    sep = (line.count(","), line.count(";"))
    sep = "," if sep[0] > sep[1] else ";"
    clean = list(match.sub("_", x).lower() for x in line.split(sep))
    # Aprovecho para cambiar el separador por ";", de forma que
    # excel pueda entender estos CSV a la primera.
    newsep = sep if not options.excel else ";"
    # 3.- Enlazar la tabla con una anterior, si procede.
    if (blkno == 0) or not (clean[0].startswith(prefix[0])):
        prefix[0], key[0] = name, clean[0]
    else:
        name = "%s.%s" % (prefix[0], name)
        clean[0] = "%s.%s" % (prefix[0], key[0])
    # 4.- Convertir en lista los campos que sean una secuencia
    mapping = OrderedDict()
    for index, column in enumerate(clean):
        parts = tuple(x for x in column.split("_") if x)
        if parts[-1].isdigit():
            parts = parts[:-1]
        column = "_".join(parts)
        mapping.setdefault(column, []).append(index)
    # 5.- Saco la cabecera (tipos de datos y nombres de columnas)
    header = ("String" if len(val) == 1 else "List.String" 
              for val in mapping.itervalues())
    outfile.write("%s%s" % (newsep, ";".join(header)))
    outfile.write("\n%s%s%s\n" % (name, newsep, newsep.join(mapping.keys())))
    # 6.- Voy sacando las filas
    trailing = newsep * len(mapping)
    while True:
        line = lines.next()
        if not line.strip():
            break
        fields = line.split(sep)
        data = (("\"%s\"" % ",".join(
                  field for field in (fields[x] for x in indexes) if field
                )
                for indexes in mapping.itervalues()))
        outfile.write("%s%s%s\n" % (newsep, newsep.join(data), trailing))
    outfile.write("\n")
    

try:

    context = ContextMaker(options.outpath, options.ext, options.collapse)    
    for inname in inputfiles:
        with context.get_template_context(inname)() as outfile:
            adapt(inname, outfile)

except Exception as detail:

    for detail in format_exception_only(sys.exc_type, sys.exc_value):
        sys.stderr.write(str(detail))
    if options.debug:
        print_exc(file=sys.stderr)
    sys.exit(UNKNOWN_ERRNO)
