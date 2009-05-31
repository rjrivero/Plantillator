#!/usr/bin/env python
# -*- vim: expandtab tabstop=4 shiftwidth=4 smarttab autoindent


from unittest import TestCase


def build_tester(name, cases, case_tester):
    """Crea un TestCase a partir de una lista de casos
    
    utilizando una lista de casos (cases), y una funcion
    quew transforma cada caso en un test (case_tester), crea
    una nueva clase derivada de TestCase con un test por cada
    caso de la lista.  
    """
    def test_iterator():
        for index, data in enumerate(cases):
            yield ("test_%d" % index, case_tester(*data))
    return type(name, (TestCase,), dict(test_iterator()))


