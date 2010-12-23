#!/usr/bin/env python
# -*- vim: expandtab tabstop=4 shiftwidth=4 smarttab autoindent


import os
import os.path
import sys
try:
    import cPickle as pickle
except ImportError:
    import pickle

from contextlib import contextmanager

from .pathfinder import PathFinder, FileSource
from .ciscopw import password, secret
from .meta import DataSet
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
        self.shelfname, shelf = shelfname, dict()
        try:
            with open(shelfname, "rb") as shelve:
                shelf = pickle.load(shelve)
        except (IOError, EOFError, pickle.UnpicklingError):
            pass
        super(ShelfLoader, self).__init__(shelf)
        self.files, self.dirty = None, False
        try:
            if self.shelf[ShelfLoader.VERSION] == ShelfLoader.CURRENT:
                self.files = self.shelf[ShelfLoader.FILES]
        except KeyError:
            pass
        if self.files is None:
            # Si el pickle falla o no es completo, recargamos los datos
            # (cualquiera que sea el error)
            self.files = dict()
            self.dirty = True
        self.glob = {
            "CISCOPASSWORD": password,
            "CISCOSECRET": secret,
            "ANY": DataSet.ANY,
            "NONE": DataSet.NONE,
        }
        self.cache = dict()

    def set_tmplpath(self, tmplpath):
        """Prepara la carga de plantillas del path"""
        self.path = PathFinder(tmplpath)

    def set_datapath(self, datapath, lazy=True):
        """ejecuta la carga de datos"""
        super(ShelfLoader, self).set_datapath(datapath, lazy)
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
            with open(self.shelfname, "wb") as shelve:
                pickle.dump(self.shelf, shelve, protocol=2)


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

    class Node(dict):
        def __init__(self):
            super(Interactor.Node, self).__init__()
            self.exhausted = False

    def __init__(self):
        self.tree = Interactor.Node()
        self.path = []

    def exhaust(self, itemlist):
        """Selecciona un elemento de la lista, y lo marca como usado"""
        itemlist = dict((str(item), item) for item in itemlist)
        # Voy bajando por el arbol hasta llegar al punto
        # de insercion actual
        prev = self.tree
        for index in self.path:
            prev = prev.setdefault(index, Interactor.Node())
        if len(prev) == 0:
            # Es la primera vez que vemos este nodo.
            prev.update(dict((x, Interactor.Node()) for x in itemlist.keys()))
        else:
            # Me aseguro de que las opciones son las mismas que
            # se hayan dado en otras visitas a este nodo del arbol.
            assert(prev.keys() == itemlist.keys())
        # Busco un elemento de la lista que no este usado.
        for name, subdict in prev.iteritems():
            if not subdict.exhausted:
                self.path.append(name)
                return itemlist[name]
        # Aqui no se debe llegar nunca!
        assert(False)

    def select(self, itemlist, sort=True):
        """Permite al usuario seleccionar un elemento de la lista dada"""
        itemlist = list((str(item), item) for item in itemlist)
        if len(itemlist) == 1:
            item = itemlist[0]
            print "** SE SELECCIONA %s" % item[0]
            return item[1]
        if sort:
            itemlist = sorted(itemlist)
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

    @property
    def exhausted(self):
        # Voy a revisar el path y marcar como exhausted los
        # nodos para los que ya no haya opciones
        prev, path = self.tree, [self.tree]
        for index in self.path:
            prev = prev[index]
            path.append(prev)
        # Marco el ultimo nodo del trayecto como agotado.
        path[-1].exhausted = True
        # Y voy revisando los nodos anteriores, a ver si
        # con esta eleccion he agotado las opciones
        for item in reversed(path[:-1]):
            if all(x.exhausted for x in item.values()):
                item.exhausted = True
        self.path = []
        return self.tree.exhausted
