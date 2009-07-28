#!/usr/bin/env python
# -*- vim: expandtab tabstop=4 shiftwidth=4 smarttab autoindent


from gettext import gettext as _

from ..data.base import DataError
from .loader import TableLoader, Block
from .parser import *


_INVALID_VARNAME = _("El nombre %(varname)s no es valido")


class DataSource(TableLoader):

    """Carga e interpreta ficheros de datos"""

    _HOOKS = {
        'variables':    "_variables",
        'dependencias': "_dependencias"
    }

    def read(self, source, data):
        """Carga un fichero de datos, actualiza el diccionario.

        Devuelve una lista con las dependencias del fichero.
        """
        TableLoader.read(self, source, data)
        self.dependencies, remove = list(), list()
        for path, parser in self.iteritems():
            try:
                hook = getattr(self, self._HOOKS[path.lower()])
                remove.append(path)
            except (KeyError, AttributeError):
                pass
            else:
                self.lineno = "N/A"
                for source, block in parser:
                    try:
                        hook(source, block)
                    except (IndexError, TypeError) as details:
                        raise DataError(source, self.lineno, details)
        for path in remove:
            del(self[path])
        return self.dependencies

    def _variables(self, source, block):
        nombre, valor = block.headers[0], block.headers[1]
        for self.lineno, item in block:
            varname = item[nombre]
            if not varname or not VALID_ATTRIB.match(str(varname)):
                raise DataError(source, self.lineno,
                         _INVALID_VARNAME % {'varname': str(varname)})
            self.data[varname] = item[valor]

    def _dependencias(self, source, block):
        nombre = block.headers[0]
        for self.lineno, item in block:
            self.dependencies.append(item[nombre])

