#!/usr/bin/env python

"""
Esta libreria tiene como objetivo permitir adaptar el formato
de los peerings en el Ayto. de Sevilla al nuevo modelo de datos,
con PEERs y PeerSets
"""

from cuac.libs.meta import ObjectField
from cuac.libs.fields import IntField


def adapt_peers(from_dset, to_dset, adaptor):
    """Convierte un listado de interfaces en un grupo de PeerSets

    from_dset: Listado de interfaces donde estan los objetos que queremos
            convertir en PEERs.
    to_dset:   Listado de interfaces contra los que pueden ir conectados
    adaptor:   Funcion que encuentra el objeto al que esta conectado una
            interfaz, y le crea un PEER. Se le invoca con tres parametros:
                - El meta del objeto PEER.
                - El item que estamos conviritiendo en peer.
                - La lista de posibles remotos (to_dset)
    """
    for meta in (from_dset._meta, to_dset._meta):
        if "POSITION" not in meta.fields:
            meta.fields["POSITION"] = IntField(indexable=False)
        if "PEER" not in meta.fields:
            meta.fields["PEER"] = ObjectField()
    meta = to_dset._meta
    for item in from_dset:
        if item.get("POSITION") is not None:
            continue
        item.POSITION = 0
        peer = adaptor(meta, item, to_dset)
        if peer:
            peer.POSITION = 1
            item.PEER = peer
            peer.PEER = item
