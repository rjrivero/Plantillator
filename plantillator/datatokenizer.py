#!/usr/bin/env python
# -*- vim: expandtab tabstop=4 shiftwidth=4 smarttab autoindent

import csv

from mytokenizer import Tokenizer


class DataTokenizer(Tokenizer):

    """Tokenizer de fichero de datos

    Los ficheros de datos son CSV. Este tokenizer filtra las lineas
    vacias, y separa las otras en los campos que las componen
    """

    def __init__(self, source, comment):
        Tokenizer.__init__(self, source)
        self.comment = comment
    
    def tokens(self):
        """Iterador que genera un flujo de tokens"""
        delim  = self._sniff()
        reader = csv.reader(self.source.readlines("rb"), delimiter=delim)
        for record in (self._norm(item) for item in reader):
            if record:
                self.lineno = reader.line_num
                yield record

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
        crit  = {
            ',': [0, 0, 0],
            ';': [0, 0, 0]
                # primer valor: veces que el caracter es el primero de la linea
                # segundo valor: lineas en las que aparece el caracter
                # tercer valor: numero total de veces que aparece el caracter
        }
        for line in self.source.readlines():
            for char, data in crit.iteritems():
                if line.startswith(char):
                    data[0] += 1
                count = line.count(char)
                if count:
                    data[1] += 1
                    data[2] += count
        for comma_count, semicolon_count in zip(crit[','], crit[';']):
            if comma_count != semicolon_count:
                return "," if comma_count > semicolon_count else ';'
        # si todos los criterios son iguales, solo nos queda devolver
        # un valor cualquiera. Por defecto, escogemos la coma.
        return ","

