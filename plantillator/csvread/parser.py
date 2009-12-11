#!/usr/bin/env python
# -*- vim: expandtab tabstop=4 shiftwidth=4 smarttab autoindent


import re
from gettext import gettext as _

from ..data.base import DataError, asIter


_NOT_ENOUGH_INDEXES = _("No hay suficientes indices")
_INDEX_ERROR = _("No se encuentra el indice '%(index)s'")
_INVALID_PATH = _("La ruta '%(path)s' no existe")
_INVALID_ATTRIB = _("El nombre de atributo '%(attrib)s' es incorrecto")
_UNKNOWN_PREFIX = _("'%(prefix)s' no se corresponde con ningun ancestro")

# valores validos para los nombres de propiedades
VALID_ATTRIB = re.compile(r'^[a-zA-Z]\w*$')


class ValidHeader(str):

    """Cabecera "validada"

    Derivacion de una cadena de texto que  simplemente comprueba
    al construirse que el valor es un nombre de campo o filtro
    valido.
    """

    def __new__(cls, data):
        parts = [x.strip() or None for x in data.split(".")]
        match = VALID_ATTRIB.match
        if (not 0 < len(parts) <= 2) or (not all(match(x) for x in parts)):
            raise ValueError, _INVALID_ATTRIB % {'attrib': str(data)}
        obj = str.__new__(cls, ".".join(parts))
        obj.suffix = parts.pop()
        obj.prefix = parts.pop() if parts else None
        return obj


class RowFilter(set):

    def __init__(self, attr, headers):
        """Construye un filtro segun la cabecera.

        Construye un filtro que recibe un DataSet y filtra el atributo
        "name", devolviendo un DataSet filtrado. El criterio de filtrado
        lo da la cabecera "header": Los campos se comparan con
        "name.XXX", y si coinciden, se retiran de la cabecera y se filtra
         por el campo XXX del DataSet.
        """
        set.__init__(self)
        self.attr = attr
        for h in headers:
            if h.prefix and attr.startswith(h.prefix):
                self.add(h)
                headers.remove(h)

    def __call__(self, dset, item):
        """Filtra el dataset"""
        dset = getattr(dset, self.attr)
        if len(self):
            try:
                crit = dict((h.suffix, item.pop(h)) for h in self)
            except KeyError:
                raise SyntaxError, _NOT_ENOUGH_INDEXES
            dset = dset(**crit)
            if not dset:
                raise SyntaxError, _INDEX_ERROR % {'index': str(crit)}
        return dset


class TableParser(list):

    """Factoria de objetos

    Esta factoria de objetos carga tablas completas de datos, obtenidas de
    ficheros CSV o de cualquier otro medio. Cada tabla tiene una ruta, unos
    filtros, y unos datos:

     - La ruta define cual es el DataType de los datos (por ejemplo,
       sedes.switches.vlans)
     - Los filtros definen como determinar a que DataObject se le
       agregan los datos (por ejemplo, filtrando por sedes.nombre,
       switches.id, etc)

    El TableParser es una lista de pares (source, bloque). "source" es
    el origen de datos del que procede el bloque. El "bloque" es una lista
    de entradas (id, diccionario) con un atributo "headers" que lista todas
    las claves de los diccionarios como ValidHeaders.

    :data - El DataObject raiz
    :path - La lista de nombres de tipos anidados.
    """

    def __init__(self, data, path):
        list.__init__(self)
        self.data = data
        self.attr = path.pop()
        self.path = path

    def __call__(self, item, attrib):
        """Carga el atributo solicitado "attrib" del item"""
        self._type = item._type._DOMD.subtype(attrib)
        if not len(self):
            return self._type._DOMD.new_set()
        while self:
            source, block = self.pop()
            self._block(source, block)
        return item[attrib]

    def _block(self, source, block):
        """Carga un bloque de datos"""
        headers = block.headers[:]
        filters = [RowFilter(x, headers) for x in self.path]
        attfilt = RowFilter(self.attr, headers)
        for h in (x for x in headers if x.prefix):
            raise DataError(source, 'header', _UNKNOWN_PREFIX % {'prefix': h})           
        self._type._DOMD.attribs.update(headers)
        for (itemid, item) in block:
            try:
                self._item(filters, attfilt, item)
            except SyntaxError as details:
                raise DataError(source, itemid, str(details))

    def _update(self, items, attfilt, data):
        """Actualiza un grupo de datos"""
        for item in attfilt(items, data):
            item.update(data)

    def _append(self, items, data):
        """Agrega datos a un grupo de items"""
        for item in asIter(items):
            getattr(item, self.attr).add(self._type(item, data))

    def _item(self, filters, attfilt, item):
        """Carga un elemento"""
        current = self.data
        for filt in filters:
            current = filt(current, item)
        if attfilt:
            self._update(current, attfilt, item)
        else:
            self._append(asIter(current), item)

    def sources(self):
        """Devuelve una lista de los sources que han aportado datos"""
        return dict((s.id, s) for s, block in self).values()

