#!/usr/bin/env python
# -*- vim: expandtab tabstop=4 shiftwidth=4 smarttab autoindent

import os.path
import itertools
import re

from scopetype import ScopeType
from scopedict import ScopeDict
from scopelist import ScopeList
from mytokenizer import PathFinder
from datatokenizer import DataTokenizer
from myoperator import normalize


DATA_COMMENT = "!"


class DataList(ScopeList):

    """Lista de ScopeDicts con campos fijos

    Crea una lista de ScopeDicts, cada uno de ellos con los datos de una
    linea del fichero CSV.

    El primer elemento de la lista es la "clave primaria". Solo puede
    haber un ScopeDict por cada clave primaria. Si se intenta incluir un dict
    cuya clave primaria coincide con la de otro que ya existe, se
    actualiza el antiguo con los elementos del nuevo.
    """

    def _find(self, key, val):
        """Busca un solo elemento, sin fallbacks"""
        for item in self:
            # la clave primaria nunca se hereda, asi que puedo buscarla
            # en el diccionario y no como atributo.
            if item._data[key] == val:
                return item
        raise KeyError, val

    def __init__(self, dicttype, fallback, fieldset=None):
        """Crea una lista vacia

        @dicttype: Objeto ScopeType con el que se crearan los ScopeDicts.
        @fallback: el diccionario al que los ScopeDicts creados deben
            hacer fallback.
        @fieldset: las claves a usar para cada columna al crear el ScopeDict.
            si fieldset == None, el datalist queda "reducido": no se pueden
            insertar nuevos valores.
        """
        ScopeList.__init__(self, dicttype, fallback, fieldset)

    def additems(self, tokenizer, items):
        """Incluye en la lista un ScopeDict con los elementos de 'items'

        tokenizer: el tokenizer, para poder generar errores.
        items: una lista de items, ya normalizada.
        """
        data = zip(self.fieldset, items)
        data = (p for p in data if all(x is not None for x in p))
        try:
            item = self._find(self.dicttype.pkey, items[0])
            item.update(dict(data))
        except KeyError:
            self.append(ScopeDict(self.dicttype, data, self.fallback))


class DataPath(object):

    """Ruta para proceso de listas anidadas

    Permite procesar listas anidadas. Una lista anidada se caracteriza porque
    su nombre es una secuencia de variables separadas por '.' (por ejemplo,
    'lista_principal.lista_anidada')

    En la linea CSV que define cada elemento de la lista, la primera
    columna debe ser un campo que sirva para indexar la lista "madre". Por
    ejemplo:

    principal; id; nombre
             ; 1 ; elemento_1
             ; 2 ; elemento_2

    principal.anidada_1; principal.id; nombre
                       ; 1           ; sub_elemento_1_1
                       ; 1           ; sub_elemento_1_2
                       ; 2           ; sub_elemento_2_1

    principal.anidada_2; principal.nombre; nombre
                       ; elemento_1  ; sub_elemento_1_1
                       ; elemento_1  ; sub_elemento_1_2
                       ; elemento_2  ; sub_elemento_2_1

    Las listas pueden anidarse tantos niveles como se desee.
    """

    def __init__(self, tokenizer, root, head, fields):
        """Inicializa la ruta

        @tokenizer: el tokenizer, para lanzar errores.
        @root: Objeto ScopeDict raiz de la ruta
        @fields: nombre y conjunto de campos (la linea completa del CSV)
        """
        self.root = root
        path = list(p.strip() for p in head.split("."))
        if len(fields) < len(path):
            tokenizer.error("No hay bastantes columnas de indice")
        self.make_path(path, fields)
        self.make_type(fields)

    def make_path(self, path, fields):
        """Obtiene el conjunto de atributos que se usan como path"""
        def last_part(field):
            return field.split(".").pop().strip()
        self.attr = path.pop()
        self.path = tuple((item, last_part(fields.pop(0))) for item in path)

    def make_type(self, fields):
        """Construye el ScopeType adecuado y actualiza el tipo padre

        Cuando se crea una sublista, se insertan nuevos campos en
        la lista "madre". Esos campos deben figurar como nuevos campos
        en el tipo que usa la lista madre, para que por error no se
        haga fallback y acabemos usando una lista de un nivel superior.
        """
        typedict = self.root._TypeDict
        # creo un tipo para los elementos de esta lista "hija"
        parentlist = list(listname for listname, attrib in self.path)
        sublist = parentlist + [self.attr]
        self.dicttype = typedict.setdefault(".".join(sublist), ScopeType())
        self.fieldset = self.dicttype.fieldset(fields)
        # actualizo el tipo de la lista "madre"
        if self.path:
            typedict[".".join(parentlist)].addtype(self.attr, self.dicttype)

    def additems(self, tokenizer, items):
        """Inserta un elemento en la lista

        Avanza por la ruta hasta llegar a la lista indicada, y
        cuando llega, inserta el elemento.
        """
        if len(items) <= len(self.path):
            tokenizer.error("No hay bastantes valores de indice")
        base = self.root
        try:
            for listname, attrib in self.path:
                base = base[listname]._find(attrib, items.pop(0))
        except KeyError:
            tokenizer.error("No se encuentra el indice")
        try:
            target = base[self.attr]
        except KeyError:
            target = DataList(self.dicttype, base, self.fieldset)
            base[self.attr] = target
        target.additems(tokenizer, items)


class DataParser(ScopeDict):
    """Carga un fichero de datos

    Un fichero de datos es basicamente una forma mas resumida de definir
    una estructura de "diccionarios" python, mediante CSV

    todos los objetos de un fichero de datos son diccionarios
    con una ruta, y un conjunto de valores.

    Hay dos rutas especiales:
        VARIABLES: la ruta raiz
        DEPENDENCIAS: una "pseudoruta", hace que se inserte en linea el
            contenido de otro fichero.
    """

    _Instrucciones = {
        'variables': ('nombre', 'valor'),
        'dependencias': ('fichero',),
    }

    def _variables(self, tokenizer, variables):
        for item in variables:
            self[item.nombre] = item.valor

    def _dependencias(self, tokenizer, dependencias):
        for item in dependencias:
            self.read(tokenizer.source.resolve(item.fichero))
        
    def __init__(self, data=None):
        ScopeDict.__init__(self, ScopeType(), data)
        self._includes = set()
        self._TypeDict = dict()

    def read(self, source):
        """Carga un fichero de datos"""
        tokenizer, curpath = DataTokenizer(source, DATA_COMMENT), None
        if tokenizer.source.id in self._includes:
            return # ya ha sido cargado
        self._includes.add(tokenizer.source.id)
        for line in tokenizer.tokens():
            line = (normalize(field) for field in line)
            head = line.next()
            if head:
                try:
                    line = self._Instrucciones[head.lower()]
                    head = head.lower()
                except KeyError:
                    pass
                datapath = DataPath(tokenizer, self, head, list(line))
            else:
                datapath.additems(tokenizer, list(line))
        # proceso las instrucciones que haya encontrado
        for instruccion in DataParser._Instrucciones:
            if instruccion in self:
                data = self[instruccion]
                del(self[instruccion])
                getattr(self, "_%s" % instruccion)(tokenizer, data)


if __name__ == "__main__":
    import sys
    import pprint
    p = DataParser()
    for f in sys.argv[1:]:
        p.read(PathFinder([]).find(f))
    pprint.pprint(p)

