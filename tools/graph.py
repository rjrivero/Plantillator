#!/usr/bin/env python


from collections import namedtuple, defaultdict
from itertools import chain

from plantillator.meta import SYMBOL_SELF


# Descriptor de un elemento del grafo, bien un nodo o bien
# un extremo de un enlace.
ItemDescriptor = namedtuple("ItemDescriptor", "ID, label, attribs")


# Estilos de linea
LINK_SOLID  = 0
LINK_DOTTED = 1
LINK_DASHED = 2


class NodeList(tuple):

    """Lista de nodos con atributos comunes"""

    def __new__(cls, items, id_resolver, label_resolver,
                shape=None, rank=None, attribs=None):
        """"Construye un grupo de nodos con atributos comunes.
        
        items:      Nodos que forman el grupo
        item_id:    Resolver que obtiene el ID de cada nodo
        item_label: Resolver que obtiene el label de cada nodo.
        shape:      Nombre del icono que debe tener el objeto.
        rank:       Rango jerarquico del objeto (para dot, principalmente)
        attribs:    Nombres de los atributos que se exportaran.
        """
        obj = super(NodeList, cls).__new__(cls, NodeList._process(
            items, id_resolver, label_resolver, attribs))
        obj.attribs = attribs
        obj.IDs = frozenset(x.ID for x in obj)
        obj.shape = shape
        obj.rank = rank
        return obj

    @staticmethod
    def _process(items, id_resolver, label_resolver, attribs):
        """Itera sobre los objetos, devolviendo tuplas.
        
        Las tuplas que devuelve contienen:
        (ID, label, shape, { attribs })
        """
        for item in items:
            # Obtengo el ID y el label de cada atributo desde el resolver
            symbol_table = { SYMBOL_SELF: item }
            ID = id_resolver._resolve(symbol_table)
            label = label_resolver._resolve(symbol_table)
            # Obtengo los atributos del objeto pedidos
            if attribs:
                values = ((attr, item.get(attr)) for attr in attribs)
                values = dict((x, y) for (x, y) in values if y is not None)
            else:
                values = None
            # y devuelvo el descriptor
            yield ItemDescriptor(ID, label, values)


class LinkList(tuple):
    
    """Lista de enlaces con atributos comunes"""

    def __new__(cls, items,
        src_id, src_label, src_attribs,
        dst_id, dst_label, dst_attribs,
        style=LINK_SOLID, width=1, color="#000000"):
        """"Construye un grupo de enlaces con atributos comunes.
        
        items:       Nodos que forman el grupo
        src_id:      Resolver que obtiene el ID del nodo padre del enlace
        dst_id:      Resolver que obtiene el ID del nodo padre del PEER
        src_label:   Resolver que obtiene el label del nodo padre del enlace
        dst_label:   Resolver que obtiene el label del nodo padre del PEER
        src_attribs: Lista de atributos del nodo origen.
        dst_attribs: Lista de atributos del nodo destino.
        """
        obj = super(LinkList, cls).__new__(cls, LinkList._process(
            items,
            src_id, src_label, src_attribs,
            dst_id, dst_label, dst_attribs))
        attribs = set()
        if src_attribs:
            attribs.update("%s%s" % ("src_", attrib) for attrib in src_attribs)
        if dst_attribs:
            attribs.update("%s%s" % ("dst_", attrib) for attrib in dst_attribs)
        # Meto los atributos "origen" y "destino", que pertenen a todos
        # los enlaces.
        attribs.update(("origen", "destino"))
        obj.style = style
        obj.width = width
        obj.color = color
        obj.attribs = attribs
        return obj

    @staticmethod
    def _process(items, src_id, src_label, src_attribs, dst_id, dst_label, dst_attribs):
        """Itera sobre los objetos, devolviendo tuplas.
        
        Las tuplas que devuelve contienen un ItemDescriptor para el
        origen y otro para el destino.
        """
        for item in items:
            # Obtengo el ID y el label de cada atributo desde el resolver
            src_table = { SYMBOL_SELF: item.up }
            src_desc  = LinkList._descriptor(
                item, src_table,
                src_id, src_label, src_attribs, "src_")
            if item._get("PEER"):
                dst_table = { SYMBOL_SELF: item.PEER.up }
                dst_desc  = LinkList._descriptor(
                    item.PEER, dst_table,
                    dst_id, dst_label, dst_attribs, "dst_")
            else:
                dst_desc = None
            yield (src_desc, dst_desc)

    @staticmethod
    def _descriptor(link, symbols, id_resolver, label_resolver, attribs, prefix):
        """Devuelve un descriptor"""
        ID     = id_resolver._resolve(symbols)
        label  = label_resolver._resolve(symbols)
        if attribs:
            values = (("%s%s" % (prefix, attr), link.get(attr)) for attr in attribs)
            values = dict((x, y) for (x, y) in values if y is not None)
        else:
            values = None
        return ItemDescriptor(ID, label, values)

    def valid_links(self, IDs):
        return (link for link in self
                     if link[1] is not None
                     and link[0].ID in IDs
                     and link[1].ID in IDs
        )


class NodeGroup(list):

    @property
    def attribs(self):
        return frozenset(chain(*(x.attribs for x in self if x.attribs)))

    @property
    def IDs(self):
        return frozenset(chain(*(x.IDs for x in self)))

    @property
    def shapes(self):
        return frozenset(x.shape for x in self)


class Graph(object):
    
    """Objeto Grafo, compuesto por grupos de nodos y enlaces.
    
    Solo se permite un nivel de agrupamiento porque muchos graficos
    quedan feotes de todas formas, si se agrupan en mas de un nivel.
    
    Dicho de otra forma: si se necesita mas de un nivel, es mas recomendable
    hacer el grafico por capas. Y ya veremos como enlazamos unas capas con
    otras...
    """
    
    def __init__(self):
        self.groups = defaultdict(NodeGroup)
        self.links = list()

    @property
    def node_attribs(self):
        return frozenset(chain(*(x.attribs for x in self.groups.values())))

    @property
    def link_attribs(self):
        return frozenset(chain(*(x.attribs for x in self.links)))

    @property
    def shapes(self):
        return frozenset(chain(*(x.shapes for x in self.groups.values())))

    @property
    def IDs(self):
        return frozenset(chain(*tuple(x.IDs for x in self.groups.values())))

    def add_links(self, items,
        src_id, src_label, src_attribs,
        dst_id, dst_label, dst_attribs,
        style=LINK_SOLID, width=1, color="#000000"):
        self.links.append(
            LinkList(items,
                src_id, src_label, src_attribs,
                dst_id, dst_label, dst_attribs,
                style=style, width=width, color=color
            )
        )

    def add_group(self, gname, items, id_resolver, label_resolver,
                  shape=None, rank=None, attribs=None):
        self.groups[gname].append(
            NodeList(items, id_resolver, label_resolver, shape, rank, attribs)
        )
