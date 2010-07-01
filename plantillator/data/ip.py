#!/usr/bin/env python
# -*- vim: expandtab tabstop=4 shiftwidth=4 smarttab autoindent encoding=utf-8


from itertools import chain
from .IPy import IP


BYTES_LIST = ('255','127','63','31','15','7','3','1')
NIBBLES_LIST = (
    'ffff', '7fff', '3fff', '1fff',
    '0fff', '07ff', '03ff', '01ff',
    '00ff', '007f', '003f', '001f',
    '000f', '0007', '0003', '0001',
)


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
        'mascara',      # mascara (texto)
        'red',          # IP de la red (texto)
        'broadcast',    # IP de broadcast de la red (texto)
        'bits',         # numero de bits de la mascara (entero)
        'bitsize',      # numero de bits totales de la direccion
        'wildmask',     # mascara invertida (estilo Cisco)
    ))

    def __init__(self, ip, host=None):
        """Construye un objeto de tipo IP.
        - Si se omite "host", "ip" debe ser una cadena de texto en formato
          "ip / mask".
        - Si no se omite "host", ip debe ser un objeto IPy.IP.
        """
        if host is not None:
            self.host = host
            self.raw_network = ip
        else:
            self._str = ip

    def validate(self):
        """Valida una IP que se ha creado a partir de una cadena de texto"""
        try:
            address, mask = self._str.split('/')
        except ValueError:
            address, mask = self._str, None
        ip = IP(address) 
        self.bitsize = ip.prefixlen()
        masklen = int(mask) if mask is not None else self.bitsize
        self.raw_network = ip.make_net(masklen)
        self.host = ip.int() - self.raw_network.int()
        return self

    def asHost(self):
        """Devuelve un objeto IPAddress con la misma IP y máscara FF...FF"""
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

    def _mascara(self):
        """Mascara de la red en formato texto"""
        return self.raw_network.netmask().strNormal(0)

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
            return self.ip
        return " /".join((self.ip, str(self.bits)))

    def __unicode__(self):
        if self.bits == self.bitsize:
            return unicode(self.ip)
        return u" /".join((self.ip, str(self.bits)))

    def __repr__(self):
        return "IPAddress('%s')" % str(self)

    def __cmp__(self, other):
        # Para listas mixtas de IPs, donde algunos elementos sean
        # una IP como tal, y otros una lista de IPs en formato texto
        # (por ejemplo, [IP("A.B.C.D/a"), "L.M.N.O/b, P.Q.R.S/c"]
        if isinstance(other, basestring):
            return cmp(str(self), other)
        return cmp(self.int, other.int)
