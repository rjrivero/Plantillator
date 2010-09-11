#!/usr/bin/env python
# -*- vim: expandtab tabstop=4 shiftwidth=4 smarttab autoindent


import shelve
import os
import os.path
import re
import sys

from contextlib import contextmanager

from ..tools import PathFinder, FileSource, password, secret
from ..data import Resolver, SYMBOL_SELF, DataSet
from ..data import Templite
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
        self.cache = dict()

    def set_tmplpath(self, tmplpath):
        """Prepara la carga de plantillas del path"""
        self.path = PathFinder(tmplpath)

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
            template = Templite(FileSource(source).read(), timestamp=mtime)
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
                self.output_dir = os.getcwd()
            else:
                self.output_dir = os.path.dirname(self.outpath)
        else:
            self.output_dir = outpath or os.getcwd()

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
        """Obtiene un contexto de escritura al fichero 'outname'.

        'outname' es una ruta completa (o relativa a getcwd()), en ningun
        caso relativa a "output_dir".
        """
        if self.overwrite and os.path.isfile(outname):
            os.unlink(outname)
        def outcontext():
            return open(outname, "a+")
        return outcontext

    def resolve_relative(self, outname):
        """Resuelve un nombre de fichero relativo al dir. de salida"""
        # Por si el nombre de salida viene con directorio... puede venir
        # con separadores en formato UNIX, y luego pegarse con los de
        # WINDOWS, o viceversa.
        pathelems = tuple(x for x in os.path.split(outname) if x)
        return os.path.join(self.output_dir, *pathelems)

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


class Consumer(object):

    """Consumidor de plantillas"""

    OPTIONS = {
        'path': [],
        'outpath': "",
        'outdir': "",
        'overwrite': True,
        'collapse': False,
        'definitions': [],
        'inputfiles': [],
        'ext': ".cfg",
    }

    def __init__(self):
        self.__dict__.update(self.OPTIONS)

    def prepare(self):
        if len(self.inputfiles) > 1:
            datashelf = self.inputfiles[0]
            template  = self.inputfiles[1]
        else:
            datashelf = "data.shelf"
            template  = self.inputfiles[0]
        self.tmplname = template
        self.loader = ShelfLoader(datashelf)
        self.loader.set_datapath(self.path)
        self.loader.set_tmplpath(self.path)
        self.maker = ContextMaker(self.outpath, self.ext, self.collapse, self.overwrite)
        self.actor = Interactor()
        self._add_objects()
        self.loader.add_symbols({
            "INSERT": self.INSERT,
            "APPEND": self.APPEND,
            "SAVEAS": self.SAVEAS,
            "DOTPNG": self.DOTPNG,
            })

    def _add_objects(self):
        """Carga objetos predefinidos e indicados en la linea de comandos."""
        varpattern = re.compile(r"^[a-zA-Z][a-zA-Z0-9]*$")
        for definition in self.definitions or tuple():
            var, expr = tuple(x.strip() for x in definition.split("=", 1))
            if not varpattern.match(var):
                raise SyntaxError, "\"%s\" NO es un nombre valido" % var
            self.dataloader.data[var] = eval(expr, self.dataloader.data)

    def _consume(self, tmplid, outname=None):
        if outname is None:
            # No hay hints, guardamos el fichero como digan las opciones
            context = self.maker.get_template_context(tmplid)
        else:
            # Hay un hint, va a ser un nombre relativo al outdir.
            context = self.maker.get_relative_context(outname)
        with context() as outfile:
            try:
                while True:
                    outfile.write((yield))
            except GeneratorExit:
                pass

    class Pending(object):

        def __init__(self, tmplid, template, outname, data, loc=None):
            self.tmplid = tmplid
            self.template = template
            self.outname = outname
            self.data = dict(data)
            self.loc = dict(loc) if loc is not None else dict()

        def key(self):
            return (self.tmplid, self.outname)

        def render(self, consumer):
            self.consumer = consumer
            self.template.render(consumer, self.data, self.loc)

        def dup(self, tmplid, template, outname):
            return Consumer.Pending(tmplid, template, outname, self.data, self.loc)

        def embed(self, template):
            template.embed(self.consumer, self.data, self.loc)

    def render(self):
        try:
            tmplid, template = self.loader.get_template(self.tmplname)
            self._queue = [Consumer.Pending(tmplid, template, None, self.loader.data)]
            self._done  = set()
            while self._queue:
                self._pending = self._queue.pop(0)
                key = self._pending.key()
                if key not in self._done:
                    self._done.add(key)
                    self._pending.render(self._consume(*key))
            return tuple() # para hacerlo compatible con consola.py
        finally:
            self.loader.close()

    def INSERT(self, fname):
        """Inserta una plantilla en linea"""
        # Damos preferencia en el path al directorio de la plantilla actual
        tmplid, template = self.loader.get_template(fname, self._pending.tmplid)
        self._pending.embed(template)
        
    def APPEND(self, fname, outname=None):
        """Ejecuta una plantilla a posteriori"""
        tmplid, template = self.loader.get_template(fname, self._pending.tmplid)
        self._queue.append(self._pending.dup(tmplid, template, outname))

    def DOTPNG(self, outname, program="dot"):
        """Filtro que genera un grafico "dot" en formato PNG"""
        if not outname.lower().endswith(".png"):
            outname += ".png"
        def saveme(strings):
            graph = pydot.graph_from_dot_data("".join(strings))
            fname = self.maker.resolve_relative(outname)
            graph.write(fname, format="png", prog=program)
            return tuple()
        return saveme

    def SAVEAS(self, outname):
        """Filtro que guarda el contenido del bloque en un fichero"""
        def saveme(strings):
            with self.maker.get_relative_context(outname)() as outfile:
                outfile.write("".join(strings))
            return tuple()
        return saveme
