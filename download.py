import urllib, re, urlparse, htmlentitydefs
from HTMLParser import HTMLParser
import pdb
import optparse, sys

VERBOSE = 0

htmlentitydefs.name2codepoint['nbsp'] = ord(" ")


def get_attr_value(attrs, key):
    for x,y in attrs:
        if x==key:
            return y

class Figure:
    def __init__(self, out_fd, url = ''):
        ## Create a valid filename
        self.src = self.download_drawing(url)
        self.caption = ''
        self.extra = ''
        self.out_fd = out_fd

    def download_drawing(self, url):
        ## If its a google drawing we can just fetch it as pdf
        s = urlparse.urlsplit(url)
        ext = "png"
        if s.netloc == 'docs.google.com' and s.path == "/Drawing":
            q = urlparse.parse_qs(s.query)
            url = "%s://%s/%s?%s" % (s.scheme,
                                     s.netloc,
                                     #"drawings/export/%s" % ext,
                                     "drawings/image",
                                     "id=%s&w=600&h=600&rev=%s&ac=1" % (
                    q['drawingId'][0], q['drawingRev'][0])
                                     )

            filename = "figure_%s_%s.%s" % (q['drawingId'][0], q['drawingRev'][0], ext)
            try:
                fd = open(filename, "r")
            except IOError:
                f = urllib.urlopen(url)
                data = f.read()
                fd = open(filename,"w")
                fd.write(data)
                fd.close()

            return filename

        return re.sub("[:/\&?]","_",url)

    def set_caption(self, caption):
        def update_extra(x):
            self.extra += x.group(0)

        caption = re.sub(r"\\label\{[^\}]+\}", update_extra, caption)
        m = re.search(r"{\\bf(.+)}(.+)",caption)
        if m:
            caption = m.group(1) + m.group(2)

        caption = re.sub(r"(Table|Figure) \d+:",'',caption)

        self.caption = caption

    def end(self):
        self.out_fd.write(r"""\begin{figure}[tb]
\begin{center}
\includegraphics[width=\columnwidth]{%s}
\caption{%s}
%s
\end{center}
\end{figure}
""" % (self.src, self.caption, self.extra))

class Table(Figure):
    name = "table"

    def __init__(self, out_fd, attrs):
        self.columns = []
        self.rows = [[None]]
        self.x = -1
        self.y = -1
        self.attrs = attrs
        Figure.__init__(self, out_fd)

        style=get_attr_value(attrs, "style")
        if style and "font-family:Courier New" in style:
            self.type = "verbatim"
        else:
            self.type = "tabular"

        border = get_attr_value(attrs, "border")
        if border and int(border) > 2:
            self.name = "table*"

    def start_td(self, attrs):
        self.x += 1

        try:
            self.columns[self.x] = 'l'
        except IndexError:
            self.columns.append("l")

        try:
            self.rows[self.y][self.x] = None
        except IndexError:
            self.rows[self.y].append(None) 

        style=get_attr_value(attrs, "style")
        if style and "text-align:right" in style:
            self.columns[self.x] = 'r'

    def end_td(self, attrs):
        #self.x -= 1
        pass

    def end_tr(self, attrs):
        #self.y -= 1
        self.x = -1

    def start_tr(self, attrs):
        self.y += 1

        try:
            self.rows[self.y] = []
        except IndexError:
            self.rows.append([''])

    def data(self, data):
        if self.rows[self.y][self.x] is None:
            self.rows[self.y][self.x] = '' 

        self.rows[self.y][self.x] += data

    def end(self):
        self.out_fd.write(r"""\begin{%s}[tbp]
\caption{%s}
%s
""" % (self.name, self.caption, self.extra))
        if self.type == "tabular":
            self.out_fd.write(r"\begin{tabular}{%s}\hline " % (''.join(self.columns)))
            for y in range(len(self.rows)):
                self.out_fd.write(" & ".join(self.rows[y]) + "\\\\\n")
                if y==0:
                    self.out_fd.write("\\hline\n")

            self.out_fd.write(r"""\hline""")

        else:
            self.out_fd.write(r"""\begin{verbatim}""" + self.rows[0][0])

        self.out_fd.write(r"""\end{%s}
\end{%s}
""" % (self.type, self.name))

class Handler:
    emit = False
    emitter = None
    mode = ['normal']
    biblio_fd = None
    verb = False
    quote_mode = "''"

    def __init__(self, out_fd):
        self.tables = []
        self.para = ''
        self.current_table = None
        self.out_fd = out_fd

    def start_table(self, attrs):
        t = Table(self.out_fd, attrs)
        self.tables.append(t)
        self.emitter = t.data

    def end_table(self, attrs):
        self.current_table = self.tables.pop(-1)
        self.emitter = None

    def start_td(self, attrs):
        self.tables[-1].start_td(attrs)

    def start_tr(self, attrs):
        self.tables[-1].start_tr(attrs)

    def end_td(self, attrs):
        if self.emitter:
            self.emitter(self.para)
        self.tables[-1].end_td(attrs)
        self.para = ''

    def end_tr(self, attrs):
        self.tables[-1].end_tr(attrs)

    def start_b(self, attrs):
        self.para += r"{\bf "

    def end_b(self, attrs):
        self.para += "}"

    def start_i(self, attrs):
        self.para += "{\em "

    def end_i(self, attrs):
        self.para += "}"

    def start_br(self, attrs):
        if self.emit:
            if self.current_table and self.para:
                self.current_table.set_caption(self.para)
                self.current_table.end()
                self.current_table = None
            elif self.emitter:
                self.emitter("\n")
            else:
                self.out_fd.write(self.para)

            self.para = ''

    def end_br(self, attrs): pass

    def end_font(self, attrs): pass

    def start_p(self, attrs):
        self.start_br(attrs)

    def end_p(self, attrs): pass

    def escape_latex_chars(self, data):
        """ Some characters are not allowed in latex modes.

        This needs to become a context aware latex parser.
        """
        def quote(x):
            if self.quote_mode == '``':
                self.quote_mode = "''"
            else:
                self.quote_mode = '``'

            return self.quote_mode

        if self.mode[-1] == 'bibliography' or self.mode[-1] == "verbatim":
            return data

        return re.sub('"', quote, data)

    def data(self, data):
        if self.mode[-1] == 'comment':
            self.para += "\n%%%s" % data

        m = re.search(r"\\bibliography\{([^\}]+)}", data)
        if m:
            self.mode.append("bibliography")
            def bibliography_write(data):
                if not self.biblio_fd:
                    self.biblio_fd = open("%s.bib" % m.group(1),"w")

                self.biblio_fd.write(self.para + data)
                self.para = ''

            self.emitter = bibliography_write
            self.out_fd.write(data)
        else:
            self.para += self.escape_latex_chars(data)
            if self.tables:
                self.tables[-1].data(self.para)
                self.para = ''

    def start_div(self, attrs):
        if get_attr_value(attrs, "id") == "doc-contents":
            self.emit = True
            self.para = ''

    def end_div(self, attrs):
        if get_attr_value(attrs, "id") == "doc-contents":
            self.emit = False

    def start_h1(self, attrs):
        self.para += r"\title{"

    def end_h1(self, attrs):
        self.para += "}\n\n\maketitle\n"

    def start_h2(self, attrs):
        self.para += "\section{"

    def end_h2(self, attrs):
        self.para += "}\n"

    def start_h3(self, attrs):
        self.para += "\subsection{"

    def end_h3(self, attrs):
        self.para += "}\n"

    def start_h4(self, attrs):
        self.para += "\subsubsection{"

    def end_h4(self, attrs):
        self.para += "}\n"

    def start_font(self, attrs):
        face = get_attr_value(attrs, "face").lower()
        if face and "courier new" in face:
            try:
                self.tables[-1].type = "verbatim"
                self.mode.append("verbatim")
            except IndexError:
                self.para += r"\verb|"
                self.verb = True

    def end_font(self, attrs):
        face = get_attr_value(attrs, "face")
        if face and "courier new" in face and self.verb:
            self.verb = False
            self.para += "|"

        if self.mode[-1]=='verbatim':
            self.mode.pop(-1)

    def start_img(self, attrs):
        src = get_attr_value(attrs, "src")
        self.current_table = Figure(self.out_fd, src)

    def start_ol(self, attrs):
        self.para += r"""
\begin{enumerate}
"""
    def end_ol(self,attrs):
        self.para += r"""
\end{enumerate}
"""
    def start_ul(self, attrs):
        self.para += r"""
\begin{itemize}
"""
    def end_ul(self,attrs):
        self.para += r"""
\end{itemize}
"""

    def start_li(self, attrs):
        self.para += r"\item  "

    def end_li(self, attrs):
        self.para += "\n"

    def start_span(self, attrs):
        cls = get_attr_value(attrs, "class")
        if cls and "comment" in cls:
            self.mode.append('comment')

    def end_span(self, attrs):
        if self.mode[-1] == 'comment':
            self.mode.pop(-1)

class MyHTMLParser(HTMLParser):
    ## Tags for a stack
    tags = {}

    def __init__(self, out_fd):
        self.h = Handler(out_fd)
        HTMLParser.__init__(self)
        self.out_fd = out_fd

    def handle_data(self, data):
        self.h.data(data)

    def handle_entityref(self, name):
        self.handle_data(chr(htmlentitydefs.name2codepoint[name]))

    def handle_starttag(self, tag, attrs):
        try:
            getattr(self.h, "start_%s" % tag)(attrs)
        except AttributeError:
            if self.h.emit and VERBOSE:
                print "Encountered the beginning of a %s tag %s" % (tag, attrs)

        try:
            self.tags[tag].append(attrs)
        except KeyError:
            self.tags[tag] = [attrs]

    def handle_endtag(self, tag):
        attrs = self.tags[tag].pop(-1)
        try:
            getattr(self.h, "end_%s" % tag)(attrs)
        except AttributeError:
            if self.h.emit and VERBOSE:
                print "Encountered the end of a %s tag %s" % (tag, attrs)


parser = optparse.OptionParser()
parser.add_option("-o", "--output", default = None,
                  help="write files to FILE (Without extensions)", metavar="FILE")

(options, args) = parser.parse_args()

if options.output:
    out_fd = open("%s.tex" % options.output,"w")
else:
    out_fd = sys.stdout

for arg in args:
    f = urllib.urlopen(arg)
    data = f.read()

    out_fd.write( r"""
    %\documentclass{article}
    \documentclass[12pt, conference]{IEEEtran}
    %\documentclass[doc,helv,longtable,twocolumn]{apa}
    \usepackage{graphicx}
    \usepackage{verbatim}
    \usepackage{cite}
    \bibliographystyle{IEEEtran}

    \begin{document}
    """)

    try:
        p = MyHTMLParser(out_fd)
        p.feed(data)
    except Exception, e:
        print e
        pdb.post_mortem()

    out_fd.write( """\end{document}""")
