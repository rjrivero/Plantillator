#!/usr/bin/env python


import os
import os.path
import re
import math

from xml.sax.saxutils import escape
from collections import namedtuple

from cuac.libs.pathfinder import FileSource
from cuac.tools.graph import StringWrapper
from cuac.tools.graph import LINK_SOLID, LINK_DOTTED, LINK_DASHED, LINK_DOUBLE
from cuac.tools.graph import ARROW_SMALL, ARROW_LARGE, ARROW_NONE


SVGDIMS = re.compile(r'<svg[^>]*width="(?P<width>[^"]+)"\s+height="(?P<height>[^"]+)"')
VIEWBOX = re.compile(r'viewBox="-?\d+(\.\d+)?\s+-?\d+(\.\d+)?\s+(?P<width>\d+(\.\d+)?)\s+(?P<height>\d+(\.\d+)?)"')


Resources = namedtuple("Resources", "nattribs, lattribs, shapes")
ShapeFile = namedtuple("Shape", "width, height, data")


def read_svg(path):
    """Lee un fichero SVG.

    Devuelve una tupla (ancho, alto, contenido)
    """
    try:
        data = FileSource(path).read()
        dims = SVGDIMS.search(data)
        if dims:
            width  = dims.group("width")
            height = dims.group("height")
            return ShapeFile(width, height, data)
        vbox = VIEWBOX.search(data)
        if vbox:
            # width  = math.ceil(float(vbox.group("width")))
            # height = math.ceil(float(vbox.group("height")))
            width  = dims.group("width")
            height = dims.group("height")
            return ShapeFile(width, height, data)
    except:
        pass


STYLES = {
    LINK_SOLID: "line",
    LINK_DOTTED: "dotted",
    LINK_DASHED: "dashed",
    LINK_DOUBLE: "line",
}

ARROWS = {
    ARROW_SMALL: "standard",
    ARROW_LARGE: "delta",
    ARROW_NONE: "none",
}


def YedGraph(graph, shapedir="iconos", plain=False):
    """Convierte un grafo en texto en formato yEd

    - shapedir: Directorio donde encontrar los iconos (en .svg)
    - plain: si es True, se ignora la clasificacion en grupos.
    """
    # Primero, asegurarnos de que las shapes son legibles
    gshapes   = tuple(x for x in graph.shapes if x)
    sfiles    = dict((s, read_svg(os.path.join(shapedir, s)+".svg")) for s in gshapes)
    if any(x is None for x in sfiles.values()):
        return "\n".join(["Could not read the following shapes:",
                 "\n".join(key for (key, value) in sfiles.iteritems() if value is None)
              ])
    # Primero, encontrar cuantos IDs de recurso tengo que reservar
    # yEd es muy curioso... cuando cargue este grafico me va a mostrar
    # los atributos alreves, pero cuando lo guarde les vuelve a dar
    # la vuelta.
    reserved  = 10 # No. de IDs de atributo que dejamos libres, por si acaso.
    nattribs  = dict((v, i+reserved) for (i, v) in enumerate(graph.node_attribs))
    reserved  = len(nattribs) + reserved
    lattribs  = dict((v, i+reserved) for (i, v) in enumerate(graph.link_attribs))
    reserved  = len(lattribs) + reserved
    shapes    = dict((v, i+reserved) for (i, v) in enumerate(gshapes))
    resources = Resources(nattribs, lattribs, shapes)
    # Y devolvemos el resultado
    return StringWrapper("\n".join(_graph_yed(graph, resources, sfiles, plain)))


def _graph_yed(graph, resources, sfiles, plain):
    # Cabecera
    #---------
    yield "\n".join((
        '<?xml version="1.0" encoding="UTF-8" standalone="no"?>',
        '<graphml xmlns="http://graphml.graphdrawing.org/xmlns" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" xmlns:y="http://www.yworks.com/xml/graphml" xsi:schemaLocation="http://graphml.graphdrawing.org/xmlns http://www.yworks.com/xml/schema/graphml/1.1/ygraphml.xsd">',
        '<key for="graphml" id="d0" yfiles.type="resources"/>',
        '<key attr.name="description" attr.type="string" for="graph" id="d1"><default/></key>',
        '<key attr.name="description" attr.type="string" for="node" id="d2"><default/></key>',
        '<key attr.name="description" attr.type="string" for="edge" id="d3"><default/></key>',
        '<key for="node" id="d4" yfiles.type="nodegraphics"/>',
        '<key for="edge" id="d5" yfiles.type="edgegraphics"/>',
    ))
    # IDs de recursos
    #----------------
    # Para ordenar los atributos en funcion de su indice.
    # Es importante porque el orden en el que se definan los atributos,
    # es el orden en que yEd los presenta, pero invertido... tocate los
    # webs. De todas formas, despues de guardar, les vuelve a dar la
    # vuelta!
    def key(item):
        return item[1]
    for attrib, index in sorted(resources.nattribs.iteritems(), key=key):
        yield '  <key attr.name="%s" attr.type="string" for="node" id="d%d"><default/></key>' % (attrib, index)
    for attrib, index in sorted(resources.lattribs.iteritems(), key=key):
        yield '  <key attr.name="%s" attr.type="string" for="edge" id="d%d"><default/></key>' % (attrib, index)
    yield '<graph edgedefault="undirected" id="G">'
    # Grupos
    #-------
    index, idmap = 0, dict()
    for key, group in graph.groups.iteritems():
        group.index = index
        index += 1
        if plain or not key:
            group.prefix = None
            pre, post = "", ""
        else:
            group.prefix = "n%04d" % index
            pre, post = tuple(_group_wrapper(group, key))
        yield pre
        gap = 15
        for sublist in group:
            for item in _list_yed(group, gap, sublist, resources, sfiles, idmap):
                yield item
            gap += len(sublist) * GAPX
        yield post
    # Enlaces
    #--------
    IDs = graph.IDs
    edgecount = 0
    #srcindex = resources.lattribs["origen"]
    #dstindex = resources.lattribs["destino"]
    for sublist in graph.links:
        for link in sublist.valid_links(IDs):
            edgecount += 1
            srcid = idmap[link[0].ID]
            dstid = idmap[link[1].ID]
            yield "\n".join((
                '<edge id="e%d" source="%s" target="%s">' % (edgecount, srcid, dstid),
                '<data key="d3">%s --&gt; %s</data>' % (escape(link[0].label), escape(link[1].label)),
                #'<data key="d%d">%s</data>' % (srcindex, escape(link[0].label)),
                #'<data key="d%d">%s</data>' % (dstindex, escape(link[1].label)),
            ))
            for linkside in (link[0], link[1]):
                if linkside.attribs:
                    for key, val in linkside.attribs.iteritems():
                        idattrib = resources.lattribs[key]
                        yield '<data key="d%d">%s</data>' % (idattrib, escape(str(val)))
            yield "\n".join((
                '<data key="d5">',
                '<y:PolyLineEdge>',
                '<y:Path sx="0.0" sy="0.0" tx="0.0" ty="0.0"/>',
                '<y:LineStyle color="%s" type="%s" width="%s"/>' % (sublist.color, STYLES.get(sublist.style, "solid"), sublist.width),
                '<y:Arrows source="%s" target="%s"/>' % (ARROWS.get(sublist.source_arrow, "none"), ARROWS.get(sublist.target_arrow, "none")),
            ))
            if link[2]:
                yield '<y:EdgeLabel alignment="center" distance="2.0" fontFamily="Calibri" fontSize="9" fontStyle="plain" hasBackgroundColor="false" hasLineColor="false" modelName="side_slider" preferredPlacement="source" ratio="0.0" textColor="#000000" visible="true">%s</y:EdgeLabel>' % escape(str(link[2]))
            else:
                # Source label
                yield '<y:EdgeLabel alignment="center" configuration="AutoFlippingLabel" distance="2.0" fontFamily="Calibri" fontSize="9" fontStyle="plain" hasBackgroundColor="false" hasLineColor="false" modelName="free" modelPosition="anywhere" preferredPlacement="source" ratio="0.5" textColor="#000000" visible="true">%s<y:PreferredPlacementDescriptor angle="0.0" angleOffsetOnRightSide="0" angleReference="absolute" angleRotationOnRightSide="co" distance="-1.0" placement="source" side="anywhere" sideReference="relative_to_edge_flow"/></y:EdgeLabel>' % escape(str(link[0].label))
                # Dest label
                yield '<y:EdgeLabel alignment="center" configuration="AutoFlippingLabel" distance="2.0" fontFamily="Calibri" fontSize="9" fontStyle="plain" hasBackgroundColor="false" hasLineColor="false" modelName="free" modelPosition="anywhere" preferredPlacement="source" ratio="0.5" textColor="#000000" visible="true">%s<y:PreferredPlacementDescriptor angle="0.0" angleOffsetOnRightSide="0" angleReference="absolute" angleRotationOnRightSide="co" distance="-1.0" placement="source" side="anywhere" sideReference="relative_to_edge_flow"/></y:EdgeLabel>' % escape(str(link[1].label))
            yield "\n".join((
                '<y:BendStyle smoothed="false"/>',
                '</y:PolyLineEdge>',
                '</data>',
                '</edge>',
            ))
    # Recursos
    #---------
    yield "\n".join((
        '</graph>',
        '<data key="d0">',
        '  <y:Resources>',
    ))
    for shape, key in resources.shapes.iteritems():
        yield "".join((
            '    <y:Resource id="%d" type="java.lang.String">' % key,
            escape(sfiles[shape].data),
            '    </y:Resource>',
        ))
    yield "\n".join((
        '  </y:Resources>',
        '</data>',
        '</graphml>'
    ))


GAPX = 150
GAPY = 150


def _group_wrapper(group, label):
    """Devuelve la cabecera y la cola de un grupo yed"""
    # Rectangulo que va a contener al grupo: alto, ancho, x e y
    total_nodes   = sum(len(sublist) for sublist in group)
    open_bounds   = (GAPY-10, GAPX*(total_nodes+2), 10, 10+group.index*GAPY)
    closed_bounds = (GAPY-10, GAPX, 10, 10+group.index*GAPY)
    label         = escape(str(label))
    yield "\n".join((
        '<node id="%s" yfiles.foldertype="group">' % group.prefix,
        '<data key="d2">%s</data>' % label,
        '<data key="d4">',
        '<y:ProxyAutoBoundsNode>',
        '  <y:Realizers active="0">',
        '    <y:GroupNode>',
        '      <y:Geometry height="%d" width="%d" x="%d" y="%d"/>' % open_bounds,
        '      <y:Fill color="#CAECFF84" transparent="false"/>',
        '      <y:BorderStyle color="#666699" type="dotted" width="1.0"/>',
        '      <y:NodeLabel alignment="right" autoSizePolicy="node_width" backgroundColor="#99CCFF" borderDistance="0.0" fontFamily="Calibri" fontSize="11" fontStyle="plain" hasLineColor="false" modelName="internal" modelPosition="t" textColor="#000000" visible="true" x="0.0" y="0.0">%s</y:NodeLabel>' % label,
        '      <y:Shape type="roundrectangle"/>',
        '      <y:State closed="false" innerGraphDisplayEnabled="false"/>',
        '      <y:Insets bottom="15" bottomF="15.0" left="15" leftF="15.0" right="15" rightF="15.0" top="15" topF="15.0"/>',
        '      <y:BorderInsets bottom="0" bottomF="0.0" left="0" leftF="0.0" right="0" rightF="0.0" top="0" topF="0.0"/>',
        '   </y:GroupNode>',
        '    <y:GroupNode>',
        '     <y:Geometry height="%d" width="%d" x="%d" y="%d"/>' % closed_bounds,
        '      <y:Fill color="#CAECFF84" transparent="false"/>',
        '      <y:BorderStyle color="#666699" type="dotted" width="1.0"/>',
        '      <y:NodeLabel alignment="right" autoSizePolicy="node_width" backgroundColor="#99CCFF" borderDistance="0.0" fontFamily="Calibri" fontSize="11" fontStyle="plain" hasLineColor="false" height="22.37646484375" modelName="internal" modelPosition="t" textColor="#000000" visible="true" x="0.0" y="0.0">%s</y:NodeLabel>' % label,
        '      <y:Shape type="roundrectangle"/>',
        '      <y:State closed="true" innerGraphDisplayEnabled="false"/>',
        '      <y:Insets bottom="15" bottomF="15.0" left="15" leftF="15.0" right="15" rightF="15.0" top="15" topF="15.0"/>',
        '      <y:BorderInsets bottom="0" bottomF="0.0" left="0" leftF="0.0" right="0" rightF="0.0" top="0" topF="0.0"/>',
        '    </y:GroupNode>',
        '  </y:Realizers>',
        '</y:ProxyAutoBoundsNode>',
        '</data>',
        '<graph edgedefault="undirected" id="%s:">' % group.prefix,
    ))
    yield "\n".join((
        '</graph>',
        '</node>'
    ))


def _list_yed(group, gapx, sublist, resources, sfiles, idmap):
    """Crea un nodo yEd por cada nodo del NodeList"""
    for xpos, item in enumerate(sublist):
        # Calculo el ID del nodo, en funcion de su pertenencia a un grupo
        if group.prefix is not None:
            nodeid = "%s::n%s" % (group.prefix, item.ID)
        else:
            nodeid = "n%s" % item.ID
        # Guardo el mapeo de ID real a ID yEd
        idmap[item.ID] = nodeid
        # Saco la cabecera del nodo
        label = escape(str(item.label))
        yield "\n".join((
            '  <node id="%s">' % nodeid,
            '  <data key="d2">%s</data>' % label,
        ))
        # Si hay atributos, los saco tambien
        if item.attribs:
            for key, val in item.attribs.iteritems():
                ref = resources.nattribs[key]
                yield '<data key="d%d">%s</data>' % (ref, escape(str(val)))
        # Obtengo el icono y sus datos: alto, ancho, x e y
        shape = None if not sublist.shape else sfiles[sublist.shape]
#        item_bounds = (shape.height, shape.width, gapx+xpos*GAPX, 15+group.index*GAPY)
        item_bounds = (gapx+xpos*GAPX, 15+group.index*GAPY)
        labeldata = ('plain', '#000000', label)
        if sublist.label:
            labeldata = ('bold', sublist.label, label)
        # Y vuelco el SVG, si lo hay.
        if shape: # Grafico SVG
            yield "\n".join((
                '  <data key="d4">',
                '  <y:SVGNode>',
#               '    <y:Geometry height="%s" width="%s" x="%d" y="%d"/>' % item_bounds,
                '    <y:Geometry x="%d" y="%d"/>' % item_bounds,
                '    <y:Fill color="#CCCCFF" transparent="false"/>',
                '    <y:BorderStyle color="#000000" type="line" width="1.0"/>',
                '    <y:NodeLabel alignment="center" autoSizePolicy="content" fontFamily="Calibri" fontSize="11" fontStyle="%s" hasBackgroundColor="false" hasLineColor="false" height="15.0" width="80.0" modelName="sandwich" modelPosition="s" textColor="%s" visible="true">%s</y:NodeLabel>' % labeldata,
                '    <y:SVGModel svgBoundsPolicy="0">',
                '      <y:SVGContent refid="%d"/>' % resources.shapes[sublist.shape],
                '    </y:SVGModel>',
                '  </y:SVGNode>',
                '  </data>',
            ))
        else: # Cuadradin
            yield "\n".join((
                '  <data key="d4">',
                '  <y:ShapeNode>',
#               '    <y:Geometry height="%s" width="%s" x="%d" y="%d"/>' % item_bounds,
                '    <y:Geometry x="%d" y="%d"/>' % item_bounds,
                '    <y:Fill color="#FFDD33" transparent="false"/>',
                '    <y:BorderStyle color="#000000" type="line" width="1.0"/>',
                '    <y:NodeLabel alignment="center" autoSizePolicy="content" fontFamily="Calibri" fontSize="11" fontStyle="%s" hasBackgroundColor="false" hasLineColor="false" height="15.0" width="80.0" modelName="internal" modelPosition="c" textColor="%s" visible="true">%s</y:NodeLabel>' % labeldata,
                '    <y:Shape type="rectangle"/>',
                '  </y:ShapeNode>',
                '  </data>',
            ))
        yield '</node>'
