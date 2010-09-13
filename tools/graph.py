#!/usr/bin/env python


from collections import namedtuple, defaultdict
from itertools import chain

from plantillator.meta import SYMBOL_SELF


# Descriptor de un elemento del grafo, bien un nodo o bien
# un extremo de un enlace.
ItemDescriptor = namedtuple("ItemDescriptor", "ID, label, attribs")


def dot_escape(data):
    """Parecido a repr, pero usa comillas dobles en lugar de simples"""
    return "'".join(repr(x)[1:-1] for x in data.split("'")).replace('"', '\\"')


class NodeList(tuple):

    """Lista de nodos con atributos comunes"""

    def __new__(cls, items, id_resolver, label_resolver,
                shape=None, rank=None, attribs=None):
        """"Construye un grupo de nodos con atributos comunes.
        
        items:      Nodos que forman el grupo
        item_id:    Resolver que obtiene el ID de cada nodo
        item_label: Resolver que obtiene el label de cada nodo.
        shape:      Nombre del icono que debe tener el objeto.
        rank:       Rango jerarquico del objeto (para dot)
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

    def __new__(cls, items, src_id, src_label, src_attribs, dst_id, dst_label, dst_attribs):
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
        obj.attribs = attribs or None
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
                src_table, src_id, src_label, src_attribs, "src_")
            if item._get("PEER"):
                dst_table = { SYMBOL_SELF: item.PEER.up }
                dst_desc  = LinkList._descriptor(
                    dst_table, dst_id, dst_label, dst_attribs, "dst_")
            else:
                dst_desc = None
            yield (src_desc, dst_desc)

    @staticmethod
    def _descriptor(symbols, id_resolver, label_resolver, attrs, prefix):
        """Devuelve un descriptor"""
        ID     = id_resolver._resolve(symbols)
        label  = label_resolver._resolve(symbols)
        if attrs:
            values = (("%s%s" % (prefix, attr), item.get(attr)) for attr in attribs)
            values = dict((x, y) for (x, y) in values if y is not None)
        else:
            values = None
        return ItemDescriptor(ID, label, values)


class NodeGroup(list):

    @property
    def attribs(self):
        return frozenset(chain(*(x.attribs for x in self if x.attribs)))

    @property
    def IDs(self):
        return frozenset(chain(*(x.IDs for x in self)))
        
    def _group_dot(self, label):
        """Convierte un grupo de nodos en un cluster dot"""
        cluster = ""
        if label:
            cluster = label.replace(" ", "")
            yield "\n".join((
                'Subgraph cluster%s {' % cluster,
                '  margin=0.25;',
            ))
            # Fuerzo a que label vaya encerrada entre comillas dobles
            yield '  label="%s";' % dot_escape(label)
        for group in self:
            for item in self._list_dot(group, cluster):
                yield item
        for group in self:
            if group.rank is not None:
                yield '{ rank=%s; %s };' % (group.rank, "; ".join(x.ID for x in group))
        if label:
            yield "}"

    def _list_dot(self, group, label):
        for item in group:
            cluster = item.ID.replace(" ", "")
            shape = 'shapefile="%s",' % group.shape if group.shape else ""
            yield "\n".join((
                'Subgraph cluster%s_%s {' % (label, cluster),
                '  center=true;',
                '  margin=0;',
                '  nodesep=0;',
                '  mindist=0;',
                '  pad=0;',
                # obligo a que el label vaya entre comillas dobles
                '  label="%s";' % dot_escape(item.label),
                '  color=lightgray;',
                '  %s [shape=box, pad=0, label="", penwidth=0, %s fontname=Calibri, fontsize=10];' % (item.ID, shape),
                '}'
            ))

    def dot(self, label):
        return "\n".join(self._group_dot(label))


class Graph(object):
    
    """Objeto Grafo, compuesto por grupos de nodos y enlaces.
    
    Solo se permite un nivel de agrupamiento porque muchos graficos
    con graphviz quedan feotes si se agrupan en mas de un nivel.
    """
    
    def __init__(self):
        self.groups = defaultdict(NodeGroup)
        self.links = list()

    @property
    def attribs(self):
        node_attribs = chain(*(x.attribs for x in self.groups.values()))
        link_attribs = chain(*(x.attribs for x in self.links))
        return frozenset(chain(ribs, link_attribs))

    @property
    def IDs(self):
        return frozenset(chain(*tuple(x.IDs for x in self.groups.values())))

    @property
    def valid_links(self):
        """Devuelve solo los enlaces entre nodos incluidos en la lista"""
        IDs = self.IDs
        return (x for x in self.links if  x[1] is not None
                                      and x[0].ID in IDs and x[1].ID in IDs)

    def add_group(self, gname, items, id_resolver, label_resolver,
                  shape=None, rank=None, attribs=None):
        self.groups[gname].append(
            NodeList(items, id_resolver, label_resolver, shape, rank, attribs))

    def add_links(self, items, src_id, dst_id, src_label, dst_label, src_attribs, dst_attribs):
        self.links.extend(
            LinkList(items, src_id, dst_id, src_label, dst_label,
                     src_attribs, dst_attribs)
        )

    def dot(self):
        yield "Graph full {\n"
        for key, group in self.groups.iteritems():
            yield group.dot(key)
        for link in self.valid_links:
            yield "\n%s -- %s" % (link[0].ID, link[1].ID)
        yield "}\n"
