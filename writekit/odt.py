"""ODT (OpenDocument text) reader: paragraphs, headings, character styles, lists, tables, pictures, links, page size."""
import re
import zipfile
from xml.etree import ElementTree as ET

from PySide6.QtCore import Qt, QUrl
from PySide6.QtGui import (QColor, QFont, QImage, QTextBlockFormat, QTextCharFormat, QTextCursor, QTextDocument, QTextImageFormat, QTextLength, QTextListFormat,
                           QTextTableFormat)

from . import common as K

NS = {"office": "urn:oasis:names:tc:opendocument:xmlns:office:1.0", "text": "urn:oasis:names:tc:opendocument:xmlns:text:1.0",
      "style": "urn:oasis:names:tc:opendocument:xmlns:style:1.0", "fo": "urn:oasis:names:tc:opendocument:xmlns:xsl-fo-compatible:1.0",
      "table": "urn:oasis:names:tc:opendocument:xmlns:table:1.0", "draw": "urn:oasis:names:tc:opendocument:xmlns:drawing:1.0",
      "xlink": "http://www.w3.org/1999/xlink", "svg": "urn:oasis:names:tc:opendocument:xmlns:svg-compatible:1.0"}


def q(prefix, name):
    return "{%s}%s" % (NS[prefix], name)


def length_pt(v):
    if not v:
        return None
    m = re.match(r"^\s*(-?[\d.]+)\s*(cm|mm|in|pt|px|pc|%)?", v)
    if not m:
        return None
    n = float(m.group(1))
    u = m.group(2) or "pt"
    return {"cm": n / 2.54 * 72, "mm": n / 25.4 * 72, "in": n * 72, "pt": n, "px": n * 0.75, "pc": n * 12, "%": None}[u]


class OdtReader:
    def __init__(self, path):
        self.z = zipfile.ZipFile(path)
        self.names = set(self.z.namelist())
        self.styles = {}        # (family, name) -> dict(props, parent)
        self.list_styles = {}   # name -> {level: ("bullet"/"number", fmt)}
        self.page = K.Page()
        self.doc = QTextDocument()
        self.doc.setUndoRedoEnabled(False)
        self.img_n = 0
        self.first = True
        self.lists = {}
        for part in ("styles.xml", "content.xml"):
            if part in self.names:
                self.collect_styles(ET.fromstring(self.z.read(part)))

    # ---- styles
    def collect_styles(self, root):
        for st in root.iter(q("style", "style")):
            name, fam = st.get(q("style", "name")), st.get(q("style", "family"))
            props = {}
            tp = st.find(q("style", "text-properties"))
            pp = st.find(q("style", "paragraph-properties"))
            if tp is not None:
                props.update({k.split("}")[1] if "}" in k else k: v for k, v in tp.attrib.items()})
                props = {("t_" + k): v for k, v in props.items()}
            if pp is not None:
                props.update({"p_" + (k.split("}")[1]): v for k, v in pp.attrib.items()})
            tcp = st.find(q("style", "table-cell-properties"))
            if tcp is not None:
                props.update({"c_" + (k.split("}")[1]): v for k, v in tcp.attrib.items()})
            self.styles[(fam, name)] = {"p": props, "parent": st.get(q("style", "parent-style-name")), "outline": st.get(q("style", "default-outline-level"))}
        for pl in root.iter(q("style", "page-layout-properties")):
            self.read_page(pl)
            break
        for ls in root.iter(q("text", "list-style")):
            lv = {}
            for ch in ls:
                tag = ch.tag.split("}")[1]
                if tag.startswith("list-level-style"):
                    level = int(ch.get(q("text", "level"), 1))
                    if "bullet" in tag:
                        lv[level] = ("bullet", ch.get(q("text", "bullet-char"), "•"))
                    elif "number" in tag:
                        lv[level] = ("number", ch.get(q("style", "num-format"), "1"))
            self.list_styles[ls.get(q("style", "name"))] = lv

    def read_page(self, pl):
        w, h = length_pt(pl.get(q("fo", "page-width"))), length_pt(pl.get(q("fo", "page-height")))
        if w and h:
            a, b = sorted((w / 72, h / 72))
            self.page.paper = min(K.PAPERS, key=lambda n: abs(K.PAPERS[n][0] - a) + abs(K.PAPERS[n][1] - b))
            self.page.landscape = w > h
        m = []
        for side in ("top", "right", "bottom", "left"):
            v = length_pt(pl.get(q("fo", "margin-" + side)))
            m.append(v / 72 if v is not None else 1.0)
        self.page.margins = m

    def resolved(self, fam, name):
        out, chain, seen = {}, [], set()
        while name and (fam, name) in self.styles and name not in seen:
            seen.add(name)
            chain.append(self.styles[(fam, name)])
            name = self.styles[(fam, name)]["parent"]
        for s in reversed(chain):
            out.update(s["p"])
        return out

    # ---- formats
    def char_format(self, props):
        f = QTextCharFormat()
        fam = props.get("t_font-family") or props.get("t_font-name")
        if fam:
            f.setFontFamilies([fam.strip("'\"")] + K.BODY_FAMILIES[1:])
        sz = length_pt(props.get("t_font-size"))
        if sz:
            f.setFontPointSize(sz)
        if props.get("t_font-weight") in ("bold", "700", "800", "900"):
            f.setFontWeight(700)
        if props.get("t_font-style") in ("italic", "oblique"):
            f.setFontItalic(True)
        us = props.get("t_text-underline-style")
        if us and us != "none":
            f.setFontUnderline(True)
        ls = props.get("t_text-line-through-style")
        if ls and ls != "none":
            f.setFontStrikeOut(True)
        c = props.get("t_color")
        if c and re.match(r"^#[0-9a-fA-F]{6}$", c):
            f.setForeground(QColor(c))
        bg = props.get("t_background-color")
        if bg and re.match(r"^#[0-9a-fA-F]{6}$", bg):
            f.setBackground(QColor(bg))
        pos = props.get("t_text-position", "")
        if pos.startswith("super"):
            f.setVerticalAlignment(QTextCharFormat.AlignSuperScript)
        elif pos.startswith("sub") or pos.startswith("-"):
            f.setVerticalAlignment(QTextCharFormat.AlignSubScript)
        return f

    def block_format(self, props, level=0, hname=None):
        bf = QTextBlockFormat()
        al = props.get("p_text-align")
        bf.setAlignment({"center": Qt.AlignHCenter, "end": Qt.AlignRight, "right": Qt.AlignRight, "justify": Qt.AlignJustify}.get(al, Qt.AlignLeft))
        for side, setter in (("top", bf.setTopMargin), ("bottom", bf.setBottomMargin), ("left", bf.setLeftMargin), ("right", bf.setRightMargin)):
            v = length_pt(props.get("p_margin-" + side))
            if v:
                setter(K.pt_px(v))
        ti = length_pt(props.get("p_text-indent"))
        if ti:
            bf.setTextIndent(K.pt_px(ti))
        lh = props.get("p_line-height", "")
        if lh.endswith("%"):
            bf.setLineHeight(max(80.0, float(lh[:-1])), QTextBlockFormat.LineHeightTypes.ProportionalHeight.value)
        if props.get("p_break-before") == "page":
            from .docx import QTextFormat_PageBreakPolicy
            bf.setPageBreakPolicy(QTextFormat_PageBreakPolicy())
        bg = props.get("p_background-color")
        if bg and re.match(r"^#[0-9a-fA-F]{6}$", bg):
            bf.setBackground(QColor(bg))
        if level:
            bf.setHeadingLevel(min(4, level))
        return bf

    # ---- read
    def read(self):
        root = ET.fromstring(self.z.read("content.xml"))
        body = root.find(q("office", "body") + "/" + q("office", "text"))
        for st in root.iter(q("style", "style")):
            pass
        cur = QTextCursor(self.doc)
        self.container(body, cur)
        self.doc.setUndoRedoEnabled(True)
        self.doc.setModified(False)
        return self.doc, self.page

    def container(self, parent, cur, list_level=None):
        for ch in parent:
            tag = ch.tag.split("}")[1]
            if tag in ("p", "h"):
                self.paragraph(ch, cur, None)
            elif tag == "list":
                self.list_(ch, cur, 1, ch.get(q("text", "style-name")))
            elif tag == "table":
                self.table(ch, cur)
            elif tag in ("section", "index-body", "table-of-content", "index-title"):
                self.container(ch, cur)

    def list_(self, lst, cur, level, style):
        style = lst.get(q("text", "style-name")) or style
        for item in lst:
            if item.tag != q("text", "list-item") and item.tag != q("text", "list-header"):
                continue
            first_para = True
            for ch in item:
                tag = ch.tag.split("}")[1]
                if tag in ("p", "h"):
                    self.paragraph(ch, cur, (style, level) if first_para else None)
                    first_para = False
                elif tag == "list":
                    self.list_(ch, cur, level + 1, style)

    def new_block(self, cur, bf, cf):
        if self.first:
            cur.setBlockFormat(bf)
            cur.setBlockCharFormat(cf)
            self.first = False
        else:
            cur.insertBlock(bf, cf)

    def paragraph(self, p, cur, lst):
        sname = p.get(q("text", "style-name"))
        props = self.resolved("paragraph", sname)
        level = 0
        if p.tag == q("text", "h"):
            level = int(p.get(q("text", "outline-level"), 1))
        elif sname and sname.lower().startswith(("heading", "title")):
            m = re.search(r"(\d)", sname)
            level = int(m.group(1)) if m else 0
        bf = self.block_format(props, level)
        cf = self.char_format(props)
        if level and not cf.fontPointSize():
            pr = K.PRESETS.get(f"Heading {min(4, level)}")
            cf.setFontPointSize(pr["size"])
            cf.setFontWeight(700)
        if lst:
            bf.setLeftMargin(0)
            bf.setTextIndent(0)
        self.new_block(cur, bf, cf)
        if lst:
            style, lvl = lst
            kind, fmt = self.list_styles.get(style, {}).get(lvl, ("bullet", "•"))
            ls = QTextListFormat()
            if kind == "number":
                ls.setStyle({"a": QTextListFormat.ListLowerAlpha, "A": QTextListFormat.ListUpperAlpha, "i": QTextListFormat.ListLowerRoman,
                             "I": QTextListFormat.ListUpperRoman}.get(fmt, QTextListFormat.ListDecimal))
            else:
                ls.setStyle(QTextListFormat.ListCircle if fmt in ("◦", "o") else QTextListFormat.ListSquare if fmt in ("▪", "■") else QTextListFormat.ListDisc)
            ls.setIndent(lvl)
            key = (style, lvl)
            for k in [k for k in self.lists if k[0] == style and k[1] > lvl]:
                del self.lists[k]
            tl = self.lists.get(key)
            if tl is None:
                self.lists[key] = cur.createList(ls)
            else:
                tl.add(cur.block())
        else:
            self.lists = {}
        self.inline(p, cur, props, None)

    def inline(self, el, cur, base, href):
        if el.text:
            self.text(el.text, cur, base, href)
        for ch in el:
            tag = ch.tag.split("}")[1]
            if tag == "span":
                pr = dict(base)
                pr.update(self.resolved("text", ch.get(q("text", "style-name"))))
                self.inline(ch, cur, pr, href)
            elif tag == "a":
                self.inline(ch, cur, base, ch.get(q("xlink", "href")))
            elif tag == "s":
                self.text(" " * int(ch.get(q("text", "c"), 1)), cur, base, href)
            elif tag == "tab":
                self.text("\t", cur, base, href)
            elif tag == "line-break":
                self.text(" ", cur, base, href)
            elif tag == "frame":
                self.image(ch, cur)
            elif tag in ("soft-page-break",):
                pass
            elif tag in ("bookmark", "bookmark-start", "bookmark-end", "note", "sequence", "page-number"):
                pass
            elif tag in ("date", "time", "title", "author-name", "initial-creator"):
                self.inline(ch, cur, base, href)
            if ch.tail:
                self.text(ch.tail, cur, base, href)

    def text(self, t, cur, props, href):
        t = re.sub(r"[\r\n]+", " ", t)
        if not t:
            return
        cf = self.char_format(props)
        if href:
            cf.setAnchor(True)
            cf.setAnchorHref(href)
            cf.setFontUnderline(True)
            if not props.get("t_color"):
                cf.setForeground(QColor("#0563C1"))
        cur.insertText(t, cf)

    def image(self, frame, cur):
        im = frame.find(q("draw", "image"))
        if im is None:
            return
        href = im.get(q("xlink", "href"), "")
        if href not in self.names:
            return
        img = QImage.fromData(self.z.read(href))
        if img.isNull():
            return
        self.img_n += 1
        res = f"odtimg{self.img_n}"
        self.doc.addResource(QTextDocument.ImageResource, QUrl(res), img)
        fmt = QTextImageFormat()
        fmt.setName(res)
        w, h = length_pt(frame.get(q("svg", "width"))), length_pt(frame.get(q("svg", "height")))
        cw, _ = self.page.content_px()
        wpx = K.pt_px(w) if w else img.width()
        hpx = K.pt_px(h) if h else img.height()
        if wpx > cw:
            hpx, wpx = hpx * cw / wpx, cw
        fmt.setWidth(wpx)
        fmt.setHeight(hpx)
        cur.insertImage(fmt)

    def table(self, tbl, cur):
        rows = []
        for ch in tbl.iter():
            if ch.tag == q("table", "table-row"):
                rows.append(ch)
        if not rows:
            return
        cols = 0
        grid = []
        for ch in tbl:
            if ch.tag == q("table", "table-column"):
                n = int(ch.get(q("table", "number-columns-repeated"), 1))
                grid += [1] * n
        for r in rows:
            cols = max(cols, sum(int(c.get(q("table", "number-columns-spanned"), 1)) if c.tag == q("table", "table-cell") else int(c.get(q("table", "number-columns-repeated"), 1)) for c in r if c.tag in (q("table", "table-cell"), q("table", "covered-table-cell"))))
        cols = max(cols, len(grid), 1)
        tf = QTextTableFormat()
        tf.setBorder(1)
        tf.setBorderBrush(QColor("#808080"))
        tf.setCellPadding(4)
        tf.setCellSpacing(0)
        tf.setBorderCollapse(True)
        tf.setWidth(QTextLength(QTextLength.PercentageLength, 100))
        tf.setColumnWidthConstraints([QTextLength(QTextLength.PercentageLength, 100.0 / cols)] * cols)
        if not self.first:
            cur.insertBlock(QTextBlockFormat(), QTextCharFormat())
        t = cur.insertTable(len(rows), cols, tf)
        self.first = False
        merges = []
        for ri, r in enumerate(rows):
            ci = 0
            for c in r:
                if c.tag == q("table", "covered-table-cell"):
                    ci += int(c.get(q("table", "number-columns-repeated"), 1))
                    continue
                if c.tag != q("table", "table-cell"):
                    continue
                cs = int(c.get(q("table", "number-columns-spanned"), 1))
                rs = int(c.get(q("table", "number-rows-spanned"), 1))
                if ci >= cols:
                    break
                cell = t.cellAt(ri, ci)
                ccur = cell.firstCursorPosition()
                cp = self.resolved("table-cell", c.get(q("table", "style-name")))
                bg = cp.get("c_background-color")
                if bg and re.match(r"^#[0-9a-fA-F]{6}$", bg):
                    cf = cell.format().toTableCellFormat()
                    cf.setBackground(QColor(bg))
                    cell.setFormat(cf)
                saved = self.first, self.lists
                self.first, self.lists = True, {}
                self.container(c, ccur)
                self.first, self.lists = saved
                if cs > 1 or rs > 1:
                    merges.append((ri, ci, rs, cs))
                ci += cs
        for m in merges:
            t.mergeCells(*m)
        cur.setPosition(min(t.lastPosition() + 1, max(0, self.doc.characterCount() - 1)))
        self.first = False
        self.lists = {}


def read_odt(path):
    return OdtReader(path).read()
