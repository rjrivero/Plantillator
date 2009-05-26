#!/usr/bin/env python
# -*- vim: expandtab tabstop=4 shiftwidth=4 smarttab autoindent


from gettext import gettext as _

from data.namedtuple import NamedTuple
from data.datatype import DataType, TypeTree


_NOT_ENOUGH_INDEXES = _("No hay suficientes indices")
_INDEX_NOT_FOUND = _("No se encuentra el indice")


TableFilter = NamedTuple("TableFilter",
    """Definicion de un filtro

    In filtro indica:
        - El nombre (relativo) del tipo de objeto que se filtra (name)
        - El tipo de objeto que se filtra (dtype)
        - Los campos de ese objeto que se utilizan en el filtro (fields)
    """,
    name=0, dtype=1, fields=2)


class TableParser(object):

    """Analizador de tablas

    Analiza una tabla. En la linea CSV que define cada elemento de la lista,
    la primera columna debe ser un campo que indexe la lista "madre".
    Por ejemplo:

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

    def __init__(self, typetree):
        """Inicializa el arbol"""
        self.typetree = typetree

    def get_filters(self, datapath, header):
        """Obtiene la secuencia de filtros indicada por la cabecera dada

        Recibe una ruta hacia un objeto, en el mismo formato que
        TypeTree.get_types. Asociada a esa ruta, recibe una lista de campos,
        una cabecera, que identifica con que criterio se filtrara en cada
        paso de la ruta.

        Ademas, conforme va consumiendo campos de la cabecera, los
        va eliminando (pop(0)). Asume que "header" es una lista.

        Por ejemplo:
            datapath: nodos.switches.puertos
            header: ['nodo.nombre', 'switch.id', 'nombre', 'velocidad', 'modo']

        Devolveria una secuencia:
            filtros: [
                ('nodos', [DataType<nodos>], ("nombre",)),
                ('vlans', [DataType<nodos.vlans>], ("vlan",)),
                ('puertos', [DataType<nodos.vlans.puertos>], (,))
            ]
        Y dejaria en header
            ['nombre', 'velocidad', 'modo']
        """
        for name, dtype in self.typetree.get_types(datapath):
            fields, dummy = [], DataType(dtype) # solo para normalizacion
            while header:
                parts = header[0].split(".")
                if len(parts) == 2 and name.startswith(parts[0].strip()):
                    field = dummy.add_field(parts[1])
                    if field is None:
                        raise SyntaxError, header[0]
                    header.pop(0)
                    fields.append(field)
                else:
                    break
            yield TableFilter(name, dtype, fields)

    def do_type(self, dtype, header):
        """Actualiza el tipo con los campos presentes en la cabecera

        Cada campo de la cabecera se incluye en el tipo de la manera adecuada,
        es decir, normalizando el nombre, definiendolo como bloqueante o no
        bloqueante, etc.

        devuelve una lista de los campos convenientemente normalizados.
        """
        normalized = []
        for item in (x.strip() for x in header):
            if item.endswith("*"):
                normalized.append(dtype.add_field(item[:-1], False))
            else:
                normalized.append(dtype.add_field(item, True))
        return normalized
              
    def do_filter(self, dataset, filters, line):
        """Aplica los filtros especificados a una linea

        Los filtros son el valor devuelto por get_filter. "dataset"
        es el objeto raiz, y line es la linea del CSV a procesar.

        devuelve el dataset resultado de aplicar el filtro,
        y lo que queda de la linea tras consumir los valores necesarios.
        """
        for name, dtype, fields in filters:
            if len(fields) > len(line):
                raise ValueError, _NOT_ENOUGH_INDEXES
            crit = dict(zip(fields, line))
            line = line[len(fields):]
            dataset = getattr(dataset, name)(**crit)
            if not dataset:
                raise ValueError, _INDEX_NOT_FOUND
        return (dataset, line)

