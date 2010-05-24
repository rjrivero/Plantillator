#!/usr/bin/env python
# -*- vim: expandtab tabstop=4 shiftwidth=4 smarttab autoindent


import cgi
from contextlib import contextmanager

try:
    from pygments import highlight
    from pygments.lexers import PythonLexer
    from pygments.formatters import HtmlFormatter
except ImportError:
    pass


class Style(object):

    def __init__(self, indent):
        self.indent = indent
        self.items  = list()
        super(Style, self).__init__()

    def append(self, item):
        self.items.append(item)

    def __iter__(self):
        return iter(self.items)

    def variable(self, text):
        self.append(text)

    def delimiter(self, text):
        self.append(text)

    def keyword(self, text):
        self.append(text)

    def inline(self, text):
        self.append(text)

    def expression(self, text):
        self.append(text)

    def text(self, text):
        self.append(text)

    def opener(self, text):
        self.append(text)

    def closer(self, text):
        self.append(text)

    def comment(self, text):
        self.append(text)

    @contextmanager
    def block(self):
        """Agrupa una serie de items en un bloque.

        Los elementos de un bloque se asume que son tokens, y se
        inserta espacio en blanco entre ellos.

        Los elementos que no estan en un bloque se consideran texto normal
        y no se les inserta espacio en blanco.
        """
        self._openblock()
        backup = self.items
        self.items = list()
        yield
        backup.append(" ".join(self.items))
        self.items = backup
        self._closeblock()

    def _openblock(self):
        pass

    def _closeblock(self):
        pass

    def __str__(self):
        return " ".join(self)


HTML_STYLES = """
.highlight .hll { background-color: white; }
.highlight  { background-color: white; }
.highlight .block { background-color: white; }
.highlight .i {  color: orange; } /* inlined expr */
.highlight .d {  color: orange; } /* delimiter */
.highlight .c {  color: #408080; font-style: italic } /* Comment */
.highlight .err {  border: 1px solid #FF0000 } /* Error */
.highlight .k {  color: #008000; font-weight: bold } /* Keyword */
.highlight .o {  color: #666666 } /* Operator */
.highlight .cm {  color: #408080; font-style: italic } /* Comment.Multiline */
.highlight .cp {  color: #BC7A00 } /* Comment.Preproc */
.highlight .c1 {  color: #408080; font-style: italic } /* Comment.Single */
.highlight .cs {  color: #408080; font-style: italic } /* Comment.Special */
.highlight .gd {  color: #A00000 } /* Generic.Deleted */
.highlight .ge {  font-style: italic } /* Generic.Emph */
.highlight .gr {  color: #FF0000 } /* Generic.Error */
.highlight .gh {  color: #000080; font-weight: bold } /* Generic.Heading */
.highlight .gi {  color: #00A000 } /* Generic.Inserted */
.highlight .go {  color: #808080 } /* Generic.Output */
.highlight .gp {  color: #000080; font-weight: bold } /* Generic.Prompt */
.highlight .gs {  font-weight: bold } /* Generic.Strong */
.highlight .gu {  color: #800080; font-weight: bold } /* Generic.Subheading */
.highlight .gt {  color: #0040D0 } /* Generic.Traceback */
.highlight .kc {  color: #008000; font-weight: bold } /* Keyword.Constant */
.highlight .kd {  color: #008000; font-weight: bold } /* Keyword.Declaration */
.highlight .kn {  color: #008000; font-weight: bold } /* Keyword.Namespace */
.highlight .kp {  color: #008000 } /* Keyword.Pseudo */
.highlight .kr {  color: #008000; font-weight: bold } /* Keyword.Reserved */
.highlight .kt {  color: #B00040 } /* Keyword.Type */
.highlight .m {  color: #666666 } /* Literal.Number */
.highlight .s {  color: #BA2121 } /* Literal.String */
.highlight .n {  color: #19177C } /* Name.Variable */
.highlight .na {  color: #7D9029 } /* Name.Attribute */
.highlight .nb {  color: #008000 } /* Name.Builtin */
.highlight .nc {  color: #0000FF; font-weight: bold } /* Name.Class */
.highlight .no {  color: #880000 } /* Name.Constant */
.highlight .nd {  color: #AA22FF } /* Name.Decorator */
.highlight .ni {  color: #999999; font-weight: bold } /* Name.Entity */
.highlight .ne {  color: #D2413A; font-weight: bold } /* Name.Exception */
.highlight .nf {  color: #0000FF } /* Name.Function */
.highlight .nl {  color: #A0A000 } /* Name.Label */
.highlight .nn {  color: #0000FF; font-weight: bold } /* Name.Namespace */
.highlight .nt {  color: #008000; font-weight: bold } /* Name.Tag */
.highlight .nv {  color: #19177C } /* Name.Variable */
.highlight .ow {  color: #AA22FF; font-weight: bold } /* Operator.Word */
.highlight .w {  color: #bbbbbb } /* Text.Whitespace */
.highlight .mf {  color: #666666 } /* Literal.Number.Float */
.highlight .mh {  color: #666666 } /* Literal.Number.Hex */
.highlight .mi {  color: #666666 } /* Literal.Number.Integer */
.highlight .mo {  color: #666666 } /* Literal.Number.Oct */
.highlight .sb {  color: #BA2121 } /* Literal.String.Backtick */
.highlight .sc {  color: #BA2121 } /* Literal.String.Char */
.highlight .sd {  color: #BA2121; font-style: italic } /* Literal.String.Doc */
.highlight .s2 {  color: #BA2121 } /* Literal.String.Double */
.highlight .se {  color: #BB6622; font-weight: bold } /* Literal.String.Escape */
.highlight .sh {  color: #BA2121 } /* Literal.String.Heredoc */
.highlight .si {  color: #BB6688; font-weight: bold } /* Literal.String.Interpol */
.highlight .sx {  color: #008000 } /* Literal.String.Other */
.highlight .sr {  color: #BB6688 } /* Literal.String.Regex */
.highlight .s1 {  color: #BA2121 } /* Literal.String.Single */
.highlight .ss {  color: #19177C } /* Literal.String.Symbol */
.highlight .bp {  color: #008000 } /* Name.Builtin.Pseudo */
.highlight .vc {  color: #19177C } /* Name.Variable.Class */
.highlight .vg {  color: #19177C } /* Name.Variable.Global */
.highlight .vi {  color: #19177C } /* Name.Variable.Instance */
.highlight .il {  color: #666666 } /* Literal.Number.Integer.Long */
"""

class HTMLStyle(Style):

    CSSLine = 'highlight'
    CSSVariable = 'nv'
    CSSDelimiter = 'd'
    CSSKeyword = 'k'
    CSSInline = 'i'
    CSSExpression = 'nv'
    CSSOpener = 'ow'
    CSSCloser = 'ow'
    CSSComment = 'c'
    CSSBlock = 'block'

    def span(self, css, text):
        self.append("<span class='%s'>%s</span>" % (css, cgi.escape(text) or "&nbsp;"))

    def pygment(self, css, text):
        try:
            self.append(highlight(str(text), PythonLexer(), HtmlFormatter(nowrap=True)))
        except NameError:
            self.span(css, text)

    def variable(self, text):
        self.span(HTMLStyle.CSSVariable, text)

    def delimiter(self, text):
        self.span(HTMLStyle.CSSDelimiter, text)

    def keyword(self, text):
        self.span(HTMLStyle.CSSKeyword, text)

    def inline(self, text):
        self.span(HTMLStyle.CSSInline, text)

    def expression(self, text):
        self.pygment(HTMLStyle.CSSExpression, text)

    def opener(self, text):
        self.span(HTMLStyle.CSSOpener, text)

    def closer(self, text):
        self.span(HTMLStyle.CSSCloser, text)

    def text(self, text):
        self.append(cgi.escape(text))

    def comment(self, text):
        self.span(HTMLStyle.CSSComment, text)

    def _openblock(self):
        self.append("<span class='%s'>" % HTMLStyle.CSSBlock)

    def _closeblock(self):
        self.append("</span>")

    @staticmethod
    def css():
        return HTML_STYLES

    def __str__(self):
        indent = "&nbsp;&nbsp;" * self.indent
        pre = "<div class='%s'>%s" % (HTMLStyle.CSSLine, indent)
        post = "</div>\n"
        return pre + "".join(self) + post
