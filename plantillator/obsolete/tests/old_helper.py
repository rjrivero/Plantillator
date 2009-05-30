#!/usr/bin/env python
# -*- vim: expandtab tabstop=4 shiftwidth=4 smarttab autoindent

from __future__ import with_statement
import unittest
import dircache
import operator
import os
import sys


class TestDescriptor(object):
    
    """Descriptor que emula una funcion con un solo argumento

    Se usa para poder pasarle a los tests mas de un argumento. Por defecto
    una funcion de un TestCase solo recibe self, asi que para poder pasarle
    mas cosas, la envolvemos en este descriptor.

    Cuando se accede al descriptor, devuelve una funcion con un solo
    argumento. Esta funcion realmente invoca a la funcion original, y le pasa
    como argumentos todos los parametros que haya recibido el constructor.
    """

    def __init__(self, func, args):
        self.func = func
        self.args = args

    def __get__(self, obj, type=None):
        return lambda: self.func(obj, *self.args)


class Tester(object):

    def __init__(self):
        self.PATH_TO_TESTS = os.path.abspath(os.path.dirname(sys.argv[0])) + "/testdata"
        os.chdir(self.PATH_TO_TESTS)
        self.checkpath()
        # Si regenerate == TRUE, los test se ejecutan en modo "regeneracion".
        # Es decir, se asume que el programa ya pasa la bateria de tests,
        # y se hace un pase que genera ficheros de tests nuevos para aquellos
        # tests que no los tengan.
        self.REGENERATE = False
        if os.path.isfile("REGENERATE.TXT"):
            self.REGENERATE = True

    def checkpath(self):
        """Modifica sys.path para poder importar modulos de Plantillator"""
        try:
            import plantillator
        except ImportError:
            # gracias a __init__ estoy en testdata... los paquetes de plantillator
            # estan dos directorios mas arriba.
            sys.path.append("../..")

    def find_tests(self):
        """Lista todos los subdirectorios del directorio de tests
    
        Devuelve un diccionario donde cada clave es el nombre de un directorio,
        y cada elemento es la lista de todos los ficheros en ese directorio.

        Cachea la lista en TEST_DIRS, para no tener que andar reescaneando
        directorios en cada test.
        """
        self.TEST_DIRS = dict()
        for subdir in dircache.listdir(self.PATH_TO_TESTS):
            fullpath = os.path.join(self.PATH_TO_TESTS, subdir)
            if not os.path.isdir(fullpath):
                continue
            listing = dircache.listdir(fullpath)[:]
            dircache.annotate(fullpath, listing)
            filelist = set(f for f in listing if not f.endswith('/'))
            self.TEST_DIRS[subdir] = filelist
        self.find_tests = lambda: self.TEST_DIRS
        return self.TEST_DIRS

    def build(self, classname, classbase, testfunc, filtfunc):
        """Class Factory para tests

        Crea una nueva clase derivada de unittest.TestCase y de la clase
        definida por "classbase". Por cada subdirectorio de PATH_TO_TESTS,
        comprueba si debe insertar un test a la clase. Si es asi, crea en
        la clase una funcion que realiza el test definido en el
        subdirectorio.

        Para determinar si debe incluir o no en la clase cada test, utiliza
        la funcion indicada por "filtfunc". Por cada subdirectorio, llama a la
        funcion "filfunc" pasandole como parametros el nombre del
        subdirectorio y su la lista de ficheros.

        Si el directorio contiene un test valido para este TestCase, la
        funcion definida por "filter" debe devolver una tupla de argumentos,
        que sera el conjunto de argumentos que hay que pasarle a la funcion
        de test.

        Si REGENERATE == True, en lugar de la funcion "testfunc", se invoca
        a la funcion classobj.regenerate
        """
        newclass = type(classname, (classbase, unittest.TestCase), {})
        testfunc = getattr(newclass, testfunc)
        if self.REGENERATE and hasattr(newclass, "regenerate"):
            testfunc = newclass.regenerate
        for testdir, files in self.find_tests().iteritems():
            args = filtfunc(testdir, files)
            if args:
                descriptor = TestDescriptor(testfunc, args)
                testname = "test_%s_%s" % (classname, testdir.replace('.', '_'))
                setattr(newclass, testname, descriptor)
        return newclass

    def exist(self, *arg):
        """Generador de filtros

        Genera un filtro que acepta los directorios donde existen todos
        los ficheros nombrados. El filtro devuelve una tupla con el nombre
        del directorio y de cada uno de los ficheros, en orden.
        """
        def filter(dirname, files):
            if all(file in files for file in arg):
                fullpaths = (os.path.join(dirname, f) for f in arg)
                return (dirname,) + tuple(fullpaths)
        return filter

tester = Tester()

