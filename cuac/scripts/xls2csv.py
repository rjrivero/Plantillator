#!/usr/bin/env python

from __future__ import print_function

import sys
try:
	import openpyxl
except ImportError:
	print("ERROR: Debe instalar la libreria openpyxl", file=sys.stderr)
	sys.exit(-1)

def dump_sheet(workSheet):
	for row in workSheet.rows:
		print('"%s"' % '";"'.join((unicode(cell.value).encode('utf-8')
					   if cell.value is not None else '')
					   for cell in row))
	print(";")

if __name__ == "__main__":
	if len(sys.argv) < 2:
		print("Uso: xls2csv.py <fichero xlsx>", file=sys.stderr)
		sys.exit(-2)
	fname = sys.argv[1]
	try:
		wb = openpyxl.load_workbook(fname)
	except:
		print("No se pudo cargar fichero %s" % fname, file=sys.stderr)
		sys.exit(-3)
	for sn in wb.get_sheet_names():
		dump_sheet(wb.get_sheet_by_name(sn))
