#!/usr/bin/env python
#########################################################################
# Ayuda a procesar las ACLs, agrupando puertos por protocolo y numeracion
#
# NOTA: hay que modificarlo para que trabaje directamente con objetos
# IPADDRESS, no con cadenas.
#########################################################################


import re
from cuac.libs.IPy import IP


# Conjunto de digitos al final de una cadena
DIGIT_TAIL_RE = re.compile(r'[^\d]([\d/]+)$')


class Sumarizador(tuple):

    """Tupla que sumariza listas de objetos agregables (IPs, rangos...)"""

    def __new__(cls, items):
        return tuple.__new__(cls, Sumarizador.sumariza_todos(sorted(items)))

    @staticmethod
    def sumariza(items):
        """Hace un pase sobre una lista, agrupando elementos adyacentes.

        La lista debe estar ordenada. Para agrupar dos objetos (x, y)
        consecutivos de la lista, llama a x.agg(y):

          - Si la funcion devuelve un objeto: se considera agregado.
          - Si la funcion devuelve None: los objetos no se pueden agregar.
        """
        prev = items[0]
        for next in items[1:]:
            agg = prev.agg(next)
            if agg:
                prev = agg
            else:
                yield prev
                prev = next
        yield prev

    @staticmethod
    def sumariza_todos(items):
        """Intenta sumarizar/agregar una lista de objetos.

        Recorre la lista tantas veces como sea necesario, sumarizando en
        cada paso los objetos adyacentes, hasta que ya no pueda agregar mas.
        """
        # si solo hay un objeto, no hay nada que agrupar.
        if len(items) <= 1:
            return items
        grouped = tuple(Sumarizador.sumariza(items))
        if len(grouped) == len(items):
            return grouped
        return Sumarizador.sumariza_todos(grouped)


class Generador_ACL(object):

    """Generador que crea las distintas ACEs que componen una ACL.

    Al iterar sobre el objeto, se van generando las ACEs. El iterador
    intenta minimizar el uso de la TCAM, agregando redes contiguas y
    resumiendo puertos para reducir el numero de ACEs necesarias.
    """

    def __init__(self, acl, grupos_red, agg_ips=True, agg_puertos=True):
        """Construye el generador.

        acl: ACL a generar.
        grupos_red: lista para resolver nombres a direcciones IP
        agg_ips: False si no se quiere que sumarice IPs.
        agg_puertos: False si no se quiere que agregue puertos.
        """
        self.acl = acl
        self.grupos_red = grupos_red
        self.agg_ips = agg_ips
        self.agg_puertos = agg_puertos

    class Rango(object):

        """Rango de numeros de puerto TCP / UDP"""

        def __init__(self, puerto):
            puerto = tuple(int(x) for x in puerto.split("-"))
            if len(puerto) == 2:
                self.inicio, self.fin = puerto
            else:
                self.inicio = self.fin = puerto[0]

        def agg(self, other):
            if self.fin >= other.inicio and self.fin <= other.fin:
                return Rango(self.inicio, other.fin)
            return None

        def __cmp__(self, other):
            c = cmp(self.inicio, other.inicio)
            return c if c else cmp(self.fin, other.fin) 

        def __len__(self):
            return self.fin - self.inicio + 1

        def __str__(self):
            if self.fin == self.inicio:
                return " eq %d" % self.inicio
            return " range %d %d" % (self.inicio,  self.fin)

    class GrupoRangos(list):

        def __str__(self):
            return " eq " + " ".join(str(x.inicio) for x in self)

    class Descriptor(object):

        """Describe una parte de la ACE (IP, protocolo, puerto)"""

        def __init__(self, ip, protocolo, puerto=None):
            self.ip = ip
            self.protocolo = protocolo
            self.puerto = puerto

        def compatible(self, otro):
            """Devuelve True si ambos descriptores son del mismo protocolo"""
            return (self.protocolo is None
                    or otro.protocolo is None
                    or self.protocolo == otro.protocolo)

        def __str__(self):
            """Convierte el descriptor en texto"""
            if not self.ip:
                ip = "any"
            else:
                ip = "%s %s" % (self.ip.red, self.ip.wildmask)
            if self.protocolo in ('tcp', 'udp') and self.puerto:
                ip = ip + str(self.puerto)
            return ip

    def ips(self, direccion):
        """Resuelve una direccion a una lista de IPs.

        Si la direccion es "*", devuelve una lista donde el unico
        elemento es None. En otro caso, devuelve una lista de IPs
        asociadas al nombre dado.
        """
        if isinstance(direccion, IP):
            ips = (direccion,)
        elif direccion == "*":
            return (None,)
        else:
            ips = self.grupos_red(nombre=direccion).rango
        return ips if not self.agg_ips else Sumarizador(ips)

    def protocolos(self, puertos):
        """Distribuye la lista de puertos por protocolo"""
        if puertos == "*":
            return {None: None}
        protos = dict()
        for puerto, proto in (x.split("/") for x in LISTA(puertos)):
            protos.setdefault(proto.lower(), []).append(puerto)
        return protos

    def agrega_puertos(self, rangos):
        """Agrega los rangos de puertos"""
        unicos = Generador_ACL.GrupoRangos() if self.agg_puertos else None
        for rango in Sumarizador(rangos):
            if unicos is not None and rango.inicio == rango.fin:
                unicos.append(rango)
            else:
                yield rango
        if unicos:
            yield unicos

    def puertos(self, puertos):
        """Agrupa una lista de puertos por rangos.

        Recibe una cadena de texto que define pares protocolo / puerto
        (por ejemplo: 80/tcp, 53/udp). Lo divide en una secuencia de pares
        (protocolo, lista de puertos).

        Los pruertos son agrupados por protocolos y expresados en forma de
        rango o lista, para minimizar el numero de ACEs necesarias.

        Por ejemplo:
        "80/tcp, 443/tcp, 20-21/tcp, 22/tcp, 53/udp" =>
        => [("tcp", " range 20 22"), ("tcp", " eq 80 443"),
            ("udp", " eq 53")]
        """
        for proto, puertos in self.protocolos(puertos).iteritems():
            if proto in ('tcp', 'udp'):
                puertos = (Generador_ACL.Rango(x) for x in puertos)
                for puerto in self.agrega_puertos(puertos):
                    yield (proto, puerto)
            else:
                yield (proto, None)

    def descriptores(self, regla, attrib_ip, attrib_puerto):
        """Combina una lista de IPs y puertos en descriptores"""
        for ip in self.ips(regla.get(attrib_ip, "*")):
            for proto, puerto in self.puertos(regla.get(attrib_puerto, "*")):
                yield Generador_ACL.Descriptor(ip, proto, puerto)

    def regla(self, regla):
        """Crea las ACEs de una regla"""
        origenes = self.descriptores(regla, "origen", "puerto_origen")
        destinos = self.descriptores(regla, "destino", "puerto_destino")
        orden = regla.orden
        for o, d in ((x, y) for x in origenes for y in destinos
                     if x.compatible(y)):
            proto = o.protocolo or d.protocolo or "ip"
            yield " ".join((str(orden), regla.accion, proto, str(o), str(d)))
            orden = orden + 1

    def __iter__(self):
        """Genera las ACEs de una ACL"""
        for regla in self.acl:
            for ace in self.regla(regla):
                yield ace


def SimplificaInterfaz(nombre_interfaz):
    """Reduce el nombre de una interfaz FastEth o GigabitEth al minimo"""
    nombre = nombre_interfaz.split("#")[0].strip().upper()
    inicial = nombre[0]
    indice = DIGIT_TAIL_RE.search(nombre)
    if indice:
        nombre = inicial + indice.groups()[0]
    return nombre
    
