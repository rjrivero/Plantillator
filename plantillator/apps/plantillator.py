#!/usr/bin/env python
# -*- vim: expandtab tabstop=4 shiftwidth=4 smarttab autoindent encoding=utf-8

from __future__ import with_statement
import os
import os.path
import re
import sys
from contextlib import contextmanager

from ..data.pathfinder import PathFinder, FileSource
from ..data.dataobject import Fallback
from ..csvread.source import DataSource
from ..engine.loader import Loader as TmplLoader
from ..engine.cmdtree import VARPATTERN
from .dataloader import DataLoader


TMPL_EXT = set(('.txt',))
DATA_EXT = set(('.csv',))
CONF_EXT = ".cfg"


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
        'path': [],
        'outpath': "",
        'collapse': False,
        'definitions': [],
        'inputfiles': [],
    }

    def __init__(self):
        self.__dict__.update(self.OPTIONS)
        self.dataloader = DataLoader(DataSource())
        self.tmplloader = TmplLoader()

    def prepare(self, overwrite=True):
        data, tmpl = self._classify()
        self._loaddata(data)
        self._addobjects()
        self._loadtmpl(tmpl)

    def render(self, overwrite=True):
        if self.collapse:
            # borro el fichero de salida combinado
            if os.path.isfile(self.outpath) and overwrite:
                os.unlink(self.outpath)
        glob = self.dataloader.glob
        #data = FallbackDict(self.dataloader.data)
        data = Fallback(self.dataloader.data, depth=1)
        for tree in self.tmplloader:
            for block in self._renderfile(tree, glob, data):
                yield block

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
                data.append(FileSource(finder(fname), finder))
            else:
                raise ValueError, "Extension desconocida: %s" % ext
        return data, tmpl

    def _loaddata(self, data_sources):
        """carga los ficheros de datos"""
        for source in data_sources:
            self.dataloader.load(source)

    def _loadtmpl(self, tmpl_sources):
       """carga los patrones de texto"""
       for source in tmpl_sources:
            self.tmplloader.load(source)

    def _addobjects(self):
        """Carga objetos predefinidos e indicados en la linea de comandos."""
        varpattern = re.compile(VARPATTERN['var'])
        for definition in self.definitions or tuple():
            var, expr = tuple(x.strip() for x in definition.split("=", 1))
            if not varpattern.match(var):
                raise SyntaxError, "\"%s\" NO es un nombre valido" % var
            self.dataloader.data[var] = self.dataloader.evaluate(expr)

    def _outcontext(self, sourceid):
        """Genera un context que abre y cierra el fichero de salida adecuado"""
        if self.collapse:
            outcontext = lambda: open(self.outpath, "a+")
        elif self.outpath:
            outname = os.path.basename(sourceid)
            outname = os.path.splitext(outname)[0] + CONF_EXT
            outname = os.path.join(self.outpath, outname)
            if os.path.isfile(outname):
                os.unlink(outname)
            outcontext = lambda: open(outname, "w+")
        else:
            @contextmanager
            def stderr_wrapper():
                yield sys.stdout
            outcontext = stderr_wrapper
        return outcontext

    def _renderfile(self, cmdtree, glob, data):
        """Ejecuta un patron.

        Ejecuta el patron y va grabando los resultados al fichero de salida
        correspondiente.

        Si se encuentra con un bloque que no sabe interpretar (cualquier cosa
        que no sea texto), lo lanza.
        """
        outcontext = self._outcontext(cmdtree.source.id)
        items = self.tmplloader.run(cmdtree, glob, data)
        try:
            while True:
                with outcontext() as f:
                    item = items.next()
                    while type(item) == str:
                        f.write(item)
                        item = items.next()
                # si el item no es una cadena de texto, cerramos el fichero
                # temporalmente y lanzamos el item.
                yield item
        except StopIteration:
            pass
