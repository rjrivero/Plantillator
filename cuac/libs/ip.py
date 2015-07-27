#!/usr/bin/env python
# -*- vim: expandtab tabstop=4 shiftwidth=4 smarttab autoindent encoding=utf-8


import socket, array

from itertools import chain
from cuac.libs.IPy import IP


BYTES_LIST = ('255','127','63','31','15','7','3','1')
NIBBLES_LIST = (
    'ffff', '7fff', '3fff', '1fff',
    '0fff', '07ff', '03ff', '01ff',
    '00ff', '007f', '003f', '001f',
    '000f', '0007', '0003', '0001',
)


def simple_check_ip(ip, socket=socket):
    """Trata de validar si una cadena representa una IP"""
    try:
        ip, mask = tuple(x.strip() for x in ip.split("/"))
        if ":" in ip:
            af, ml = socket.AF_INET6, 128
        else:
            af, ml = socket.AF_INET, 32
        socket.getaddrinfo(ip, None, af, 0, 0, socket.AI_NUMERICHOST)
        assert(int(mask) <= ml)
    except (socket.error, AssertionError):
        raise ValueError(ip)


class IPAddress(object):

    WILDMASK_IPV4 = tuple(chain(
        ("%s.255.255.255" % a for a in BYTES_LIST),
        ("0.%s.255.255" % a for a in BYTES_LIST),
        ("0.0.%s.255" % a for a in BYTES_LIST),
        ("0.0.0.%s" % a for a in BYTES_LIST),
        ("0.0.0.0",)))

    WILDMASK_IPV6 = tuple(chain(
        ("%s:ffff:ffff:ffff:ffff:ffff:ffff:ffff" % a for a in NIBBLES_LIST),
        ("::%s:ffff:ffff:ffff:ffff:ffff:ffff" % a for a in NIBBLES_LIST),
        ("::%s:ffff:ffff:ffff:ffff:ffff" % a for a in NIBBLES_LIST),
        ("::%s:ffff:ffff:ffff:ffff" % a for a in NIBBLES_LIST),
        ("::%s:ffff:ffff:ffff" % a for a in NIBBLES_LIST),
        ("::%s:ffff:ffff" % a for a in NIBBLES_LIST),
        ("::%s:ffff" % a for a in NIBBLES_LIST),
        ("::%s" % a for a in NIBBLES_LIST),
        ("::0",)))

    ATTRIBS = set((
        'raw_network',  # el objeto IPy.IP que representa a la red
        'host',         # el numero de host dentro de la red
        'base',         # objeto IPAddress con la misma red y host 0
        'int',          # direccion IP como un entero
        'ip',           # IP (texto)
        'mask',         # mascara (texto)
        'network',	# IP de la red (texto)
        'bitmask',      # mascara (bits)
        'broadcast',    # IP de broadcast de la red (texto)
        'bits',         # numero de bits de la mascara (entero)
        'bitsize',      # numero de bits totales de la direccion
        'wildmask',     # mascara invertida (estilo Cisco)
        'bytes',        # bytes que componen la direccion (LSB first)
        'hash',         # hash interno de la direccion (para dict, set)
        'red',          # IP de la red (texto) (backward comp)
        'mascara',      # mascara (texto) (backward comp.)
    ))

    def __init__(self, ip, host=None, check_ip=simple_check_ip):
        """Construye un objeto de tipo IP.
        - Si se omite "host", "ip" debe ser una cadena de texto en formato
          "ip / mask".
        - Si no se omite "host", ip debe ser un objeto IPy.IP.
        """
        if host is not None:
            self.host = host
            self.raw_network = ip
        else:
            check_ip(ip)
            self._str = ip
            # el validate tarda MUCHISIMO, prefiero hacer una comprobacion
            # con socket.inet_pton y dejar validate() para tiempo
            # de ejecucion... si no, se me va la carga de los CSVs a un monton
            # de tiempo.
            # self.validate()

    def v6(self, prefix):
        """Devuelve una direccion IPv6 generada a partir de esta IPv4.

        Para eso, pasa a 8 digitos hexadecimales los 32 bits de la direccion
        IPv4, y los concatena con el prefijo definido. La mascara es la
        correspondiente a la que tuviera la direccion IPv4, es decir,
        (128-32+self.bits)

        Por ejemplo, IPAddress(10.0.0.1/8).v6("FEC0::") == FEC0::1200:0001/104
        """
        assert(self.bitsize == 32)
        hi, lo = (self.int >> 16) & 0x0FFFF, (self.int) & 0x0FFFF
        return IPAddress("%s%04X:%04X /%s" % (prefix, hi, lo, 96+self.bits))

    def validate(self):
        """Valida una IP que se ha creado a partir de una cadena de texto"""
        try:
            address, mask = tuple(x.strip() for x in self._str.split('/'))
        except ValueError:
            address, mask = self._str.strip(), None
        ip = IP(address) 
        self.bitsize = ip.prefixlen()
        masklen = int(mask) if mask is not None else self.bitsize
        self.raw_network = ip.make_net(masklen)
        self.host = ip.int() - self.raw_network.int()
        return self

    def asHost(self):
        """Devuelve un objeto IPAddress con la misma IP y mascara FF...FF"""
        return IPAddress(self.raw_network[self.host], 0)

    def agg(self, other):
        """Trata de agregar dos objetos de red"""
        if self.host == 0 and other.host == 0 and self.bits == other.bits:
            offs = self.bitsize - self.bits + 1
            sb = self.raw_network.int() >> offs
            ob = other.raw_network.int() >> offs
            if sb == ob:
                return IPAddress(IP(sb << offs).make_net(self.bits-1), 0)
        return None

    def _raw_network(self):
        """Objeto IPy.IP que representa la red"""
        return self.validate().raw_network

    def _host(self):
        """Numero de host dentro de la red"""
        return self.validate().host

    def _bitsize(self):
        """Longitud de la direccion, en bits"""
        return 32 if self.raw_network.version() == 4 else 128

    def _base(self):
        """Objeto IPAddress que representa la red"""
        return IPAddress(self.raw_network, 0)

    def _int(self):
        """Direccion IP como un numero entero"""
        return self.raw_network.int() + self.host

    def _ip(self):
        """Direccion IP en formato texto"""
        return self.raw_network[self.host].strNormal(0)

    def _mask(self):
        """Mascara de la red en formato texto"""
        return self.raw_network.netmask().strNormal(0)

    def _mascara(self):
        """Mascara de la red en formato texto"""
        return self.raw_network.netmask().strNormal(0)

    def _bitmask(self):
        """Mascara de la red en formato binario"""
        return self.raw_network.netmask().int()

    def _network(self):
        """Direccion de la red en formato texto"""
        return self.raw_network.strNormal(0)

    def _red(self):
        """Direccion de la red en formato texto"""
        return self.raw_network.strNormal(0)

    def _bits(self):
        """Bits de la mascara"""
        return self.raw_network.prefixlen()

    def _broadcast(self):
        """Direccion de broadcast"""
        return self.raw_network.broadcast.strNormal(0)

    def _wildmask(self):
        """Mascara invertida, estilo ACL Cisco"""
        if self.raw_network.version() == 4:
            masks = IPAddress.WILDMASK_IPV4
        else:
            masks = IPAddress.WILDMASK_IPV6
        return masks[self.bits]

    def _bytes(self):
        """Bytes que forman la direccion IP (LSB first)"""
        def stream(num, bitsize):
            for index in xrange(bitsize>>3):
                yield (num & 0x00FF)
                num = num >> 8
        return array.array("B", stream(self.int, self.bitsize))

    def _hash(self):
        """Hash unico del objeto, para indexar en mapas"""
        return hash(self.int)

    def __getattr__(self, attr):
        if attr not in IPAddress.ATTRIBS: 
            raise AttributeError(attr)
        result = getattr(IPAddress, "_%s" % attr)(self)
        setattr(self, attr, result)
        return result

    def __add__(self, num):
        return IPAddress(self.raw_network, self.host + num)

    def __str__(self):
        if self.bits == self.bitsize:
            return str(self.ip)
        return " /".join((str(self.ip), str(self.bits)))

    def __repr__(self):
        return "IPAddress('%s')" % str(self)

    def __contains__(self, other):
        if self.bits > other.bits:
            return False
        if self.host:
            return self.int == other.int
        return (self.int == other.int & self.bitmask)

    def __hash__(self):
      return self.hash

    def __cmp__(self, other):
        # Para listas mixtas de IPs, donde algunos elementos sean
        # una IP como tal, y otros una lista de IPs en formato texto
        # (por ejemplo, [IP("A.B.C.D/a"), "L.M.N.O/b, P.Q.R.S/c"]
        if isinstance(other, basestring):
            if "/" in other:
                return cmp(str(self), other)
            return cmp(self.ip, other)
        return cmp(self.int, other.int)

    def __div__(self, mask):
        # Devuelve un objeto IPAddress com la mascara cambiada
        # ejemplo: IP('1.2.3.4/32') / 24 ==> IP('1.2.3.4/24')
        return IPAddress('/'.join((self.ip, str(mask))))

    def __len__(self):
        # Para que funcionen las comparaciones con ANY, NONE.
        return 1
