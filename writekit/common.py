"""Shared constants: screen dpi, paper sizes, style presets, unit conversions."""
from PySide6.QtCore import QSizeF
from PySide6.QtGui import QFont, QGuiApplication, QTextBlockFormat, QTextCharFormat, QTextFormat

PROP_STYLE = QTextFormat.UserProperty + 1     # paragraph style name stored on the block
PROP_HR = QTextFormat.UserProperty + 2

BODY_FAMILIES = ["Calibri", "Carlito", "Arial", "Liberation Sans", "DejaVu Sans"]
MONO_FAMILIES = ["Consolas", "DejaVu Sans Mono", "Liberation Mono", "Courier New", "monospace"]
PAPERS = {"A4": (8.268, 11.693), "Letter": (8.5, 11.0), "Legal": (8.5, 14.0), "A5": (5.827, 8.268), "A3": (11.693, 16.535)}


def dpi():
    try:
        s = QGuiApplication.primaryScreen()
        v = s.logicalDotsPerInch() if s else 96.0
    except Exception:
        v = 96.0
    return max(72.0, min(220.0, v))


def pt_px(pt):
    return pt * dpi() / 72.0


def px_pt(px):
    return px * 72.0 / dpi()


def tw_px(tw):
    return tw / 1440.0 * dpi()


def px_tw(px):
    return int(round(px / dpi() * 1440))


def emu_px(emu):
    return emu / 914400.0 * dpi()


def px_emu(px):
    return int(round(px / dpi() * 914400))


class Page:
    """paper size and margins in inches"""

    def __init__(self):
        self.paper = "A4"
        self.landscape = False
        self.margins = [1.0, 1.0, 1.0, 1.0]   # top, right, bottom, left
        self.header = ""
        self.footer = "Page {page} of {pages}"
        self.header_on = False
        self.footer_on = False

    def size_in(self):
        w, h = PAPERS.get(self.paper, PAPERS["A4"])
        return (h, w) if self.landscape else (w, h)

    def paper_px(self):
        w, h = self.size_in()
        return w * dpi(), h * dpi()

    def content_px(self):
        pw, ph = self.paper_px()
        t, r, b, l = self.margins
        return pw - (l + r) * dpi(), ph - (t + b) * dpi()


# name -> (char props, block props)
PRESETS = {
    "Normal": dict(size=11, bold=False, italic=False, color=None, family=None, before=0, after=6, line=115, indent=0, bg=None, level=0),
    "Title": dict(size=26, bold=True, italic=False, color="#1B1040", family=None, before=0, after=8, line=100, indent=0, bg=None, level=0),
    "Subtitle": dict(size=14, bold=False, italic=True, color="#63596B", family=None, before=0, after=10, line=110, indent=0, bg=None, level=0),
    "Heading 1": dict(size=20, bold=True, italic=False, color="#8A2150", family=None, before=18, after=6, line=108, indent=0, bg=None, level=1),
    "Heading 2": dict(size=16, bold=True, italic=False, color="#C2395C", family=None, before=14, after=5, line=108, indent=0, bg=None, level=2),
    "Heading 3": dict(size=13, bold=True, italic=False, color="#1B1040", family=None, before=12, after=4, line=108, indent=0, bg=None, level=3),
    "Heading 4": dict(size=11, bold=True, italic=True, color="#1B1040", family=None, before=10, after=3, line=108, indent=0, bg=None, level=4),
    "Quote": dict(size=11, bold=False, italic=True, color="#63596B", family=None, before=6, after=6, line=115, indent=36, bg=None, level=0),
    "Code": dict(size=10, bold=False, italic=False, color="#1B1040", family="mono", before=4, after=4, line=100, indent=0, bg="#EEF2F0", level=0),
}
STYLE_IDS = {"Normal": "Normal", "Title": "Title", "Subtitle": "Subtitle", "Heading 1": "Heading1", "Heading 2": "Heading2",
             "Heading 3": "Heading3", "Heading 4": "Heading4", "Quote": "Quote", "Code": "Code"}
ID_STYLES = {v: k for k, v in STYLE_IDS.items()}


def body_font(size=11):
    f = QFont()
    f.setFamilies(BODY_FAMILIES)
    f.setPointSizeF(size)
    return f


def block_style_name(block_format):
    lvl = block_format.headingLevel()
    if 1 <= lvl <= 4:
        return f"Heading {lvl}"
    n = block_format.property(PROP_STYLE)
    return n if isinstance(n, str) and n in PRESETS else "Normal"


def char_family(f):
    """first font family of a char format ('' when not set); fontFamilies() can crash PySide on unset formats"""
    try:
        if f.hasProperty(QTextFormat.FontFamilies):
            v = f.property(QTextFormat.FontFamilies)
            if isinstance(v, (list, tuple)) and v:
                return str(v[0])
            if isinstance(v, str):
                return v
        if f.hasProperty(QTextFormat.FontFamily):
            return str(f.property(QTextFormat.FontFamily) or "")
    except Exception:
        pass
    return ""
