#!/usr/bin/env python
# -*- vim: expandtab tabstop=4 shiftwidth=4 smarttab autoindent


import csv


class DataTokenizer(object):

    """Tokenizer de fichero de datos

    Los ficheros de datos son CSV. Este tokenizer filtra las lineas
    vacias, y separa las otras en los campos que las componen
    """

    def __init__(self, source, comment):
        """Conecta el tokenizer a un flujo de lineas

        Genera los atributos:
            "source": objeto source.
            "lineno": numero de linea, comienza en 0.
        """
        self.source = source
        self.lineno = 0
        self.comment = comment
    
    def tokens(self):
        """Iterador que genera un flujo de tokens"""
        delim  = self._sniff()
        reader = csv.reader(self.source.readlines("rb"), delimiter=delim)
        for record in (self._norm(item) for item in reader):
            if record:
                yield (reader.line_num, record)

    def _norm(self, record):
        if not record or record[0].startswith(self.comment):
            return None
        for item in reversed(record):
            if item and not item.isspace():
                return record
            record.pop()

    def _sniff(self):
        """pa mear y no echar gota

        Resulta que si exportas un excel a csv desde el menu
        "archivo>guardar como", te lo guarda separado por ';'. Pero si
        usas una macro, workSheet.saveAs format:=xlCSV, te lo guarda
        separado por ",". Tocate las narices.
        """
        # lo unico que me interesa es el delimiter, lo demas vale por defecto
        valid = set([',', ';'])
        for line in self.source.readlines():
            if line and line[0] in valid:
                return line[0]
        return ','

