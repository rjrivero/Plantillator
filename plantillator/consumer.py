#!/usr/bin/env python
# -*- vim: expandtab tabstop=4 shiftwidth=4 smarttab autoindent


import sys
import re
import os.path
import code

import tools
from .iotools import ShelfLoader, ContextMaker, Interactor


# Nombre de variable valido. Excluyo los que comienzan por "_",
# estan reservados para atributos internos del plantillator.
varpattern = re.compile(r'^[a-zA-Z][a-zA-Z0-9_]*$')


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
        'test': False,
        'lazy': False,
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
        try:
            self.loader.set_datapath(self.path, self.lazy)
            self.loader.set_tmplpath(self.path)
            self.maker = ContextMaker(self.outpath, self.ext, self.collapse, self.overwrite)
            self.actor = Interactor()
            self._add_objects()
            self.loader.add_symbols({
                "OUTDIR": self.maker.output_dir,
                "INSERT": self.INSERT,
                "APPEND": self.APPEND,
                "SAVEAS": self.SAVEAS,
                "SELECT": self.SELECT,
                "BREAK":  self.BREAK,
                "tools":  tools,
                })
        except:
            self.loader.close()
            raise

    def _add_objects(self):
        """Carga objetos predefinidos e indicados en la linea de comandos."""
        varpattern = re.compile(r"^[a-zA-Z][a-zA-Z0-9]*$")
        symbols = dict()
        for definition in self.definitions or tuple():
            var, expr = tuple(x.strip() for x in definition.split("=", 1))
            if not varpattern.match(var):
                raise SyntaxError, "\"%s\" NO es un nombre valido" % var
            symbols[var] = eval(expr, self.loader.data)
        self.loader.add_symbols(symbols)

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

        def __init__(self, tmplid, template, outname, data):
            self.tmplid = tmplid
            self.template = template
            self.outname = outname
            self.data = dict(data)

        def key(self):
            return (self.tmplid, self.outname)

        def render(self, consumer):
            self.consumer = consumer
            self.template.render(consumer, self.data)

        def dup(self, tmplid, template, outname):
            return Consumer.Pending(tmplid, template, outname, self.data)

        def embed(self, template):
            template.embed(self.consumer, self.data)

    def render(self):
        try:
            tmplid, template = self.loader.get_template(self.tmplname)
            pending = Consumer.Pending(tmplid, template, None, self.loader.data)
            self._queue, self._done = [pending], set()
            while self._queue:
                self._pending = self._queue.pop(0)
                key = self._pending.key()
                if key not in self._done:
                    self._done.add(key)
                    self._pending.render(self._consume(*key))
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

    def SELECT(self, sort=True, **kw):
        """Pide al usuario que seleccione elementos.

        Los argumentos opcionales son pares "nombre"="lista". La funcion
        presenta cada lista al usuario, y guarda el objeto elegido en el
        espacio global con el nombre asignado.

        Si el nombre ya existe en el espacio global, se salta la eleccion.
        """
        for key, items in kw.iteritems():
            if key in self._pending.data:
                continue
            if not self.test:
                item = self.actor.select(items, sort)
            else:
                item = self.actor.exhaust(items)
            self._pending.data[key] = item

    def SAVEAS(self, outname):
        """Filtro que guarda el contenido del bloque en un fichero.

        Devuelve una sola linea, el nombre del fichero.
        """
        def saveme(strings):
            outpath = self.maker.resolve_relative(outname)
            with self.maker.get_context(outpath)() as outfile:
                outfile.write("".join(strings))
            return (outpath,)
        return saveme

    def BREAK(self, label=None):
        """Lanza un interprete interactivo, para depuracion"""
        banner = "\n".join((
            "***",
            "Breakpoint en plantilla %s: '%s'" % (
                os.path.basename(self._pending.tmplid),
                str(label) if label is not None else "<Sin etiqueta>",
            ),
            "  Para salir de la sesion, pulse Ctrl+D",
            "  Para cancelar la ejecucion de la plantilla, excriba 'exit()'",
            "***",
        ))
        code.interact(banner=banner, local=self._pending.data)
