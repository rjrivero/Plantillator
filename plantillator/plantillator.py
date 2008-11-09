#!/usr/bin/env python
# -*- vim: expandtab tabstop=4 shiftwidth=4 smarttab autoindent encoding=utf-8

from __future__ import with_statement
import os
import os.path
import re
import sys
from contextlib import contextmanager
from myoperator import MyOperator, MySearcher
from dataparser import DataParser
from mytokenizer import PathFinder
from mycommands import VARPATTERN


class Plantillator(object):

    OPTIONS = {
        'path': [],
        'outpath': "",
        'collapse': False,
        'definitions': [],
        'inputfiles': [],
    }

    PREDEFINIDOS = {
        'LISTA':             DataParser._aslist,
        'RANGO':             DataParser._asrange,
        'cualquiera':        MyOperator(),
        '_cualquiera_de':    MySearcher(),
        'ninguno':           (MyOperator() == None),
        'ninguna':           (MyOperator() == None),
    }

    DATA_SUFFIX = set((".csv",))
    TMPL_SUFFIX = set((".txt",))
    CONF_SUFFIX = ".cfg"

    def __init__(self):
        self.__dict__.update(Plantillator.OPTIONS)

    def render(self, engine):
        self._loadfiles(engine)
        self._addobjects()
        if self.collapse:
            # borro el fichero de salida combinado
            if os.path.isfile(self.outpath):
                os.unlink(self.outpath)
        for template, data in engine.templates():
            for block in self._renderfile(template, data):
                yield block

    def _loadfiles(self, engine):
        """carga los ficheros de datos y patrones"""
        self.dataparser = DataParser()
        finder = PathFinder(self.path)
        for fname in self.inputfiles:
            parts = os.path.splitext(fname)
            if len(parts) < 2:
                raise ValueError, "Fichero sin extension: %s" % fname
            ext = parts[1].lower()
            if ext in Plantillator.TMPL_SUFFIX:
                engine.read(self.dataparser, finder.find(fname))
            elif ext in Plantillator.DATA_SUFFIX:
                self.dataparser.read(finder.find(fname))
            else:
                raise ValueError, "Extension desconocida: %s" % fname

    def _addobjects(self):
        """Carga objetos predefinidos e indicados en la linea de comandos."""
        self.dataparser.update(Plantillator.PREDEFINIDOS)
        varpattern = re.compile(VARPATTERN['varflat'])
        for definition in self.definitions or tuple():
            var, expr = tuple(x.strip() for x in definition.split("=", 1))
            if not varpattern.match(var):
                raise SyntaxError, "\"%s\" NO es un nombre valido" % var
            self.dataparser[var] = eval(expr, self.dataparser)

    def _outcontext(self, template):
        """Genera un context que abre y cierra el fichero de salida adecuado"""
        if self.collapse:
            outcontext = lambda: open(self.outpath, "a+")
        elif self.outpath:
            outname = os.path.basename(template.source.id)
            outname = os.path.splitext(outname)[0] + Plantillator.CONF_SUFFIX
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

    def _renderfile(self, template, data):
        """Ejecuta un patron.

        Ejecuta el patron y va grabando los resultados al fichero de salida
        correspondiente.

        Si se encuentra con un bloque que no sabe interpretar (cualquier cosa
        que no sea texto), lo lanza.
        """
        outcontext = self._outcontext(template)
        items = template.render(data)
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

