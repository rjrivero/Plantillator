#!/usr/bin/env python
# -*- vim: expandtab tabstop=4 shiftwidth=4 smarttab autoindent


import shelve
import os
import os.path

from contextlib import contextmanager

from ..data import PathFinder, FileSource
from ..data import Resolver, SYMBOL_SELF, DataSet, password, secret
from ..csvread import CSVShelf


class ShelfLoader(CSVShelf):

    FILES    = "tmpl_files"
    VERSION  = "tmpl_version"
    CURRENT  = 1

    def __init__(self, shelfname):
        """Inicializa el cargador"""
        shelf = shelve.open(shelfname, protocol=2)
        super(ShelfLoader, self).__init__(shelf)
        try:
            if self.shelf[ShelfLoader.VERSION] == ShelfLoader.CURRENT:
                self.files = self.shelf[ShelfLoader.FILES]
        except:
            # Si el pickle falla o no es completo, recargamos los datos
            # (cualquiera que sea el error)
            self.files = dict()
            self.shelf[ShelfLoader.VERSION] = ShelfLoader.CURRENT
            self.shelf[ShelfLoader.FILES] = self.files
            self.dirty = True
        solv = Resolver(SYMBOL_SELF)
        self.glob = {
            "CISCOPASSWORD": password,
            "CISCOSECRET": secret,
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

    def set_tmplpath(self, tmplpath):
        """Prepara la carga de plantillas del path"""
        self.path = PathFinder(tmplpath)

    def add_symbols(self, symbols):
        """Agrega simbolos al espacio global de los templates"""
        self.data.update(symbols)

    def get_template(self, tmplname):
        source   = self.path(tmplname)
        template = self.files.get(source.id, None)
        mtime    = os.stat(source.id).st_mtime
        if template is None or template.timestamp < mtime:
            template = Templite(source.read(), timestamp=mtime)
            self.dirty = True
            self.files[source.id] = template
        return template

    def close(self):
        if self.dirty:
            self.shelf.sync()
        self.shelf.close()


class ContextMaker(object):
    
    """Genera contextos que dirigen la salida al fichero adecuado"""

    def __init__(self, outpath=".", ext=".cfg", collapse=False):
        """Prepara el generador.
        
        - outpath: directorio de salida (si collapse == False), o nombre del
            fichero de salida (si collapse == True).
        
        - ext: extension que se le pone a los ficheros de salida.
        
        - output_dir: directorio de salida, sea collapse True o False.
        """
        self.outpath = outpath
        self.collapse = collapse
        self.ext = ext
        # Calculo el directorio de salida en funcion de los valores
        # de outpath y collapse.
        if collapse:
            if not outpath:
                self.output_dir = os.getcwd()
            else:
                self.output_dir = os.path.dirname(self.outpath)
        else:
            self.output_dir = outpath

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
            outpath = os.path.join(self.outpath, outname)
        return outpath

    def get_context(self, outname):
        """Obtiene un contexto que sirve para escribir al fichero adecuado.

        'outname' es una ruta completa, no relativa a "output_dir".
        """
        if os.path.isfile(outname):
            os.unlink(outname)
        def outcontext():
            return open(outname, "a+")
        return outcontext

    def get_relative_context(self, outname):
        """Obtiene un contexto que sirve para escribir al fichero adecuado.

        'outname' es una ruta relativa a "output_dir".
        """
        return self.get_context(os.path.join(self.output_dir, outname))

    def get_template_context(self, tmplname):
        """Obtiene un contexto que sirve para escribir al fichero adecuado.
        
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
        pass

    def exhaust(self, itemlist):
        """Selecciona un elemento de la lista, y lo marca como usado"""
        pass
