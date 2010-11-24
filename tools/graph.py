#!/usr/bin/env python


from copy import copy
from collections import namedtuple, defaultdict
from itertools import chain, groupby, izip

from .builder import SpecBuilder, BuilderHelper


# Estilos de linea
LINK_SOLID  = "solid"
LINK_DOTTED = "dotted"
LINK_DASHED = "dashed"

# Estilos de flecha
ARROW_SMALL = "small"
ARROW_LARGE = "large"
ARROW_NONE  = "none"


class ItemDescriptor(object):

    """
    Descriptor de un elemento del grafo, bien un nodo o bien
    un extremo de un enlace.
    """

    __slots__ = ("ID", "label", "attribs", "objID")

    def __init__(self, objID, ID, label, attribs):
        self.ID = ID
        self.label = label
        self.attribs = attribs or dict()
        self.objID = objID

    def update(self, other):
        self.label = other.label
        self.attribs.update(other.attribs)


class LinkDescriptor(tuple):

    """Descriptor de un enlace, combina los descriptores de ambos extremos"""

    def __new__(cls, objID, src_desc, dst_desc):
        obj = super(LinkDescriptor, cls).__new__(cls, (src_desc, dst_desc))
        obj.objID = objID
        return obj


class OrderedFSet(tuple):
    
    """Una especie de frozenset que recuerda el orden de insercion.
    
    Cuando se itera sobre el, lo hace en el mismo orden en que
    estuvieran los elementos en la secuencia inicial.
    
    Lo utilizo para las listas de atributos de nodos y enlaces, porque
    el orden en que se definan es luego el orden en que yEd las presenta
    (independientemente del identificador que se les asigne).
    """

    def __new__(cls, sequence):
        ordered = dict()
        for index, val in enumerate(sequence):
            ordered.setdefault(val, index)
        ordered = ((idx, val) for (val, idx) in ordered.iteritems())
        return super(OrderedFSet, cls).__new__(cls, (x[1] for x in sorted(ordered)))


class StringWrapper(tuple):

    """Objeto que envuelve una cadena en una tuple.

    Es para poder usar una cadena de texto como entrada a un filtro
    de Templite (que normalmente reciben una secuencia de cadenas)
    """

    def __new__(cls, string):
        return super(StringWrapper, cls).__new__(cls, (string,))

    def __str__(self):
        return self[0]


class NodeProperties(object):

    """Propiedades comunes de un grupo de nodos"""

    DEFAULTS = {
        "rank":  None,
        "shape": None,
    }

    def __init__(self, attribs=None, **kw):
        """"Construye un grupo de nodos con atributos comunes.
        
        shape:      Nombre del icono que debe tener el objeto.
        rank:       Rango jerarquico del objeto (para dot, principalmente)
        attribs:    Nombres de los atributos que se exportaran.
        """
        self.attribs = attribs
        for key, val in NodeProperties.DEFAULTS.iteritems():
            setattr(self, key, kw.get(key, val))

    @staticmethod
    def process(items, id_resolver, label_resolver, attribs):
        """Itera sobre los objetos, devolviendo tuplas.
        
        Las tuplas que devuelve son ItemDescriptors:
        ItemDescriptor(ID, label, { attribs })
        """
        for item in items:
            # Obtengo el ID y el label de cada atributo desde el resolver
            ID = id_resolver(item)
            label = label_resolver(item)
            # Obtengo los atributos del objeto pedidos
            if attribs:
                values = ((attr, item.get(attr)) for attr in attribs)
                values = dict((x, y) for (x, y) in values if y is not None)
            else:
                values = None
            # y devuelvo el descriptor
            yield ItemDescriptor(id(item), ID, label, values)

    def combine(self, new_props, **kw):
        """Crea un nuevo objeto con las propiedades combinadas"""
        # Copio este objeto, y le agrego los atributos nuevos
        anew = copy(self)
        anew.attribs = OrderedFSet(chain(anew.attribs, new_props.attribs))
        # Machaco todos los parametros existentes con los nuevos
        defaults = NodeProperties.DEFAULTS
        for key, val in kw.iteritems():
            if key in defaults:
                setattr(anew, key, val)
        return anew


class NodeList(tuple):

    """Lista de nodos con atributos comunes"""

    def __new__(cls, properties, descriptors):
        """"Construye un grupo de nodos con atributos comunes"""
        obj = super(NodeList, cls).__new__(cls, descriptors)
        obj.__dict__.update(properties.__dict__)
        obj.IDs = frozenset(x.ID for x in descriptors)
        return obj


class LinkProperties(object):

    """Propiedades comunes a un grupo de enlaces"""

    DEFAULTS = {
        "style": LINK_SOLID,
        "width": 1,
        "color": "#000000",
        "source_arrow": ARROW_NONE,
        "target_arrow": ARROW_NONE,
    }

    def __init__(self, src_attribs, dst_attribs, **kw):
        """"Construye un grupo de enlaces con atributos comunes.
        
        src_attribs: Lista de atributos del nodo origen.
        dst_attribs: Lista de atributos del nodo destino.
        """
        attribs = list()
        if src_attribs:
            attribs.extend("%s%s" % ("src_", attrib) for attrib in src_attribs)
        if dst_attribs:
            attribs.extend("%s%s" % ("dst_", attrib) for attrib in dst_attribs)
        self.attribs = OrderedFSet(attribs)
        for key, val in LinkProperties.DEFAULTS.iteritems():
            setattr(self, key, kw.get(key, val))

    @staticmethod
    def process(items,
        src_id, src_label, src_attribs,
        dst_id, dst_label, dst_attribs):
        """Itera sobre los objetos, devolviendo tuplas.
        
        Las tuplas que devuelve contienen itemdescriptors:
        - un ItemDescriptor para el origen.
        - un ItemDescriptor para el destino.
        """
        for item in (x for x in items if x._get("PEER")):
            # Obtengo el ID y el label de cada atributo desde el resolver
            src_desc  = LinkProperties._descriptor(
                item, item.up,
                src_id, src_label, src_attribs, "src_")
            dst_desc  = LinkProperties._descriptor(
                item.PEER, item.PEER.up,
                dst_id, dst_label, dst_attribs, "dst_")
            yield LinkDescriptor(id(item), src_desc, dst_desc)

    @staticmethod
    def _descriptor(link, item, id_resolver, label_resolver, attribs, prefix):
        """Devuelve un descriptor"""
        ID     = id_resolver(item)
        label  = label_resolver(item)
        if attribs:
            values = (("%s%s" % (prefix, attr), link.get(attr)) for attr in attribs)
            values = dict((x, y) for (x, y) in values if y is not None)
        else:
            values = None
        return ItemDescriptor(None, ID, label, values)

    def combine(self, new_props, **kw):
        """Crea un nuevo objeto con las propiedades combinadas"""
        # Copio este objeto, y le agrego los atributos nuevos
        anew = copy(self)
        anew.attribs = OrderedFSet(chain(
            (x for x in anew.attribs if x.startswith("src_")),
            (x for x in new_props.attribs if x.startswith("src_")),
            (x for x in anew.attribs if x.startswith("dst_")),
            (x for x in new_props.attribs if x.startswith("dst_")),
        ))
        # Machaco todos los parametros existentes con los nuevos
        defaults = LinkProperties.DEFAULTS
        for key, val in kw.iteritems():
            if key in defaults:
                setattr(anew, key, val)
        return anew


class LinkList(tuple):
    
    """Lista de enlaces con atributos comunes"""

    def __new__(cls, properties, descriptors):
        """"Construye un grupo de enlaces con atributos comunes"""
        obj = super(LinkList, cls).__new__(cls, descriptors)
        obj.__dict__.update(properties.__dict__)
        return obj

    def valid_links(self, IDs):
        return (link for link in self
                     if  link[0].ID in IDs
                     and link[1].ID in IDs
        )


class NodeGroup(tuple):

    """Lista de NodeLists pertenecientes a un mismo grupo"""

    def __new__(cls, nodes):
        def key(node):
            return node.properties
        def group():
            for prop, subnodes in groupby(sorted(nodes, key=key), key):
                yield NodeList(prop, (x.descriptor for x in subnodes))
        return super(NodeGroup, cls).__new__(cls, group())
            
    @property
    def attribs(self):
        return OrderedFSet(chain(*(x.attribs for x in self if x.attribs)))

    @property
    def IDs(self):
        return frozenset(chain(*(x.IDs for x in self)))

    @property
    def shapes(self):
        return frozenset(x.shape for x in self)


class Node(object):

    """Representa un nodo del grafo"""
    
    __slots__ = ("group", "properties", "descriptor")
    
    def __init__(self, group, properties, descriptor):
        self.group = group
        self.properties = properties
        self.descriptor = descriptor

    def update(self, new_node, new_properties):
        """Actualiza el link con los nuevos datos y propiedades"""
        self.descriptor.update(new_node.descriptor)
        self.properties = new_properties


class Link(object):

    """Representa un enlace del grafo"""

    __slots__ = ("properties", "descriptor")

    def __init__(self, properties, descriptor):
        self.properties = properties
        self.descriptor = descriptor

    def update(self, new_link, new_properties):
        """Actualiza el link con los nuevos datos y propiedades"""
        new_descriptor = new_link.descriptor
        for anew, aold in izip(new_descriptor, self.descriptor):
            aold.update(anew)
        self.properties = new_properties


class Graph(object):
    
    """Objeto Grafo, compuesto por grupos de nodos y enlaces.
    
    Solo se permite un nivel de agrupamiento porque muchos graficos
    quedan feotes de todas formas, si se agrupan en mas de un nivel.
    
    Dicho de otra forma: si se necesita mas de un nivel, es mas recomendable
    hacer el grafico por capas. Y ya veremos como enlazamos unas capas con
    otras...
    """
    
    def __init__(self):
        self.node_dict = dict()
        self.link_dict = dict()

    @property
    def node_properties(self):
        return frozenset(x.properties for x in self.node_dict.values())

    @property
    def link_properties(self):
        return frozenset(x.properties for x in self.link_dict.values())

    @property
    def node_attribs(self):
        return OrderedFSet(chain(*(x.attribs for x in self.node_properties if x.attribs)))

    @property
    def link_attribs(self):
        return OrderedFSet(chain(*(x.attribs for x in self.link_properties if x.attribs)))

    @property
    def shapes(self):
        return frozenset(x.shape for x in self.node_properties)

    @property
    def IDs(self):
        return frozenset(x.descriptor.ID for x in self.node_dict.values())

    def add_group(self, gname, items, id_resolver, label_resolver,
                  attribs=None, **kw):
        """Agrega un grupo de nodos al grafo.

        Si alguno de los nodos estaba ya en el grafo, sus propiedades
        y atributos se reemplazan por los que se especifiquen ahora.

        Los kw reconocidos son:
            - "shape": nombre del icono
            - "rank": rango de los nodos, para Dot.
        """
        # Creo un nuevo objeto Properties y convierto los items en descriptores.
        properties  = NodeProperties(attribs, **kw)
        descriptors = NodeProperties.process(items,
            id_resolver, label_resolver, attribs)
        # Si los nodos ya existen, lo que hago es actualizar sus propiedades.
        # Para actualizarlas, se crea un nuevo objeto "Properties" con una
        # combinacion de las propiedades antiguas, y las nuevas.
        #
        # No quiero crear un objeto Properties distinto por cada nodo solapado,
        # sino solamente uno por cada combinacion encontrada de (properties
        # antiguas, properties nuevas). Para eso, voy a crear un diccionario
        # donde ire guardando esas combinaciones.
        new_properties = dict()
        for descriptor in descriptors:
            new_node = Node(gname, properties, descriptor)
            old_node = self.node_dict.setdefault(descriptor.objID, new_node)
            if old_node is not new_node:
                new_prop = new_properties.get(old_node.properties, None)
                if not new_prop:
                    new_prop = old_node.properties.combine(properties, **kw)
                    new_properties[old_node.properties] = new_prop
                old_node.update(new_node, new_prop)

    def add_links(self, items,
                  src_id, src_label, src_attribs,
                  dst_id, dst_label, dst_attribs,
                  **kw):
        """Agrega un grupo de enlaces al grafo.

        Si alguno de los enlaces estaba ya en el grafo, sus atributos
        y propiedades se sustituyen por los que se especifiquen ahora.

        Los kw reconocidos son:

        - style: "dotted", "dashed", "solid"
        - width: ancho de la linea
        - color: color de la linea
        - source_arrow: flecha en el origen
        - target_arrow: flecha en el destino
        """
        properties  = LinkProperties(src_attribs, dst_attribs, **kw)
        descriptors = LinkProperties.process(items,
            src_id, src_label, src_attribs,
            dst_id, dst_label, dst_attribs)
        new_properties = dict()
        for descriptor in descriptors:
            new_link = Link(properties, descriptor)
            old_link = self.link_dict.setdefault(descriptor.objID, new_link)
            if old_link is not new_link:
                new_prop = new_properties.get(old_link.properties)
                if not new_prop:
                    new_prop = old_link.properties.combine(properties, **kw)
                    new_properties[old_link.properties] = new_prop
                old_link.update(new_link, new_prop)

    @property
    def groups(self):
        """Devuelve un diccionario donde:

        - Cada clave es un nombre de grupo
        - Cada valor es un NodeGroup con todos los NodeLists del grupo.
        """
        def key(item):
            return item.group
        return dict((group, NodeGroup(items)) for (group, items)
            in groupby(sorted(self.node_dict.values(), key=key), key))

    @property
    def links(self):
        """Devuelve una lista donde cada elemento es un LinkList"""
        def key(item):
            return item.properties
        return tuple(LinkList(prop, (x.descriptor for x in items)) for (prop, items)
            in groupby(sorted(self.link_dict.values(), key=key), key))


x = BuilderHelper()

GraphHelper = (x.grafo << [
    x.grupo(args="id") << [
        x.props(args="id_resolver, label_resolver, attribs") << [
            x.estilo(kwargs="shape, rank") << "Nodos del grafo"
        ]
    ],
    x.enlaces << [
        x.props(args="src_id, src_label, src_attribs, dst_id, dst_label, dst_attribs") << [
            x.estilo(kwargs="style, width, color") << "Enlaces del grafo"
        ]
    ]
]).build(SpecBuilder())


class GraphBuilder(object):

    """Construye un objeto Graph a partir de un GraphHelper"""

    def grafo(self, parent):
        yield (Graph(), None)

    def grupo(self, parent, groupid):
        def func(*arg, **kw):
            parent.add_group(groupid, *arg, **kw)
        yield (func, None)

    def enlaces(self, parent):
        yield (parent.add_links, None)

    def props(self, parent, *args):
        yield ((parent, args), None)

    def estilo(self, parent, **kw):
        func, args = parent
        items = list()
        yield (None, items.append)
        func(items, *args, **kw)
