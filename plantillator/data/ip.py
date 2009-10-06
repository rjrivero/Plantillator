#!/usr/bin/env python
# -*- vim: expandtab tabstop=4 shiftwidth=4 smarttab autoindent encoding=utf-8


from itertools import chain
from IPy import IP


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
        'ip',           # IP (texto)
        'mascara',      # mascara (texto)
        'red',          # IP de la red (texto)
        'bits',         # numero de bits de la mascara (entero)
        'wildmask'      # mascara invertida (estilo Cisco)
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
        try:
            address, mask = self._str.split('/')
        except IndexError:
            address, mask = self._str, None
        ip = IP(address) 
        masklen = int(mask) if mask is not None else ip.prefixlen()
        self.raw_network = ip.make_net(masklen)
        self.host = ip.int() - self.raw_network.int()
        return self

    def _raw_network(self):
        return self.validate().raw_network

    def _host(self):
        return self.validate().host

    def _base(self):
        return IPAddress(self.raw_network, 0)

    def _ip(self):
        return self.raw_network[self.host].strNormal(0)

    def _mascara(self):
        return self.raw_network.netmask().strNormal(0)

    def _red(self):
        return self.raw_network.strNormal(0)

    def _bits(self):
        return self.raw_network.prefixlen()

    def _wildmask(self):
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
        return " /".join((self.ip, str(self.bits)))

    def __unicode__(self):
        return u" /".join((self.ip, str(self.bits)))

    def __repr__(self):
        return "IPAddress('%s')" % str(self)

    def __cmp__(self, other):
        result = cmp(self.raw_network, other.raw_network)
        if not result:
            result = cmp(self.host, other.host)
        return result
