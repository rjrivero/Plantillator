#!/usr/bin/env python


# He copiado la funcionalidad que necesito de pydot, porque
# solo me hace falta la parte de localizar los ejecutables y llamarlos.
# No voy a manipular graficos como objetos python ni nada de eso.

from __future__ import with_statement

import subprocess
import os
import os.path

from cuac.tools.graph import StringWrapper
from cuac.tools.graph import LINK_SOLID, LINK_DOTTED, LINK_DASHED, LINK_DOUBLE
from cuac.tools.graph import ARROW_SMALL, ARROW_LARGE, ARROW_NONE


class DotFilter(str):

    """Filtro que procesa un fichero con Graphviz"""

    @staticmethod
    def _find_executables(path):
        """Used by find_graphviz
        
        path - single directory as a string
        
        If any of the executables are found, it will return a dictionary
        containing the program names as keys and their paths as values.
        
        Otherwise returns None
        """
        success = False
        progs = {'dot': '', 'twopi': '', 'neato': '', 'circo': '', 'fdp': '', 'sfdp': ''}
        was_quoted = False
        path = path.strip()
        if path.startswith('"') and path.endswith('"'):
            path = path[1:-1]
            was_quoted =  True
        if os.path.isdir(path) : 
            for prg in progs.keys():
                if progs[prg]:
                    continue
                if os.path.exists( os.path.join(path, prg) ):
                    if was_quoted:
                        progs[prg] = '"' + os.path.join(path, prg) + '"'
                    else:
                        progs[prg] = os.path.join(path, prg)
                    success = True
                elif os.path.exists( os.path.join(path, prg + '.exe') ):
                    if was_quoted:
                        progs[prg] = '"' + os.path.join(path, prg + '.exe') + '"'
                    else:
                        progs[prg] = os.path.join(path, prg + '.exe')
                    success = True
        if success:
            return progs
        else:
            return None

    # The multi-platform version of this 'find_graphviz' function was
    # contributed by Peter Cock
    #
    @staticmethod
    def _find_graphviz():
        """Locate Graphviz's executables in the system.
        
        Tries three methods:
        
        First: Windows Registry (Windows only)
        This requires Mark Hammond's pywin32 is installed.
        
        Secondly: Search the path
        It will look for 'dot', 'twopi' and 'neato' in all the directories
        specified in the PATH environment variable.
        
        Thirdly: Default install location (Windows only)
        It will look for 'dot', 'twopi' and 'neato' in the default install
        location under the "Program Files" directory.
        
        It will return a dictionary containing the program names as keys
        and their paths as values.
        
        If this fails, it returns None.
        """    
        # Method 1 (Windows only)
        #
        if os.sys.platform == 'win32':
            try:
                import win32api, win32con
                # Get the GraphViz install path from the registry
                #
                hkey = win32api.RegOpenKeyEx( win32con.HKEY_LOCAL_MACHINE,
                    "SOFTWARE\ATT\Graphviz", 0, win32con.KEY_QUERY_VALUE )
                path = win32api.RegQueryValueEx( hkey, "InstallPath" )[0]
                win32api.RegCloseKey( hkey )
                # Now append the "bin" subdirectory:
                #
                path = os.path.join(path, "bin")
                progs = DotFilter._find_executables(path)
                if progs is not None :
                    #print "Used Windows registry"
                    return progs
            except ImportError :
                # Print a messaged suggesting they install these?
                #
                pass
    
        # Method 2 (Linux, Windows etc)
        #
        if os.environ.has_key('PATH'):
            for path in os.environ['PATH'].split(os.pathsep):
                progs = DotFilter._find_executables(path)
                if progs is not None :
                    #print "Used path"
                    return progs
        # Method 3 (Windows only)
        #
        if os.sys.platform == 'win32':
            # Try and work out the equivalent of "C:\Program Files" on this
            # machine (might be on drive D:, or in a different language)
            #
            if os.environ.has_key('PROGRAMFILES'):
                # Note, we could also use the win32api to get this
                # information, but win32api may not be installed.
                path = os.path.join(os.environ['PROGRAMFILES'], 'ATT', 'GraphViz', 'bin')
            else:
                #Just in case, try the default...
                path = r"C:\Program Files\att\Graphviz\bin"
            progs = DotFilter._find_executables(path)
            if progs is not None :
                #print "Used default install location"
                return progs
        # Method 4 (A bunch of default directories)
        #
        for path in (
            '/usr/bin', '/usr/local/bin',
            '/opt/bin', '/sw/bin', '/usr/share',
            '/Applications/Graphviz.app/Contents/MacOS/' ):
            progs = DotFilter._find_executables(path)
            if progs is not None :
                #print "Used path"
                return progs
        # Failed to find GraphViz
        #
        return None

    @classmethod
    def get_path(cls, prog):
        try:
            return cls.PATHS.get(prog, None)
        except AttributeError:
            pass
        progs = DotFilter._find_graphviz() or dict()
        if progs:
            for key in progs:
                if not os.path.exists( progs[key] ) or not os.path.isfile( progs[key] ):
                    progs[key] = None
        cls.PATHS = progs
        return progs.get(prog, None)

    def __call__(self, strings):
        """Crea un fichero .png utilizando el lenguaje DOT de graphviz.
    
        Es un filtro que siempre debe ser invocado despues de SAVEAS.
        """
        if len(strings) != 1 or not os.path.isfile(strings[0]):
            return ("*** ERROR: NO INPUT FILE ***" ,)
        prog = DotFilter.get_path(self)
        if prog is None:
            return ("*** ERROR: NO PROGRAM %s ***" % self,)
        outname = os.path.splitext(strings[0])[0] + ".png"
        with open('/dev/null', 'wb') as nullfd: 
            status = subprocess.call((prog, '-Tpng', "-o%s" % outname, strings[0]), stdout=nullfd, stderr=nullfd)
        if status != 0:
           return ("*** ERROR %s RETURNED %d ***" % (self, status),)
        return (outname,)


DOT   = DotFilter("dot")
NEATO = DotFilter("neato")
CIRCO = DotFilter("circo")
TWOPI = DotFilter("twopi")
FDP   = DotFilter("fdp")
SFDP  = DotFilter("sfdp")


STYLES = {
    LINK_SOLID: "solid",
    LINK_DOTTED: "dotted",
    LINK_DASHED: "dashed",
    LINK_DOUBLE: "solid",
}


ARROWS = {
    ARROW_SMALL: "normal",
    ARROW_LARGE: "dot",
    ARROW_NONE:  "none",
}


def DotGraph(graph, shapedir="iconos", scale=False):
    """Convierte un grafo en texto en formato dot"""
    return StringWrapper("\n".join(_graph_dot(graph, shapedir, scale)))


def _dot_escape(data):
    """Escapa un texto para meterlo en un atributo de dot"""
    # Antes usaba "repr", pero eso sustituia los caracteres no ASCII
    # por secuencias de escape... ahora hago el escapado a mano para
    # conservar esos caracteres.
    return str(data).replace('"', '\\"').replace("\n", "\\n")


def _graph_dot(graph, shapedir, scale):
    """Convierte un grafo en un Graph de dot
    
    - shapedir: directorio donde estan los iconos (.png)
    - scale: True si se quiere escalar el grafico a A4
    """
    yield "\n".join((
        "Digraph full {",
        '  charset="UTF-8";',
    ))
    if scale:
        yield '  size = "6.5,9.5" /* a4 en pulgadas, menos el margen */'
    for key, group in graph.groups.iteritems():
        if not key:
            cluster   = None
            pre, post = "", ""
        else:
            cluster   = key.replace(" ", "")
            pre, post = tuple(_group_wrapper(cluster, key))
        yield pre
        for sublist in group:
            for item in _list_dot(sublist, cluster, shapedir):
                yield item
        for sublist in group:
            if sublist.rank is not None:
                yield '  { rank=%s; %s };' % (sublist.rank, "; ".join(str(x.ID) for x in sublist))
        yield post
    IDs = graph.IDs
    for sublist in graph.links:
        for link in sublist.valid_links(IDs):
	    color = sublist.color
            if sublist.style == LINK_DOUBLE:
                color = "%s:white:%s" % (color, color)
            yield '  %s -> %s [ color="%s", penwidth="%s", style="%s", arrowhead="%s", arrowtail="%s" ];' % (
                link[0].ID, link[1].ID, color, sublist.width,
                STYLES.get(sublist.style, "solid"),
                ARROWS.get(sublist.source_arrow, "none"),
                ARROWS.get(sublist.target_arrow, "none"),
            )
    yield "}"


def _group_wrapper(cluster, label):
    """Devuelve la parte inicial y final de un subgraph"""
    yield "\n".join((
        '  Subgraph cluster%s {' % cluster,
        '    margin=0.25;',
        '    label="%s";' % _dot_escape(label),
    ))
    yield "  }"


def _list_dot(sublist, label, shapedir):
    """Crea un cluster dot por cada nodo del NodeList"""
    for item in sublist:
        cluster, shape, border, label = str(item.ID).replace(" ", ""), "", sublist.border, label or ""
        if sublist.shape:
            shape = 'shapefile="%s.png",' % os.path.join(shapedir, sublist.shape)
        yield "\n".join((
            '    Subgraph cluster%s_%s {' % (label, cluster),
            '      center=true;',
            '      margin=0;',
            '      nodesep=0;',
            '      mindist=0;',
            '      pad=0;',
            '      label="%s";' % _dot_escape(item.label),
            '      color=%s;' % border,
            '      %s [shape=box, pad=0, label="", penwidth=0, %s fontname=Calibri, fontsize=10];' % (item.ID, shape),
            '    }'
        ))
