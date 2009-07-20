#!/usr/bin/env python
# -*- vim: expandtab tabstop=4 shiftwidth=4 smarttab autoindent


import os, glob
from unittest import TestCase, main

try:
    from plantillator.data.base import *
except ImportError:
    import sys
    sys.path.append("../../..")
    from plantillator.data.base import *
from plantillator.data.pathfinder import *
from plantillator.data.dataobject import *
from plantillator.data.dataset import *
from plantillator.csvread.source import DataSource
from plantillator.engine.loader import Loader


MenuSource = DataSource()
MenuType   = RootType(MenuSource)
Menu       = MenuType()
MenuSource.read(StringSource("menu",
"""
beverages, color,  alcohol
         , white , no
         , black , no
         , red   , yes
         , yellow, yes

pizzas, title      , type
      , fourcheese , cheese
      , barbacoa   , meat
      , special    , meat

pizzas.toppings, pizza.title, name      , type
              , fourcheese , tomato    , vegetable
              , fourcheese , mozzarella,
              , fourcheese , parmesano ,
              , fourcheese , provolone ,
              , fourcheese , ricota,
              , barbacoa   , tomato    , vegetable
              , barbacoa   , mozzarella, cheese
              , barbacoa   , calf      ,
              , barbacoa   , bbq sauce , sauce
              , special    , tomato    , vegetable
              , special    , mozzarella, cheese
              , special    , olive     , fruit
              , special    , onion     , vegetable
              , special    , calf      ,
              , special    , mushroom  , fungus
"""), Menu)


GLOBALS = {
    "__builtins__": __builtins__,
    "LISTA": asList,
    "RANGO": asRange,
    "GRUPO": asSet,
    "cualquiera": Deferrer(),
    "ninguno": None,
    "ninguna": None,
    "X": Deferrer(),
    "x": Deferrer(),
    "donde": Filter
}


class TestLoader(TestCase):

    def setUp(self):
        self.loader = Loader()


class Test(object):

    def __init__(self, fname, save=False):
        self.fname = fname
        self.save = save

    def do(self, obj):
        source = FileSource(self.fname)
        obj.loader.load(source)
        result = []
        for tmpl in obj.loader:
            result.extend(obj.loader.run(tmpl, GLOBALS, Menu))
        result = "".join(result)
        cfg = os.path.splitext(source.id)[0] + ".cfg"
        if self.save:
            try:
                with open(cfg, "w+") as outfile:
                    outfile.write(result)
            except:
                obj.failIf(True)
        else:
            with open(cfg, "r") as infile:
                obj.failUnless(result == infile.read())

    def __get__(self, obj, cls):
        return lambda: self.do(obj)

           
def MakeTests(save):
    for infile in glob.glob(os.path.join('cases', '*.txt')):
        test = Test(infile, save)
        name = os.path.splitext(os.path.basename(infile))[0]
        setattr(TestLoader, "test_%s" % name, test)


if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1 and sys.argv[1].upper() == "REBUILD":
        answer = raw_input("Are you sure to rebuild the cases [y/n]? ")
        if answer.lower() in ('y', 'ye', 'yes'):
            sys.argv.pop(1)
            MakeTests(True)
    else:
        MakeTests(False)
    main()

