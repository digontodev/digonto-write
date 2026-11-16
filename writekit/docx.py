"""DOCX reader and writer for QTextDocument (zip + XML only)."""
import base64
import io
import os
import re
import zipfile
from xml.etree import ElementTree as ET
from xml.sax.saxutils import escape

from PySide6.QtCore import QBuffer, QByteArray, QIODevice, QSizeF, Qt, QUrl
from PySide6.QtGui import (QColor, QFont, QImage, QTextBlockFormat, QTextCharFormat, QTextCursor, QTextDocument, QTextFormat, QTextFrameFormat, QTextImageFormat,
                           QTextLength, QTextList, QTextListFormat, QTextTableCellFormat, QTextTableFormat)

from . import common as K

W = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
R = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
WP = "http://schemas.openxmlformats.org/drawingml/2006/wordprocessingDrawing"
A = "http://schemas.openxmlformats.org/drawingml/2006/main"
PIC = "http://schemas.openxmlformats.org/drawingml/2006/picture"
NSMAP = f'xmlns:w="{W}" xmlns:r="{R}" xmlns:wp="{WP}" xmlns:a="{A}" xmlns:pic="{PIC}"'


def w(tag):
    return "{%s}%s" % (W, tag)


def x(s):
    return escape(str(s), {'"': "&quot;"})


# ======================================================================= writer
LIST_FMT = {QTextListFormat.ListDisc: ("bullet", "", "Symbol"), QTextListFormat.ListCircle: ("bullet", "o", "Courier New"),
            QTextListFormat.ListSquare: ("bullet", "", "Wingdings"), QTextListFormat.ListDecimal: ("decimal", "%{n}.", None),
            QTextListFormat.ListLowerAlpha: ("lowerLetter", "%{n}.", None), QTextListFormat.ListUpperAlpha: ("upperLetter", "%{n}.", None),
            QTextListFormat.ListLowerRoman: ("lowerRoman", "%{n}.", None), QTextListFormat.ListUpperRoman: ("upperRoman", "%{n}.", None)}


class Writer:
    def __init__(self, doc, page, meta):
        self.doc, self.page, self.meta = doc, page, meta or {}
        self.rels = []          # (id, type, target, external)
        self.media = []         # (name, bytes)
        self.lists = {}         # id(list) -> numId
        self.list_styles = {}   # style -> abstractNumId
        self.nums = []          # (numId, abstractId)
        self.img_n = 0
        self.link_ids = {}
        self.dpi = K.dpi()

    def rel(self, typ, target, external=False):
        rid = f"rId{len(self.rels) + 10}"
        self.rels.append((rid, typ, target, external))
        return rid

    # ---- runs
    def run_props(self, f, extra=""):
        p = []
        fam = ""
        if f.hasProperty(QTextFormat.FontFamilies):
            v = f.property(QTextFormat.FontFamilies)
            if isinstance(v, (list, tuple)) and v:
                fam = str(v[0])
            elif isinstance(v, str):
                fam = v
        elif f.hasProperty(QTextFormat.FontFamily):
            fam = str(f.property(QTextFormat.FontFamily) or "")
        if fam and fam != K.BODY_FAMILIES[0] and fam.lower() != "calibri":
            p.append(f'<w:rFonts w:ascii="{x(fam)}" w:hAnsi="{x(fam)}" w:cs="{x(fam)}" w:eastAsia="{x(fam)}"/>')
        if f.fontWeight() >= 600:
            p.append("<w:b/><w:bCs/>")
        if f.fontItalic():
            p.append("<w:i/><w:iCs/>")
        if f.fontStrikeOut():
            p.append("<w:strike/>")
        fg = f.foreground()
        if fg.style() != Qt.NoBrush:
            col = QColor(fg.color())
            if col.isValid() and col.name().upper() != "#000000":
                p.append(f'<w:color w:val="{col.name()[1:].upper()}"/>')
        sz = f.fontPointSize()
        if sz > 0:
            p.append(f'<w:sz w:val="{int(round(sz * 2))}"/><w:szCs w:val="{int(round(sz * 2))}"/>')
        bg = f.background()
        if bg.style() != Qt.NoBrush:
            col = QColor(bg.color())
            if col.isValid():
                p.append(f'<w:shd w:val="clear" w:color="auto" w:fill="{col.name()[1:].upper()}"/>')
        if f.fontUnderline() or (f.isAnchor() and f.anchorHref()):
            p.append('<w:u w:val="single"/>')
        va = f.verticalAlignment()
        if va == QTextCharFormat.AlignSuperScript:
            p.append('<w:vertAlign w:val="superscript"/>')
        elif va == QTextCharFormat.AlignSubScript:
            p.append('<w:vertAlign w:val="subscript"/>')
        return ("<w:rPr>" + "".join(p) + extra + "</w:rPr>") if (p or extra) else ""

    def text_run(self, text, f):
        out = []
        parts = re.split(r"( |\t|\n)", text)
        rpr = self.run_props(f)
        for part in parts:
            if part == "":
                continue
            if part in (" ", "\n"):
                out.append(f"<w:r>{rpr}<w:br/></w:r>")
            elif part == "\t":
                out.append(f"<w:r>{rpr}<w:tab/></w:r>")
            else:
                out.append(f'<w:r>{rpr}<w:t xml:space="preserve">{x(part)}</w:t></w:r>')
        return "".join(out)

    def image_run(self, fmt):
        name = fmt.name()
        img = self.doc.resource(QTextDocument.ImageResource, QUrl(name))
        qi = None
        if isinstance(img, QImage):
            qi = img
        elif img is not None and not isinstance(img, (int, float, str)) and hasattr(img, "isNull"):
            try:
                qi = QImage(img)
            except Exception:
                qi = None
        if qi is None or qi.isNull():
            qi = QImage(name.replace("file://", ""))
        if qi.isNull():
            return ""
        buf = QBuffer()
        buf.open(QIODevice.WriteOnly)
        qi.save(buf, "PNG")
        data = bytes(buf.data())
        self.img_n += 1
        fname = f"image{self.img_n}.png"
        self.media.append((fname, data))
        rid = self.rel("http://schemas.openxmlformats.org/officeDocument/2006/relationships/image", "media/" + fname)
        wpx = fmt.width() if fmt.width() > 0 else qi.width() * self.dpi / 96
        hpx = fmt.height() if fmt.height() > 0 else wpx * qi.height() / max(1, qi.width())
        cx, cy = K.px_emu(wpx), K.px_emu(hpx)
        return (f'<w:r><w:drawing><wp:inline distT="0" distB="0" distL="0" distR="0"><wp:extent cx="{cx}" cy="{cy}"/><wp:docPr id="{self.img_n}" name="Picture {self.img_n}"/>'
                f'<a:graphic><a:graphicData uri="{PIC}"><pic:pic><pic:nvPicPr><pic:cNvPr id="{self.img_n}" name="{fname}"/><pic:cNvPicPr/></pic:nvPicPr>'
                f'<pic:blipFill><a:blip r:embed="{rid}"/><a:stretch><a:fillRect/></a:stretch></pic:blipFill>'
                f'<pic:spPr><a:xfrm><a:off x="0" y="0"/><a:ext cx="{cx}" cy="{cy}"/></a:xfrm><a:prstGeom prst="rect"><a:avLst/></a:prstGeom></pic:spPr></pic:pic></a:graphicData></a:graphic></wp:inline></w:drawing></w:r>')

    # ---- paragraphs
    def num_for(self, lst):
        key = lst.item(0).position()
        if key in self.lists:
            return self.lists[key]
        fmt = lst.format()
        style = fmt.style()
        if style not in self.list_styles:
            self.list_styles[style] = len(self.list_styles) + 1
        nid = len(self.nums) + 1
        self.nums.append((nid, self.list_styles[style]))
        self.lists[key] = nid
        return nid

    def paragraph(self, block, in_cell=False):
        bf = block.blockFormat()
        ppr = []
        style = K.block_style_name(bf)
        if style != "Normal":
            ppr.append(f'<w:pStyle w:val="{K.STYLE_IDS[style]}"/>')
        lst = block.textList()
        if lst is not None:
            lvl = max(0, min(8, lst.format().indent() - 1))
            ppr.append(f'<w:numPr><w:ilvl w:val="{lvl}"/><w:numId w:val="{self.num_for(lst)}"/></w:numPr>')
        if bf.pageBreakPolicy() == QTextFormat_PageBreakPolicy():
            ppr.append("<w:pageBreakBefore/>")
        top, bottom = bf.topMargin(), bf.bottomMargin()
        sp = f'<w:spacing w:before="{K.px_tw(top)}" w:after="{K.px_tw(bottom)}"'
        if bf.lineHeightType() == QTextBlockFormat.ProportionalHeight and bf.lineHeight() > 0:
            sp += f' w:line="{int(bf.lineHeight() / 100 * 240)}" w:lineRule="auto"'
        elif bf.lineHeightType() in (QTextBlockFormat.FixedHeight, QTextBlockFormat.LineHeightTypes.MinimumHeight.value) and bf.lineHeight() > 0:
            sp += f' w:line="{K.px_tw(bf.lineHeight())}" w:lineRule="{"exact" if bf.lineHeightType() == QTextBlockFormat.FixedHeight else "atLeast"}"'
        ppr.append(sp + "/>")
        left, right, first = bf.leftMargin(), bf.rightMargin(), bf.textIndent()
        if lst is None and (left or right or first):
            ind = f'<w:ind w:left="{K.px_tw(left)}" w:right="{K.px_tw(right)}"'
            if first > 0:
                ind += f' w:firstLine="{K.px_tw(first)}"'
            elif first < 0:
                ind += f' w:hanging="{K.px_tw(-first)}"'
            ppr.append(ind + "/>")
        if bf.layoutDirection() == Qt.RightToLeft:
            ppr.append("<w:bidi/>")
        al = bf.alignment()
        jc = "both" if al & Qt.AlignJustify else "center" if al & Qt.AlignHCenter else "right" if (al & Qt.AlignRight) else None
        if jc:
            ppr.append(f'<w:jc w:val="{jc}"/>')
        if bf.background().style() != Qt.NoBrush and style != "Code":
            ppr.append(f'<w:shd w:val="clear" w:color="auto" w:fill="{bf.background().color().name()[1:].upper()}"/>')
        runs = []
        it = block.begin()
        link = None
        link_runs = []

        def flush():
            nonlocal link, link_runs
            if link is not None and link_runs:
                href = link
                if href.startswith("#"):
                    runs.append(f'<w:hyperlink w:anchor="{x(href[1:])}">{"".join(link_runs)}</w:hyperlink>')
                else:
                    rid = self.link_ids.get(href) or self.rel("http://schemas.openxmlformats.org/officeDocument/2006/relationships/hyperlink", href, True)
                    self.link_ids[href] = rid
                    runs.append(f'<w:hyperlink r:id="{rid}">{"".join(link_runs)}</w:hyperlink>')
            elif link_runs:
                runs.extend(link_runs)
            link, link_runs = None, []
        while not it.atEnd():
            fr = it.fragment()
            it += 1
            f = fr.charFormat()
            href = f.anchorHref() if f.isAnchor() else None
            if href != link:
                flush()
                link = href
            if f.isImageFormat():
                link_runs.append(self.image_run(f.toImageFormat()))
            else:
                t = fr.text()
                if t:
                    link_runs.append(self.text_run(t, f))
        flush()
        return f'<w:p><w:pPr>{"".join(ppr)}</w:pPr>{"".join(runs)}</w:p>'

    def container(self, it):
        out = []
        while not it.atEnd():
            fr = it.currentFrame()
            b = it.currentBlock()
            if fr is not None and hasattr(fr, "rows") and hasattr(fr, "cellAt"):
                out.append(self.table(fr))
            elif b.isValid():
                out.append(self.paragraph(b))
            it += 1
        return "".join(out)

    def table(self, t):
        fmt = t.format()
        rows, cols = t.rows(), t.columns()
        pw, _ = self.page.content_px()
        widths = []
        cons = fmt.columnWidthConstraints()
        for c in range(cols):
            if c < len(cons) and cons[c].type() == QTextLength.PercentageLength:
                widths.append(int(cons[c].rawValue() / 100 * pw))
            elif c < len(cons) and cons[c].type() == QTextLength.FixedLength:
                widths.append(int(cons[c].rawValue()))
            else:
                widths.append(int(pw / cols))
        bw = fmt.border()
        bcol = fmt.borderBrush().color().name()[1:].upper() if fmt.borderBrush().style() != Qt.NoBrush else "808080"
        borders = ""
        if bw > 0:
            borders = "<w:tblBorders>" + "".join(f'<w:{s} w:val="single" w:sz="{max(2, int(bw * 6))}" w:space="0" w:color="{bcol}"/>' for s in ("top", "left", "bottom", "right", "insideH", "insideV")) + "</w:tblBorders>"
        cp = int(fmt.cellPadding() * 15) if fmt.cellPadding() else 60
        out = [f'<w:tbl><w:tblPr><w:tblW w:w="{K.px_tw(sum(widths))}" w:type="dxa"/>{borders}<w:tblLayout w:type="fixed"/><w:tblCellMar><w:top w:w="{cp}" w:type="dxa"/><w:left w:w="{cp * 2}" w:type="dxa"/><w:bottom w:w="{cp}" w:type="dxa"/><w:right w:w="{cp * 2}" w:type="dxa"/></w:tblCellMar></w:tblPr>']
        out.append("<w:tblGrid>" + "".join(f'<w:gridCol w:w="{K.px_tw(wd)}"/>' for wd in widths) + "</w:tblGrid>")
        for r in range(rows):
            out.append("<w:tr>")
            c = 0
            while c < cols:
                cell = t.cellAt(r, c)
                if cell.row() != r or cell.column() != c:
                    # covered by a merge
                    if cell.column() == c and cell.row() < r:
                        out.append(f'<w:tc><w:tcPr><w:tcW w:w="{K.px_tw(widths[c])}" w:type="dxa"/>{"<w:gridSpan w:val=%d/>" % cell.columnSpan() if False else ""}<w:vMerge/></w:tcPr><w:p/></w:tc>'.replace("<w:vMerge/></w:tcPr>", (f'<w:gridSpan w:val="{cell.columnSpan()}"/>' if cell.columnSpan() > 1 else "") + "<w:vMerge/></w:tcPr>"))
                        c += cell.columnSpan()
                    else:
                        c += 1
                    continue
                cs, rs = cell.columnSpan(), cell.rowSpan()
                cf = cell.format()
                pr = f'<w:tcW w:w="{K.px_tw(sum(widths[c:c + cs]))}" w:type="dxa"/>'
                if cs > 1:
                    pr += f'<w:gridSpan w:val="{cs}"/>'
                if rs > 1:
                    pr += '<w:vMerge w:val="restart"/>'
                if cf.background().style() != Qt.NoBrush:
                    pr += f'<w:shd w:val="clear" w:color="auto" w:fill="{cf.background().color().name()[1:].upper()}"/>'
                body = self.container(cell.begin()) or "<w:p/>"
                if not body.rstrip().endswith("</w:p>") and not body.rstrip().endswith("</w:tbl>"):
                    body += "<w:p/>"
                if body.rstrip().endswith("</w:tbl>"):
                    body += "<w:p/>"
                out.append(f"<w:tc><w:tcPr>{pr}</w:tcPr>{body}</w:tc>")
                c += cs
            out.append("</w:tr>")
        out.append("</w:tbl>")
        return "".join(out)

    # ---- parts
    def styles_xml(self):
        out = [f'<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n<w:styles xmlns:w="{W}">']
        out.append(f'<w:docDefaults><w:rPrDefault><w:rPr><w:rFonts w:ascii="Calibri" w:hAnsi="Calibri" w:cs="Calibri" w:eastAsia="Calibri"/><w:sz w:val="22"/><w:szCs w:val="22"/><w:lang w:val="en-US"/></w:rPr></w:rPrDefault>'
                   f'<w:pPrDefault><w:pPr><w:spacing w:after="120" w:line="276" w:lineRule="auto"/></w:pPr></w:pPrDefault></w:docDefaults>')
        for name, sid in K.STYLE_IDS.items():
            p = K.PRESETS[name]
            ppr = f'<w:spacing w:before="{int(p["before"] * 20)}" w:after="{int(p["after"] * 20)}" w:line="{int(p["line"] / 100 * 240)}" w:lineRule="auto"/>'
            if p["indent"]:
                ppr += f'<w:ind w:left="{int(p["indent"] * 15)}"/>'
            if p["level"]:
                ppr += f'<w:keepNext/><w:outlineLvl w:val="{p["level"] - 1}"/>'
            if p["bg"]:
                ppr += f'<w:shd w:val="clear" w:color="auto" w:fill="{p["bg"][1:]}"/>'
            rpr = ""
            if p["family"] == "mono":
                rpr += '<w:rFonts w:ascii="Consolas" w:hAnsi="Consolas" w:cs="Consolas"/>'
            if p["bold"]:
                rpr += "<w:b/>"
            if p["italic"]:
                rpr += "<w:i/>"
            if p["color"]:
                rpr += f'<w:color w:val="{p["color"][1:]}"/>'
            rpr += f'<w:sz w:val="{int(p["size"] * 2)}"/>'
            default = ' w:default="1"' if name == "Normal" else ""
            based = "" if name == "Normal" else '<w:basedOn w:val="Normal"/>'
            out.append(f'<w:style w:type="paragraph"{default} w:styleId="{sid}"><w:name w:val="{x(name if name != "Normal" else "Normal")}"/>{based}<w:qFormat/><w:pPr>{ppr}</w:pPr><w:rPr>{rpr}</w:rPr></w:style>')
        out.append('<w:style w:type="character" w:styleId="Hyperlink"><w:name w:val="Hyperlink"/><w:rPr><w:color w:val="0563C1"/><w:u w:val="single"/></w:rPr></w:style>')
        out.append("</w:styles>")
        return "".join(out)

    def numbering_xml(self):
        out = [f'<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n<w:numbering xmlns:w="{W}">']
        for style, aid in sorted(self.list_styles.items(), key=lambda kv: kv[1]):
            fmt, txt, font = LIST_FMT.get(style, ("bullet", "", "Symbol"))
            out.append(f'<w:abstractNum w:abstractNumId="{aid}"><w:multiLevelType w:val="hybridMultilevel"/>')
            for lvl in range(9):
                text = txt if fmt == "bullet" else f"%{lvl + 1}."
                rpr = f'<w:rPr><w:rFonts w:ascii="{font}" w:hAnsi="{font}" w:hint="default"/></w:rPr>' if font else ""
                out.append(f'<w:lvl w:ilvl="{lvl}"><w:start w:val="1"/><w:numFmt w:val="{fmt}"/><w:lvlText w:val="{x(text)}"/><w:lvlJc w:val="left"/>'
                           f'<w:pPr><w:ind w:left="{720 * (lvl + 1)}" w:hanging="360"/></w:pPr>{rpr}</w:lvl>')
            out.append("</w:abstractNum>")
        for nid, aid in self.nums:
            out.append(f'<w:num w:numId="{nid}"><w:abstractNumId w:val="{aid}"/><w:lvlOverride w:ilvl="0"><w:startOverride w:val="1"/></w:lvlOverride></w:num>')
        out.append("</w:numbering>")
        return "".join(out)

    def hf_xml(self, kind, text):
        parts = re.split(r"(\{page\}|\{pages\})", text)
        runs = []
        for p in parts:
            if p == "{page}":
                runs.append('<w:r><w:fldChar w:fldCharType="begin"/></w:r><w:r><w:instrText xml:space="preserve"> PAGE </w:instrText></w:r><w:r><w:fldChar w:fldCharType="separate"/></w:r><w:r><w:t>1</w:t></w:r><w:r><w:fldChar w:fldCharType="end"/></w:r>')
            elif p == "{pages}":
                runs.append('<w:r><w:fldChar w:fldCharType="begin"/></w:r><w:r><w:instrText xml:space="preserve"> NUMPAGES </w:instrText></w:r><w:r><w:fldChar w:fldCharType="separate"/></w:r><w:r><w:t>1</w:t></w:r><w:r><w:fldChar w:fldCharType="end"/></w:r>')
            elif p:
                runs.append(f'<w:r><w:t xml:space="preserve">{x(p)}</w:t></w:r>')
        tag = "hdr" if kind == "header" else "ftr"
        return f'<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n<w:{tag} {NSMAP}><w:p><w:pPr><w:jc w:val="center"/></w:pPr>{"".join(runs)}</w:p></w:{tag}>'


def QTextFormat_PageBreak_Before():
    from PySide6.QtGui import QTextFormat
    return int(QTextFormat.PageBreakFlag.PageBreak_AlwaysBefore.value) if hasattr(QTextFormat, "PageBreakFlag") else 0x001


def write_docx(doc, path, page, meta=None):
    wr = Writer(doc, page, meta)
    body = wr.container(doc.rootFrame().begin())
    pw, ph = page.size_in()
    t, r, b, l = page.margins
    hf = ""
    parts_extra = []
    if page.header_on and page.header:
        rid = wr.rel("http://schemas.openxmlformats.org/officeDocument/2006/relationships/header", "header1.xml")
        hf += f'<w:headerReference w:type="default" r:id="{rid}"/>'
        parts_extra.append(("word/header1.xml", wr.hf_xml("header", page.header), "application/vnd.openxmlformats-officedocument.wordprocessingml.header+xml"))
    if page.footer_on and page.footer:
        rid = wr.rel("http://schemas.openxmlformats.org/officeDocument/2006/relationships/footer", "footer1.xml")
        hf += f'<w:footerReference w:type="default" r:id="{rid}"/>'
        parts_extra.append(("word/footer1.xml", wr.hf_xml("footer", page.footer), "application/vnd.openxmlformats-officedocument.wordprocessingml.footer+xml"))
    sect = (f'<w:sectPr>{hf}<w:pgSz w:w="{int(pw * 1440)}" w:h="{int(ph * 1440)}"' + (' w:orient="landscape"' if page.landscape else "") + "/>"
            f'<w:pgMar w:top="{int(t * 1440)}" w:right="{int(r * 1440)}" w:bottom="{int(b * 1440)}" w:left="{int(l * 1440)}" w:header="708" w:footer="708" w:gutter="0"/></w:sectPr>')
    docxml = f'<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n<w:document {NSMAP}><w:body>{body}{sect}</w:body></w:document>'
    # lists must be known before numbering is written -> numbering_xml after body
    numbering = wr.numbering_xml()
    rels = ['<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">',
            '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/styles" Target="styles.xml"/>',
            '<Relationship Id="rId2" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/numbering" Target="numbering.xml"/>']
    for rid, typ, target, ext in wr.rels:
        rels.append(f'<Relationship Id="{rid}" Type="{typ}" Target="{x(target)}"' + (' TargetMode="External"' if ext else "") + "/>")
    rels.append("</Relationships>")
    ct = ['<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">',
          '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/><Default Extension="xml" ContentType="application/xml"/><Default Extension="png" ContentType="image/png"/>',
          '<Override PartName="/word/document.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/>',
          '<Override PartName="/word/styles.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.styles+xml"/>',
          '<Override PartName="/word/numbering.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.numbering+xml"/>',
          '<Override PartName="/docProps/core.xml" ContentType="application/vnd.openxmlformats-package.core-properties+xml"/>']
    for name, _, c in parts_extra:
        ct.append(f'<Override PartName="/{name}" ContentType="{c}"/>')
    ct.append("</Types>")
    core = ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n<cp:coreProperties xmlns:cp="http://schemas.openxmlformats.org/package/2006/metadata/core-properties" xmlns:dc="http://purl.org/dc/elements/1.1/" xmlns:dcterms="http://purl.org/dc/terms/">'
            f'<dc:title>{x((meta or {}).get("title", ""))}</dc:title><dc:creator>{x((meta or {}).get("author", ""))}</dc:creator></cp:coreProperties>')
    tmp = path + ".part"
    with zipfile.ZipFile(tmp, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("[Content_Types].xml", "".join(ct))
        z.writestr("_rels/.rels", '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="word/document.xml"/><Relationship Id="rId2" Type="http://schemas.openxmlformats.org/package/2006/relationships/metadata/core-properties" Target="docProps/core.xml"/></Relationships>')
        z.writestr("word/document.xml", docxml)
        z.writestr("word/styles.xml", wr.styles_xml())
        z.writestr("word/numbering.xml", numbering)
        z.writestr("word/_rels/document.xml.rels", "".join(rels))
        z.writestr("docProps/core.xml", core)
        for name, content, _ in parts_extra:
            z.writestr(name, content)
        for fname, data in wr.media:
            z.writestr("word/media/" + fname, data)
    os.replace(tmp, path)


# ======================================================================= reader
class Reader:
    def __init__(self, path):
        self.z = zipfile.ZipFile(path)
        self.names = set(self.z.namelist())
        self.doc = QTextDocument()
        self.doc.setUndoRedoEnabled(False)
        self.dpi = K.dpi()
        self.styles = {}
        self.defaults = {"r": {}, "p": {}}
        self.num_defs = {}      # numId -> {ilvl: (fmt, text)}
        self.rels = {}
        self.img_n = 0
        self.page = K.Page()
        self.lists = {}
        self.parse_rels()
        self.parse_styles()
        self.parse_numbering()

    # ---- helpers
    def xml(self, name):
        return ET.fromstring(self.z.read(name))

    def parse_rels(self):
        n = "word/_rels/document.xml.rels"
        if n in self.names:
            for r in self.xml(n):
                self.rels[r.get("Id")] = (r.get("Type"), r.get("Target"), r.get("TargetMode"))

    def rpr_dict(self, rpr):
        d = {}
        if rpr is None:
            return d
        for ch in rpr:
            t = ch.tag.split("}")[1]
            v = ch.get(w("val"))
            if t in ("b", "bCs"):
                d["b"] = v not in ("0", "false")
            elif t in ("i", "iCs"):
                d["i"] = v not in ("0", "false")
            elif t == "strike" or t == "dstrike":
                d["strike"] = v not in ("0", "false")
            elif t == "u":
                d["u"] = v not in ("none", "0", "false")
            elif t == "color":
                if v and v != "auto":
                    d["color"] = "#" + v
            elif t == "sz":
                if v:
                    d["sz"] = int(v) / 2.0
            elif t == "rFonts":
                fam = ch.get(w("ascii")) or ch.get(w("hAnsi")) or ch.get(w("cs"))
                if fam:
                    d["font"] = fam
            elif t == "highlight":
                m = {"yellow": "#FFFF00", "green": "#00FF00", "cyan": "#00FFFF", "magenta": "#FF00FF", "blue": "#0000FF", "red": "#FF0000", "darkBlue": "#000080",
                     "darkCyan": "#008080", "darkGreen": "#008000", "darkMagenta": "#800080", "darkRed": "#800000", "darkYellow": "#808000", "darkGray": "#808080",
                     "lightGray": "#C0C0C0", "black": "#000000", "white": "#FFFFFF"}
                if v in m:
                    d["bg"] = m[v]
            elif t == "shd":
                fill = ch.get(w("fill"))
                if fill and fill not in ("auto", "FFFFFF"):
                    d["bg"] = "#" + fill
            elif t == "vertAlign":
                d["va"] = v
            elif t == "rStyle":
                d["rstyle"] = v
            elif t == "caps" or t == "smallCaps":
                d["caps"] = v not in ("0", "false")
        return d

    def ppr_dict(self, ppr):
        d = {}
        if ppr is None:
            return d
        for ch in ppr:
            t = ch.tag.split("}")[1]
            v = ch.get(w("val"))
            if t == "pStyle":
                d["style"] = v
            elif t == "jc":
                d["jc"] = v
            elif t == "spacing":
                for k in ("before", "after", "line", "lineRule"):
                    if ch.get(w(k)) is not None:
                        d[k] = ch.get(w(k))
            elif t == "ind":
                for k in ("left", "right", "firstLine", "hanging", "start", "end"):
                    if ch.get(w(k)) is not None:
                        d["ind_" + k] = ch.get(w(k))
            elif t == "numPr":
                n = ch.find(w("numId"))
                l = ch.find(w("ilvl"))
                d["num"] = (n.get(w("val")) if n is not None else None, int(l.get(w("val"))) if l is not None else 0)
            elif t == "pageBreakBefore":
                d["pbb"] = v not in ("0", "false")
            elif t == "shd":
                fill = ch.get(w("fill"))
                if fill and fill not in ("auto", "FFFFFF"):
                    d["bg"] = "#" + fill
            elif t == "bidi":
                d["bidi"] = v not in ("0", "false")
            elif t == "outlineLvl":
                d["outline"] = int(v)
            elif t == "rPr":
                d["rpr"] = self.rpr_dict(ch)
        return d

    def parse_styles(self):
        if "word/styles.xml" not in self.names:
            return
        root = self.xml("word/styles.xml")
        dd = root.find(w("docDefaults"))
        if dd is not None:
            r = dd.find(w("rPrDefault") + "/" + w("rPr"))
            p = dd.find(w("pPrDefault") + "/" + w("pPr"))
            self.defaults["r"] = self.rpr_dict(r)
            self.defaults["p"] = self.ppr_dict(p)
        for s in root.findall(w("style")):
            sid = s.get(w("styleId"))
            name = s.find(w("name"))
            based = s.find(w("basedOn"))
            self.styles[sid] = {"type": s.get(w("type")), "name": name.get(w("val")) if name is not None else sid, "based": based.get(w("val")) if based is not None else None,
                                "p": self.ppr_dict(s.find(w("pPr"))), "r": self.rpr_dict(s.find(w("rPr"))), "default": s.get(w("default")) == "1"}

    def style_props(self, sid, kind):
        chain, seen = [], set()
        while sid and sid in self.styles and sid not in seen:
            seen.add(sid)
            chain.append(self.styles[sid])
            sid = self.styles[sid]["based"]
        out = {}
        for s in reversed(chain):
            out.update(s[kind])
        return out

    def default_pstyle(self):
        for sid, s in self.styles.items():
            if s["type"] == "paragraph" and s["default"]:
                return sid
        return "Normal"

    def parse_numbering(self):
        if "word/numbering.xml" not in self.names:
            return
        root = self.xml("word/numbering.xml")
        abstract = {}
        for a in root.findall(w("abstractNum")):
            lv = {}
            for l in a.findall(w("lvl")):
                fmt = l.find(w("numFmt"))
                txt = l.find(w("lvlText"))
                lv[int(l.get(w("ilvl")))] = (fmt.get(w("val")) if fmt is not None else "bullet", txt.get(w("val")) if txt is not None else "")
            abstract[a.get(w("abstractNumId"))] = lv
        for n in root.findall(w("num")):
            aid = n.find(w("abstractNumId"))
            if aid is not None:
                self.num_defs[n.get(w("numId"))] = abstract.get(aid.get(w("val")), {})

    # ---- formats
    def char_format(self, props):
        f = QTextCharFormat()
        fam = props.get("font")
        if fam:
            f.setFontFamilies([fam] + K.BODY_FAMILIES[1:])
        sz = props.get("sz")
        if sz:
            f.setFontPointSize(sz)
        if props.get("b"):
            f.setFontWeight(700)
        if props.get("i"):
            f.setFontItalic(True)
        if props.get("u"):
            f.setFontUnderline(True)
        if props.get("strike"):
            f.setFontStrikeOut(True)
        if props.get("color"):
            f.setForeground(QColor(props["color"]))
        if props.get("bg"):
            f.setBackground(QColor(props["bg"]))
        if props.get("va") == "superscript":
            f.setVerticalAlignment(QTextCharFormat.AlignSuperScript)
        elif props.get("va") == "subscript":
            f.setVerticalAlignment(QTextCharFormat.AlignSubScript)
        if props.get("caps"):
            f.setFontCapitalization(QFont.AllUppercase)
        return f

    def block_format(self, p, style_name):
        bf = QTextBlockFormat()
        jc = p.get("jc")
        bf.setAlignment({"center": Qt.AlignHCenter, "right": Qt.AlignRight, "end": Qt.AlignRight, "both": Qt.AlignJustify, "distribute": Qt.AlignJustify}.get(jc, Qt.AlignLeft))
        before = int(p.get("before", 0)) / 20.0
        after = int(p.get("after", 0)) / 20.0
        bf.setTopMargin(K.pt_px(before))
        bf.setBottomMargin(K.pt_px(after))
        if p.get("line"):
            line = int(p["line"])
            rule = p.get("lineRule", "auto")
            if rule == "auto":
                bf.setLineHeight(max(80, line / 240 * 100), QTextBlockFormat.LineHeightTypes.ProportionalHeight.value)
            elif rule == "exact":
                bf.setLineHeight(K.tw_px(line), QTextBlockFormat.LineHeightTypes.FixedHeight.value)
            else:
                bf.setLineHeight(K.tw_px(line), QTextBlockFormat.LineHeightTypes.MinimumHeight.value)
        left = int(p.get("ind_left", p.get("ind_start", 0)))
        right = int(p.get("ind_right", p.get("ind_end", 0)))
        bf.setLeftMargin(K.tw_px(left))
        bf.setRightMargin(K.tw_px(right))
        if "ind_firstLine" in p:
            bf.setTextIndent(K.tw_px(int(p["ind_firstLine"])))
        elif "ind_hanging" in p:
            bf.setTextIndent(-K.tw_px(int(p["ind_hanging"])))
        if p.get("pbb"):
            bf.setPageBreakPolicy(QTextFormat_PageBreakPolicy())
        if p.get("bg"):
            bf.setBackground(QColor(p["bg"]))
        if p.get("bidi"):
            bf.setLayoutDirection(Qt.RightToLeft)
        name = style_name
        if name in K.PRESETS:
            lvl = K.PRESETS[name]["level"]
            if lvl:
                bf.setHeadingLevel(lvl)
            elif name != "Normal":
                bf.setProperty(K.PROP_STYLE, name)
        return bf

    def style_name_for(self, sid, p):
        st = self.styles.get(sid or self.default_pstyle())
        name = (st["name"] if st else "Normal").lower() if st else "normal"
        sid_l = (sid or "").lower()
        for key, nm in (("heading 1", "Heading 1"), ("heading 2", "Heading 2"), ("heading 3", "Heading 3"), ("heading 4", "Heading 4"), ("title", "Title"), ("subtitle", "Subtitle"),
                        ("quote", "Quote"), ("code", "Code")):
            if name == key or sid_l == key.replace(" ", ""):
                return nm
        outline = p.get("outline")
        if outline is not None and outline < 4:
            return f"Heading {outline + 1}"
        return "Normal"

    # ---- content
    def read(self):
        root = self.xml("word/document.xml")
        body = root.find(w("body"))
        self.read_section(body.find(w("sectPr")))
        cur = QTextCursor(self.doc)
        self.first = True
        self.container(body, cur)
        # cleanup: the document starts with one empty block when the first item was a table
        self.doc.setUndoRedoEnabled(True)
        self.doc.setModified(False)
        return self.doc, self.page

    def read_section(self, sp):
        if sp is None:
            return
        pg = sp.find(w("pgSz"))
        if pg is not None and pg.get(w("w")):
            wi, hi = int(pg.get(w("w"))) / 1440.0, int(pg.get(w("h"))) / 1440.0
            land = pg.get(w("orient")) == "landscape" or wi > hi
            a, b = (min(wi, hi), max(wi, hi))
            best = min(K.PAPERS, key=lambda n: abs(K.PAPERS[n][0] - a) + abs(K.PAPERS[n][1] - b))
            self.page.paper = best
            self.page.landscape = land
        mg = sp.find(w("pgMar"))
        if mg is not None:
            try:
                self.page.margins = [int(mg.get(w(k), 1440)) / 1440.0 for k in ("top", "right", "bottom", "left")]
            except ValueError:
                pass
        for kind, tag in (("header", "headerReference"), ("footer", "footerReference")):
            ref = sp.find(w(tag))
            if ref is not None:
                rel = self.rels.get(ref.get("{%s}id" % R))
                if rel:
                    name = "word/" + rel[1]
                    if name in self.names:
                        text = self.hf_text(self.xml(name))
                        setattr(self.page, kind, text)
                        setattr(self.page, kind + "_on", bool(text))

    def hf_text(self, root):
        out = []
        for p in root.iter(w("p")):
            t = []
            skip = False
            for el in p.iter():
                tag = el.tag.split("}")[1]
                if tag == "fldChar":
                    ty = el.get(w("fldCharType"))
                    if ty == "separate":
                        skip = True
                    elif ty == "end":
                        skip = False
                elif tag == "t" and not skip:
                    t.append(el.text or "")
                elif tag == "instrText":
                    s = (el.text or "").upper()
                    t.append("{pages}" if "NUMPAGES" in s else "{page}" if "PAGE" in s else "")
            if t:
                out.append("".join(t))
        return " ".join(out).strip()

    def container(self, parent, cur):
        for ch in parent:
            tag = ch.tag.split("}")[1]
            if tag == "p":
                self.paragraph(ch, cur)
            elif tag == "tbl":
                self.table(ch, cur)
            elif tag in ("sdt",):
                content = ch.find(w("sdtContent"))
                if content is not None:
                    self.container(content, cur)
            elif tag in ("ins",):
                self.container(ch, cur)

    def paragraph(self, p, cur):
        ppr = self.ppr_dict(p.find(w("pPr")))
        sid = ppr.get("style") or self.default_pstyle()
        props = dict(self.defaults["p"])
        props.update(self.style_props(sid, "p"))
        props.update({k: v for k, v in ppr.items() if k != "rpr"})
        name = self.style_name_for(sid, props)
        bf = self.block_format(props, name)
        base_r = dict(self.defaults["r"])
        base_r.update(self.style_props(sid, "r"))
        if ppr.get("rpr"):
            base_r.update(ppr["rpr"])
        if name in K.PRESETS and name != "Normal" and sid not in self.styles:
            pr = K.PRESETS[name]
            base_r.setdefault("sz", pr["size"])
        # list
        lst = None
        num = props.get("num")
        if num and num[0] and num[0] != "0":
            numid, lvl = num
            lv = self.num_defs.get(numid, {}).get(lvl) or self.num_defs.get(numid, {}).get(0)
            if lv:
                fmt, txt = lv
                style = {"decimal": QTextListFormat.ListDecimal, "lowerLetter": QTextListFormat.ListLowerAlpha, "upperLetter": QTextListFormat.ListUpperAlpha,
                         "lowerRoman": QTextListFormat.ListLowerRoman, "upperRoman": QTextListFormat.ListUpperRoman}.get(fmt)
                if fmt == "bullet" or fmt == "none" or style is None:
                    style = QTextListFormat.ListCircle if txt in ("o",) else QTextListFormat.ListSquare if txt in ("", "▪", "■", "§") else QTextListFormat.ListDisc
                lst = (numid, lvl, style)
        if self.first:
            cur.setBlockFormat(bf)
            self.first = False
        else:
            cur.insertBlock(bf, QTextCharFormat())
        # clear stale list membership
        base_cf = self.char_format(base_r)
        cur.setBlockCharFormat(base_cf)
        if lst:
            numid, lvl, style = lst
            key = (numid, lvl)
            for k in [k for k in self.lists if k[0] == numid and k[1] > lvl]:
                del self.lists[k]
            tl = self.lists.get(key)
            if tl is None:
                lf = QTextListFormat()
                lf.setStyle(style)
                lf.setIndent(lvl + 1)
                nbf = cur.blockFormat()
                nbf.setLeftMargin(0)
                nbf.setTextIndent(0)
                cur.setBlockFormat(nbf)
                tl = cur.createList(lf)
                self.lists[key] = tl
            else:
                tl.add(cur.block())
        else:
            self.lists = {}
        self.runs(p, cur, base_r)

    def runs(self, p, cur, base_r, href=None):
        for ch in p:
            tag = ch.tag.split("}")[1]
            if tag == "r":
                self.run(ch, cur, base_r, href)
            elif tag == "hyperlink":
                rid = ch.get("{%s}id" % R)
                target = None
                if rid and rid in self.rels:
                    target = self.rels[rid][1]
                elif ch.get(w("anchor")):
                    target = "#" + ch.get(w("anchor"))
                self.runs(ch, cur, base_r, target)
            elif tag in ("ins", "smartTag", "sdt", "fldSimple"):
                inner = ch.find(w("sdtContent")) if tag == "sdt" else ch
                if inner is not None:
                    self.runs(inner, cur, base_r, href)

    def run(self, r, cur, base_r, href):
        rpr = self.rpr_dict(r.find(w("rPr")))
        props = dict(base_r)
        if rpr.get("rstyle"):
            props.update(self.style_props(rpr["rstyle"], "r"))
            if "hyperlink" in rpr["rstyle"].lower() and not href:
                props.setdefault("color", "#0563C1")
        props.update({k: v for k, v in rpr.items() if k != "rstyle"})
        cf = self.char_format(props)
        if href:
            cf.setAnchor(True)
            cf.setAnchorHref(href)
            cf.setFontUnderline(True)
            if not props.get("color"):
                cf.setForeground(QColor("#0563C1"))
        for el in r:
            t = el.tag.split("}")[1]
            if t == "t":
                if el.text:
                    cur.insertText(el.text, cf)
            elif t == "tab":
                cur.insertText("\t", cf)
            elif t == "br":
                if el.get(w("type")) == "page":
                    nbf = QTextBlockFormat(cur.blockFormat())
                    cur.insertBlock(nbf)
                    nbf.setPageBreakPolicy(QTextFormat_PageBreakPolicy())
                    cur.setBlockFormat(nbf)
                else:
                    cur.insertText(" ", cf)
            elif t in ("drawing", "pict"):
                self.image(el, cur, cf)
            elif t == "AlternateContent":
                ch = el.find("{http://schemas.openxmlformats.org/markup-compatibility/2006}Choice")
                if ch is not None:
                    for sub in ch:
                        self.image(sub, cur, cf)

    def image(self, el, cur, cf):
        blip = None
        ext = None
        for sub in el.iter():
            tag = sub.tag.split("}")[1]
            if tag == "blip" and blip is None:
                blip = sub.get("{%s}embed" % R)
            elif tag == "extent" and ext is None:
                ext = sub
        if not blip or blip not in self.rels:
            return
        target = self.rels[blip][1].lstrip("/")
        name = target if target.startswith("word/") else "word/" + target
        if name not in self.names:
            return
        img = QImage.fromData(self.z.read(name))
        if img.isNull():
            return
        self.img_n += 1
        res = f"docximg{self.img_n}"
        self.doc.addResource(QTextDocument.ImageResource, QUrl(res), img)
        fmt = QTextImageFormat()
        fmt.setName(res)
        if ext is not None:
            wpx, hpx = K.emu_px(int(ext.get("cx", 0))), K.emu_px(int(ext.get("cy", 0)))
        else:
            wpx, hpx = img.width(), img.height()
        pw, _ = self.page.content_px()
        if wpx > pw:
            hpx, wpx = hpx * pw / wpx, pw
        if wpx > 0:
            fmt.setWidth(wpx)
            fmt.setHeight(hpx)
        cur.insertImage(fmt)

    def table(self, tbl, cur):
        rows = tbl.findall(w("tr"))
        if not rows:
            return
        grid = [int(g.get(w("w"), 0)) for g in tbl.findall(w("tblGrid") + "/" + w("gridCol"))]
        ncols = len(grid) or max(sum(int((tc.find(w("tcPr") + "/" + w("gridSpan")).get(w("val"))) if tc.find(w("tcPr") + "/" + w("gridSpan")) is not None else 1) for tc in tr.findall(w("tc"))) for tr in rows)
        if not grid:
            grid = [int(self.page.content_px()[0] / ncols / self.dpi * 1440)] * ncols
        # cell layout with spans
        layout = []   # (row, col, tc, cs, vmerge)
        vstart = {}
        spans = []
        for ri, tr in enumerate(rows):
            col = 0
            for tc in tr.findall(w("tc")):
                pr = tc.find(w("tcPr"))
                cs = 1
                vm = None
                if pr is not None:
                    gs = pr.find(w("gridSpan"))
                    if gs is not None:
                        cs = int(gs.get(w("val"), 1))
                    v = pr.find(w("vMerge"))
                    if v is not None:
                        vm = v.get(w("val"), "continue")
                if vm == "continue" and col in vstart:
                    r0 = vstart[col]
                    spans[r0][2] += 1
                    layout.append((ri, col, None, cs, "cont"))
                else:
                    layout.append((ri, col, tc, cs, vm))
                    if vm == "restart":
                        vstart[col] = len(spans)
                    spans.append([ri, col, 1, cs, tc])
                    if vm != "restart":
                        vstart.pop(col, None)
                col += cs
        # create the table
        pr = tbl.find(w("tblPr"))
        tf = QTextTableFormat()
        tf.setBorder(0)
        tf.setCellPadding(4)
        tf.setCellSpacing(0)
        tf.setBorderCollapse(True)
        tw = sum(grid)
        tf.setColumnWidthConstraints([QTextLength(QTextLength.PercentageLength, g / tw * 100) for g in grid])
        tf.setWidth(QTextLength(QTextLength.PercentageLength, 100))
        border = False
        if pr is not None:
            if pr.find(w("tblBorders")) is not None:
                b = pr.find(w("tblBorders") + "/" + w("top"))
                border = b is not None and b.get(w("val")) not in ("nil", "none")
            st = pr.find(w("tblStyle"))
            if st is not None and ("grid" in st.get(w("val"), "").lower()):
                border = True
        if border:
            tf.setBorder(1)
            tf.setBorderBrush(QColor("#808080"))
        # make sure the table starts after the current block when it has content
        if not self.first:
            cur.insertBlock(QTextBlockFormat(), QTextCharFormat())
        table = cur.insertTable(len(rows), ncols, tf)
        first_block_used = not self.first
        self.first = False
        for (ri, col, tc, cs, vm) in layout:
            if tc is None or col >= ncols:
                continue
            cell = table.cellAt(ri, col)
            ccur = cell.firstCursorPosition()
            pr2 = tc.find(w("tcPr"))
            if pr2 is not None:
                shd = pr2.find(w("shd"))
                if shd is not None and shd.get(w("fill")) not in (None, "auto", "FFFFFF"):
                    cf = cell.format().toTableCellFormat()
                    cf.setBackground(QColor("#" + shd.get(w("fill"))))
                    cell.setFormat(cf)
            saved = self.first, self.lists
            self.first = True
            self.lists = {}
            self.container(tc, ccur)
            self.first, self.lists = saved
        for (r0, c0, rs, cs, tc) in spans:
            if rs > 1 or cs > 1:
                table.mergeCells(r0, c0, rs, cs)
        # move the cursor after the table
        cur.setPosition(table.lastPosition() + 1) if table.lastPosition() + 1 <= self.doc.characterCount() - 1 else cur.movePosition(QTextCursor.End)
        self.first = False
        self.lists = {}
        # a block is needed after a table
        if cur.atEnd():
            pass
        self.first = False


def QTextFormat_PageBreakPolicy():
    from PySide6.QtGui import QTextFormat
    try:
        return QTextFormat.PageBreakFlag.PageBreak_AlwaysBefore
    except AttributeError:
        return QTextFormat.PageBreak_AlwaysBefore


def read_docx(path):
    r = Reader(path)
    return r.read()
