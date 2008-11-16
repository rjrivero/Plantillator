#!/usr/bin/env python
# -*- vim: expandtab tabstop=4 shiftwidth=4 smarttab autoindent

import itertools


class ScopeList(list):

    """Lista de ScopeDicts con un ScopeType comun"""

    def __init__(self, dicttype, fallback, fieldset=None):
        """Crea una lista vacia

        @dicttype: Objeto ScopeType con el que se crearan los ScopeDicts.
        @fallback: el diccionario al que los ScopeDicts creados deben
            hacer fallback.
        @fieldset: las claves a usar para cada columna al crear el ScopeDict.
            si fieldset == None, el datalist queda "reducido": no se pueden
            insertar nuevos valores.
        """
        list.__init__(self)
        self.dicttype = dicttype
        self.fieldset = fieldset or tuple()
        self.fallback = fallback

    def __call__(self, *arg, **kw):
        """Busca los elementos de la lista que cumplan los criterios dados.

        Si solo hay un elemento en la lista que cumpla los criterios,
        devuelve ese elemento unico.

        Si hay mas de uno, devuelve un DataList "reducido" (no pueden
        insertarse campos).

        Si no hay ninguno, lanza un KeyError.
        """
        if not arg and not kw:
            return self if len(self != 1) else self[0]
        filt = ScopeList(self.dicttype, self.fallback)
        crit = self.dicttype.search_crit(arg, kw)
        filt.extend(item for item in self if item._matches(crit))
        if not len(filt):
            raise KeyError, repr(crit)
        return filt if len(filt) != 1 else filt[0]

    def __getattr__(self, attrib):
        """Selecciona un atributo en la lista

        Devuelve un set con los distintos valores del atributo seleccionado
        en cada uno de los elementos de la lista.

        Si el atributo seleccionado es una sublista, en lugar de un set
        se devuelve un ScopeList con todos los elementos encadenados.
        """
        attribs = (item.get(attrib, None) for item in self)
        attribs = (item for item in attribs if item is not None)
        subtype = self.dicttype.subtypes.get(attrib, None)
        if subtype:
            sublist = ScopeList(subtype, None)
            sublist.extend(itertools.chain(*list(attribs)))
            if len(sublist) == 1:
                sublist = sublist[0]
        else:
            sublist = frozenset(attribs)
        return sublist 

    @property
    def up(self):
        sublist = ScopeList(None, None)
        for item in self:
            up = item.up
            if item.up not in sublist:
                sublist.append(up)
        return sublist[0] if len(sublist) == 1 else sublist

