#!/usr/bin/env python
# -*- vim: expandtab tabstop=4 shiftwidth=4 smarttab autoindent encoding=utf-8

from __future__ import with_statement
import os
import os.path
import re
import sys
from contextlib import contextmanager
from itertools import chain

try:
    import pydot
except ImportError:
    print >> sys.stderr, "Warning: PyDOT NOT SUPPORTED!"

from ..data import PathFinder, FileSource, Fallback
from ..csvread import DataSource
from ..engine import Loader as TmplLoader, VARPATTERN
from .dataloader import DataLoader


TMPL_EXT = set(('.txt',))
DATA_EXT = set(('.csv',))
TOOLS_FILE = "tools.py"


#class FallbackDict(dict):
#
#    """Diccionario que hace Fallback a un DataObject
#
#    Lo he definido para usarlo como "locals" en las llamadas a exec
#    y eval, por si utilizar un tipo basado en diccionario mejoraba algo
#    el rendimiento comparado con un tipo basado en DataType. Pero la verdad
#    es que el rendimiento se queda igual.
#    """
#
#    def __init__(self, data):
#        dict.__init__(self)
#        self._up = data
#
#    def __getitem__(self, index):
#        try:
#            return dict.__getitem__(self, index)
#        except KeyError:
#            return self.setdefault(index, self._up[index])
#
#    @property
#    def _type(self):
#        return self._up._type
#
#    def __setattr__(self, index, value):
#        self[index] = value
#
#    def __getattr__(self, attr):
#        try:
#            return self[attr]
#        except KeyError as details:
#            raise AttributeError(details)


class Plantillator(object):

    OPTIONS = {
        'keep_comments': False,
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
        self.dataloader = DataLoader(DataSource())
        self.tmplloader = TmplLoader(self.keep_comments)
        data, tmpl = self._classify()
        self._loaddata(data)
        self._addobjects()
        self._loadtmpl(tmpl)
        # Calcula el directorio de salida en funcion de
        # outpath y collapse.
        if self.collapse:
            self.outdir = os.path.dirname(self.outpath)
        elif self.outpath:
            self.outdir = self.outpath
        else:
            self.outdir = os.getcwd()

    def render(self):
        if self.collapse:
            # borro el fichero de salida combinado
            if os.path.isfile(self.outpath) and self.overwrite:
                os.unlink(self.outpath)
        for runtree in self.tmplloader:
            outcontext = self._outcontext(runtree.cmdtree.source.id, runtree.outpath)
            for block in self._renderfile(runtree, outcontext):
                yield block

    def _outcontext(self, sourceid, outpath):
        """Genera un context que abre y cierra el fichero de salida adecuado"""
        if self.collapse:
            outcontext = lambda: open(self.outpath, "a+")
        elif self.outpath:
            # Si no hay ninguna sugerencia, el fichero de salida se
            # llama igual que el de entrada, pero con la extension cambiada.
            if not outpath:
                outpath = os.path.basename(sourceid)
                outpath = os.path.splitext(outpath)[0] + self.ext
            outpath = os.path.join(self.outpath, outpath)
            if os.path.isfile(outpath):
                os.unlink(outpath)
            outcontext = lambda: open(outpath, "w+")
        else:
            @contextmanager
            def stderr_wrapper():
                yield sys.stdout
            outcontext = stderr_wrapper
        return outcontext

    def _classify(self):
        """divide los ficheros en datos y patrones"""
        data, tmpl, finder = [], [], PathFinder(self.path)
        for fname in self.inputfiles:
            parts = os.path.splitext(fname)
            if len(parts) < 2:
                raise ValueError, "Fichero sin extension: %s" % fname
            ext = parts[1].lower()
            if ext in TMPL_EXT:
                tmpl.append(FileSource(finder(fname), finder))
            elif ext in DATA_EXT:
                data.extend(FileSource(x, finder) for x in finder.every(fname))
            else:
                raise ValueError, "Extension desconocida: %s" % ext
        return data, tmpl

    def _loaddata(self, data_sources):
        """carga los ficheros de datos"""
        for source in data_sources:
            self.dataloader.load(source)

    def _loadtmpl(self, tmpl_sources):
        """carga los patrones de texto"""
        glob, loc = self.dataloader.glob, dict()
        for dirname in self.path:
            init = os.path.sep.join((dirname, TOOLS_FILE))
            if os.path.isfile(init):
                execfile(init, glob, loc)
        glob.update(loc)
        for source in tmpl_sources:
            data = Fallback(self.dataloader.data, depth=1)
            self.tmplloader.load(source, self.dataloader.glob, data)

    def _addobjects(self):
        """Carga objetos predefinidos e indicados en la linea de comandos."""
        varpattern = re.compile(VARPATTERN['var'])
        for definition in self.definitions or tuple():
            var, expr = tuple(x.strip() for x in definition.split("=", 1))
            if not varpattern.match(var):
                raise SyntaxError, "\"%s\" NO es un nombre valido" % var
            self.dataloader.data[var] = self.dataloader.evaluate(expr)

    def _renderfile(self, runtree, outcontext):
        """Ejecuta un patron.

        Ejecuta el patron y va grabando los resultados al fichero de salida
        correspondiente.

        Si se encuentra con un bloque que no sabe interpretar (cualquier cosa
        que no sea texto), lo lanza.
        """
        items = self.tmplloader.run(runtree)
        try:
            while True:
                with outcontext() as f:
                    item = items.next()
                    while type(item) == str:
                        f.write(item)
                        item = items.next()
                # si el item no es una cadena de texto, cerramos el fichero
                # temporalmente y lanzamos el item.
                if item.opcode == "DOT":
                    self._dot(item)
                else:
                    yield item
        except StopIteration:
            pass

    def _dot(self, yieldblock):
        """Genera un gráfico dot"""
        graph = pydot.graph_from_dot_data(yieldblock.command.graph)
        # El path que me dan generalmente viene en formato UNIX ("/"),
        # Si lo mezclo con WINDOWS ("\\") puede dar problemas...
        # Mejor primero lo separo en trozos, y luego lo uno todo con
        # os.path.join.
        pathelems = os.path.split(yieldblock.command.outfile)
        filename = pathelems[-1]
        filepath = os.path.join(self.outdir, *pathelems[:-1])
        for f in yieldblock.command.formats:
            outpath = os.path.join(filepath, filename + "." + f)
            graph.write(outpath, format=f, prog=yieldblock.command.program)
            # Si hay un mapa de cliente, lo cargo en el bloque para que este
            # accesible
            if f == "cmapx":
                with open(outpath, "r") as cmapx:
                    yieldblock.command.cmapx = cmapx.read()

