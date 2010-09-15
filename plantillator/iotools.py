#!/usr/bin/env python
# -*- vim: expandtab tabstop=4 shiftwidth=4 smarttab autoindent


import shelve
import os
import os.path
import sys

from contextlib import contextmanager

from .pathfinder import PathFinder, FileSource
from .ciscopw import password, secret
from .resolver import Resolver
from .meta import SYMBOL_SELF, DataSet
from .csvreader import CSVShelf
from .templite import Templite


class PathElem(str):

    """Cadena de texto en formato path."""

    def join(self, other):
        # Por si el nombre de salida viene con directorio... puede venir
        # con separadores en formato UNIX, y luego pegarse con los de
        # WINDOWS, o viceversa.
        elems = tuple(x for x in os.path.split(other) if x)
        return PathElem(os.path.join(self, *elems))


class ShelfLoader(CSVShelf):

    FILES    = "tmpl_files"
    VERSION  = "tmpl_version"
    CURRENT  = 1

    def __init__(self, shelfname):
        """Inicializa el cargador"""
        try:
            shelf = shelve.open(shelfname, protocol=2)
            super(ShelfLoader, self).__init__(shelf)
            self.files, self.dirty = None, False
            try:
                if self.shelf[ShelfLoader.VERSION] == ShelfLoader.CURRENT:
                    self.files = self.shelf[ShelfLoader.FILES]
            except KeyError:
                pass
        except:
            # si el constructor falla, me aseguro de no dejar el shelf abierto.
            shelf.close()
            raise
        if self.files is None:
            # Si el pickle falla o no es completo, recargamos los datos
            # (cualquiera que sea el error)
            self.files = dict()
            self.dirty = True
        solv = Resolver(SYMBOL_SELF)
        self.glob = {
            "CISCOPASSWORD": password,
            "CISCOSECRET": secret,
            "ANY": DataSet.ANY,
            "NONE": DataSet.NONE,
            "cualquiera": DataSet.ANY,
            "ninguno": DataSet.NONE,
            "ninguna": DataSet.NONE,
            "X": solv,
            "x": solv,
            "Y": solv,
            "y": solv,
            "Z": solv,
            "z": solv,
        }
        self.cache = dict()

    def set_tmplpath(self, tmplpath):
        """Prepara la carga de plantillas del path"""
        self.path = PathFinder(tmplpath)

    def set_datapath(self, datapath):
        """ejecuta la carga de datos"""
        super(ShelfLoader, self).set_datapath(datapath)
        self.data.update(self.glob)

    def add_symbols(self, symbols):
        """Agrega simbolos al espacio global de los templates"""
        self.data.update(symbols)

    def get_template(self, tmplname, hint=None):
        """Devuelve el Id del template (abspath), y su contenido"""
        try:
            # Cacheamos para no tener que andar resolviendo paths en cada
            # iteracion de un bucle, si dentro del bucle hay un "INSERT"
            return self.cache[(tmplname, hint)]
        except KeyError:
            pass
        if hint:
            # buscamos primero en la misma ruta que el fichero que nos
            # dan como pista
            self.path.insert(0, os.path.dirname(hint))
        source = self.path(tmplname)
        template = self.files.get(source, None)
        mtime = os.stat(source).st_mtime
        if template is None or template.timestamp < mtime:
            self.dirty = True
            template = Templite(source, FileSource(source).read(), timestamp=mtime)
            self.files[source] = template
        return self.cache.setdefault((tmplname, hint), (source, template))

    def close(self):
        if self.dirty:
            self.shelf[ShelfLoader.FILES] = self.files
            self.shelf[ShelfLoader.VERSION] = ShelfLoader.CURRENT
            self.shelf.sync()
        self.shelf.close()


class ContextMaker(object):

    """Genera contextos que dirigen la salida al fichero adecuado"""

    def __init__(self, outpath=".", ext=".cfg", collapse=False, overwrite=True):
        """Prepara el generador.
        
        - outpath: directorio de salida (si collapse == False), o nombre del
            fichero de salida (si collapse == True).
        
        - ext: extension que se le pone a los ficheros de salida.
        
        - output_dir: directorio de salida, sea collapse True o False.
        """
        self.outpath = outpath
        self.overwrite = overwrite
        self.collapse = collapse
        self.ext = ext
        # Calculo el directorio de salida en funcion de los valores
        # de outpath y collapse.
        if collapse:
            if not outpath:
                self.output_dir = PathElem(os.getcwd())
            else:
                self.output_dir = PathElem(os.path.dirname(self.outpath))
        else:
            self.output_dir = PathElem(outpath or os.getcwd())

    def _outname(self, tmplname):
        """Calcula el nombre del fichero de salida, relativo a output_dir"""
        if not self.outpath:
            # outpath debe ser algo, en caso contrario la salida sera stdout.
            return None
        if self.collapse:
            outpath = self.outpath
        else:
            outname = os.path.basename(tmplname)
            outname = os.path.splitext(outname)[0] + self.ext
            outpath = self.output_dir.join(outname)
        return outpath

    def get_context(self, outname):
        """Obtiene un contexto de escritura al fichero 'outname'.

        'outname' es una ruta completa (o relativa a getcwd()), en ningun
        caso relativa a "output_dir".
        """
        if self.overwrite:
            if os.path.isfile(outname):
                os.unlink(outname)
        def outcontext():
            return open(outname, "a+")
        return outcontext

    def resolve_relative(self, outname):
        """Resuelve un nombre de fichero relativo al dir. de salida"""
        # Por si el nombre de salida viene con directorio... puede venir
        # con separadores en formato UNIX, y luego pegarse con los de
        # WINDOWS, o viceversa.
        return self.output_dir.join(outname)

    def get_relative_context(self, outname):
        """Obtiene un contexto de escritura al fichero dado.

        outname se considera una ruta relativa al output_dir por defecto.
        """
        return self.get_context(self.resolve_relative(outname))

    def get_template_context(self, tmplname):
        """Calcula la ruta al fichero y devuelve el contexto de escritura.
        
        Utiliza los valores de self.outpath, self.ext y self.collapse para
        decidir el nombre del fichero en que se guardar el resultado, en
        funcion del nombre del template.
        """
        outname = self._outname(tmplname)
        if outname is not None:
            return self.get_context(outname)
        @contextmanager
        def outcontext():
            yield sys.stdout
        return outcontext


class Interactor(object):
    
    """Presenta al usuario una serie de opciones a elegir"""
    
    def select(self, itemlist):
        """Permite al usuario seleccionar un elemento de la lista dada"""
        itemlist = list(sorted((str(item), item) for item in itemlist))
        if len(itemlist) == 1:
            item = itemlist[0]
            print "** SE SELECCIONA %s = %s" % (var, item[0])
        elif len(itemlist) > 1:
            print "****"
            print "Selecciona un elemento de la lista:"
            for index, item in enumerate(itemlist):
                print "  %2s.- %s" % (index+1, item[0])
            print "****"
            chosen = 0
            while chosen < 1 or chosen > len(itemlist):
                userdata = input("Seleccione [1-%d]: " % len(itemlist))
                if type(userdata) == int:
                    chosen = userdata
            item = itemlist[chosen-1]
        return item[1]

    def exhaust(self, itemlist):
        """Selecciona un elemento de la lista, y lo marca como usado"""
        pass
