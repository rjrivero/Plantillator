#!/usb/bin/env python
#
###########################
# Calcula el hash necesario para configurar un password SNMPv3
# en un SR ALU, en funcion de su engineID.
###########################

import hashlib


def snmpHash(password, engineID, hashProto="sha1", hashlib=hashlib):
    """Calcula el hash de un password SNMPv3 en funcion del engineID.
    
    password: clave SNMP
    engineID: engineID
    hashProto: sha1 | md5
    """
    m, plen = hashlib.new(hashProto), len(password)
    times, rem, update = (1048576 // plen), (1048576 % plen), m.update
    for i in xrange(times):
        update(password)
    update(password[0:rem])
    blockKey = m.digest()
    m = hashlib.new(hashProto)
    m.update(blockKey)
    m.update(engineID.decode('hex'))
    m.update(blockKey)
    return m.hexdigest()
