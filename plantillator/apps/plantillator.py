#!/usr/bin/env python
# -*- vim: expandtab tabstop=4 shiftwidth=4 smarttab autoindent encoding=utf-8

from __future__ import with_statement
import os
import os.path
import re
import sys
from contextlib import contextmanager

from data.pathfinder import PathFinder, FileSource
from apps.dataloader import DataLoader
from apps.tmplloader import TmplLoader
from engine.cmdtree import VARPATTERN


class Plantillator(object):

    OPTIONS = {
        'path': [],
        'outpath': "",
        'collapse': False,
        'definitions': [],
        'inputfiles': [],
    }

    CONF_SUFFIX = ".cfg"

    def __init__(self):
        self.__dict__.update(self.OPTIONS)
        self.dataloader = DataLoader()
        self.tmplloader = TmplLoader()

    def render(self):
        data, tmpl = self._classify()
        self._loaddata(data)
        self._addobjects()
        self._loadtmpl(tmpl)
        if self.collapse:
            # borro el fichero de salida combinado
            if os.path.isfile(self.outpath):
                os.unlink(self.outpath)
        glob, data = self.dataloader.glob, self.dataloader.data
        for tmpldata in self.tmplloader.templates(glob, data):
            for block in self._renderfile(*tmpldata):
                yield block

    def _classify(self):
        """divide los ficheros en datos y patrones"""
        data, tmpl, finder = [], [], PathFinder(self.path)
        for fname in self.inputfiles:
            parts = os.path.splitext(fname)
            if len(parts) < 2:
                raise ValueError, "Fichero sin extension: %s" % fname
            ext = parts[1][1:] # viene con un "."
            if self.tmplloader.known(ext):
                tmpl.append(FileSource(finder(fname), finder))
            elif self.dataloader.known(ext):
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
            outname = os.path.splitext(outname)[0] + self.CONF_SUFFIX
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

    def _renderfile(self, sourceid, cmdtree, glob, data):
        """Ejecuta un patron.

        Ejecuta el patron y va grabando los resultados al fichero de salida
        correspondiente.

        Si se encuentra con un bloque que no sabe interpretar (cualquier cosa
        que no sea texto), lo lanza.
        """
        outcontext = self._outcontext(sourceid)
        items = cmdtree.run(glob, data)
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

