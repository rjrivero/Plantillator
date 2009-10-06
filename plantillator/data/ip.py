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

    ATTRIBS = set(('base', 'host', 'ip', 'mascara', 'red', 'bits', 'wildmask'))

    def __init__(self, ip, host=None):
        """Construye un objeto de tipo IP.
        - Si se omite "host", "ip" debe ser una cadena de texto en formato
          "ip / mask".
        - Si no se omite "host", ip debe ser un objeto IPy.IP.
        """
        if host is not None:
            self.base = ip
            self.host = host
        else:
            self._str = ip

    def validate(self):
        try:
            address, mask = self._str.split('/')
        except IndexError:
            address, mask = self._str, None
        ip = IP(address) 
        masklen = int(mask) if mask is not None else ip.prefixlen()
        self.base = ip.make_net(masklen)
        self.host = ip.int() - self.base.int()
        return self

    def _base(self):
        return self.validate().base

    def _host(self):
        return self.validate().host

    def _ip(self):
        return self.base[self.host].strNormal(0)

    def _mascara(self):
        return self.base.netmask()

    def _red(self):
        return IPAddress(self.base, 0)

    def _bits(self):
        return self.base.prefixlen()

    def _wildmask(self):
        if self.base.version() == 4:
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
        return IPAddress(self.base, self.host + num)

    def __str__(self):
        return " /".join((self.ip, str(self.bits)))

    def __unicode__(self):
        return u" /".join((self.ip, str(self.bits)))

    def __repr__(self):
        return "IPAddress('%s')" % str(self)

    def __cmp__(self, other):
        result = cmp(self.base, other.base)
        if not result:
            result = cmp(self.host, other.host)
        return result

