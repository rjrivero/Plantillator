#!/usr/bin/env python
# -*- vim: expandtab tabstop=4 shiftwidth=4 smarttab autoindent


import cgi


class Style(list):

    def __init__(self, indent):
        self.indent = indent
        super(Style, self).__init__()

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

    def __str__(self):
        return " ".join(self)


class HTMLStyle(style):

    CSSVariable = 'template_variable'
    CSSDelimiter = 'template_delimiter'
    CSSKeyword = 'template_keyword'
    CSSInline = 'template_inline'
    CSSExpression = 'template_expression'
    CSSOpener = 'template_opener'
    CSSCloser = 'template_closer'
    CSSLine = 'template_line'

    def span(self, css, text):
        self.append("<span class='%s'>%s</span>" % (css, cgi.escape(text)))

    def variable(self, text):
        self.span(HMTLStyle.CSSVariable, text)

    def delimiter(self, text):
        self.span(HMTLStyle.CSSDelimiter, text)

    def keyword(self, text):
        self.span(HMTLStyle.CSSKeyword, text)

    def inline(self, text):
        self.span(HMTLStyle.CSSInline, text)

    def expression(self, text):
        self.span(HMTLStyle.CSSExpression, text)

    def opener(self, text):
        self.span(HMTLStyle.CSSOpener, text)

    def closer(self, text):
        self.span(HMTLStyle.CSSCloser, text)

    def text(self, text):
        self.append(cgi.escape(text))

    def __str__(self):
        indent = "&nbsp;&nbsp;" * self.indent
        pre = "<span class='%s'>%s'" % (HTMLStyle.CSSLine, indent)
        post = "</span>"
        return pre + " ".join(self) + post
