#!/usb/bin/env python

#########################################################
# Partes de codigo basado en md5crypt.py de Michael Wallace 
# (http://www.sabren.net/code/python/crypt/md5crypt.py)
#
# Nota integra:
#########################################################
# 0423.2000 by michal wallace http://www.sabren.com/
# based on perl's Crypt::PasswdMD5 by Luis Munoz (lem@cantv.net)
# based on /usr/src/libcrypt/crypt.c from FreeBSD 2.2.5-RELEASE
#
# MANY THANKS TO
#
#  Carey Evans - http://home.clear.net.nz/pages/c.evans/
#  Dennis Marti - http://users.starpower.net/marti1/
#
#  For the patches that got this thing working!
#
#########################################################

"""
Utilidad para ofuscar o descifrar passwords utilizando los algoritmos
7 o 5 de Cisco.
"""

from random import randint
from hashlib import md5

# Tabla Vinegere para (des-)ofuscar las claves 7 de Cisco.
XLAT = (
    0x64, 0x73, 0x66, 0x64, 0x3b, 0x6b, 0x66, 0x6f, 0x41, 0x2c, 0x2e,
    0x69, 0x79, 0x65, 0x77, 0x72, 0x6b, 0x6c, 0x64, 0x4a, 0x4b, 0x44,
    0x48, 0x53, 0x55, 0x42, 0x73, 0x67, 0x76, 0x63, 0x61, 0x36, 0x39,
    0x38, 0x33, 0x34, 0x6e, 0x63, 0x78, 0x76, 0x39, 0x38, 0x37, 0x33,
    0x32, 0x35, 0x34, 0x6b, 0x3b, 0x66, 0x67, 0x38, 0x37,
)

# Tabla de conversion a base64
ITOA64 = u"./0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz"

# Longitud maxima de password.
PW_MAX = len(XLAT) - 15


def bytes(stream):
    """Convierte un numero hex (representado como cadena) en bytes"""
    for i in xrange(0, len(stream), 2):
        yield int(stream[i:i+2], 16)


def reveal(pw):
    """Desvela una clave ofuscada con el algoritmo 7 de Cisco"""
    if (len(pw)/2-1) > PW_MAX:
        raise ValueError(pw)
    seed = int(pw[:2], 10)
    if seed < 0 or seed > 15:
        raise ValueError(pw)
    return "".join(chr(a^b) for a, b in zip(bytes(pw[2:]), XLAT[seed:]))


def password(pw, seed=None):
    """Ofusca una clave con el algoritmo 7 de Cisco.
    "seed" debe ser un numero entre 0 y 15 (inclusives).
    """
    if len(pw) > PW_MAX:
        raise ValueError(pw)
    seed = seed % 16 if seed is not None else randint(0, 15)
    data = "".join(u"%02X" % (ord(a)^b) for a, b in zip(pw, XLAT[seed:]))
    return u"%02d%s" % (seed, data)


def to64(stream, chars):
    """Concatena algunos bytes de un stream y los convierte a base64.
    stream: cadena de la que se toman los bytes.
    chars: tupla con los bytes a codificar.
    """
    data = ord(stream[chars[0]])
    for item in chars[1:]:
        data = (data << 8) | ord(stream[item])
    bits = xrange(0, len(chars)*8, 6)
    return "".join(ITOA64[(data >> b) & 0x3F] for b in bits)


def secret(pw, salt=None, magic=u"$1$"):
    """Cifra el password con la salt dada, y MD5"""
    # Validamos la salt.
    if salt is None:
        # usamos una salt de 24 bits
        salt = u"".join(chr(randint(0, 255)) for x in xrange(0, 3))
        salt = to64(salt, (0, 1, 2))
    if len(salt) > 4:
        raise ValueError(salt)
    salt = salt.replace(u"$", u"&")
    # calculamos los valores iniciales
    final = md5(pw + salt + pw).digest()
    ctx = pw + magic + salt
    for pl in range(len(pw), 0, -16):
        ctx = ctx + final[:min(16, pl)]
    # Hacemos la primera transformacion del digest.
    i, zero, pw0 = len(pw), chr(0), pw[0]
    while i:
        ctx = ctx + (zero if i & 1 else pw0)
        i = i >> 1
    final = md5(ctx).digest()
    # Esto es un round raro que debe hacer las cosas mas lentas...
    for i in xrange(1000):
        ctx1 = pw if i & 1 else final
        if i % 3:
            ctx1 = ctx1 + salt
        if i % 7:
            ctx1 = ctx1 + pw
        ctx1 = ctx1 + (final if i & 1 else pw)
        final = md5(ctx1).digest()
    # Y la transformacion final...
    tuples = (
        (0, 6, 12),                            
        (1, 7, 13),                            
        (2, 8, 14),                            
        (3, 9, 15),                            
        (4, 10, 5),
        (11,),
    )
    passwd = "".join(to64(final, x) for x in tuples)                            
    return magic + salt + u'$' + passwd

