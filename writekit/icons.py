"""Small toolbar icons drawn with QPainter (no image files, sharp on every screen)."""
from PySide6.QtCore import QPointF, QRectF, QSize, Qt
from PySide6.QtGui import QColor, QFont, QIcon, QPainter, QPainterPath, QPen, QPixmap, QPolygonF

INK = QColor("#342C3B")
GREEN = QColor("#C2395C")
_cache = {}


def icon(name, color=None, size=22):
    key = (name, color, size)
    if key in _cache:
        return _cache[key]
    s = size * 2
    pm = QPixmap(s, s)
    pm.setDevicePixelRatio(2)
    pm.fill(Qt.transparent)
    p = QPainter(pm)
    p.setRenderHint(QPainter.Antialiasing, True)
    p.scale(size / 22.0, size / 22.0)
    ink = QColor(color) if color else INK
    pen = QPen(ink, 1.6, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin)
    p.setPen(pen)
    p.setBrush(Qt.NoBrush)
    DRAW.get(name, lambda p, ink: None)(p, ink)
    p.end()
    ic = QIcon(pm)
    # disabled look
    _cache[key] = ic
    return ic


def _text(p, ink, t, size=13, bold=True, italic=False, under=False, strike=False, rect=QRectF(0, 0, 22, 22)):
    f = QFont()
    f.setPixelSize(size)
    f.setBold(bold)
    f.setItalic(italic)
    f.setUnderline(under)
    f.setStrikeOut(strike)
    p.setFont(f)
    p.setPen(ink)
    p.drawText(rect, Qt.AlignCenter, t)


def _arrow(p, ink, flip):
    path = QPainterPath()
    path.moveTo(7, 9)
    path.cubicTo(9, 5, 17, 5, 17, 13)
    p.save()
    if flip:
        p.translate(22, 0)
        p.scale(-1, 1)
    p.drawPath(path)
    p.drawLine(QPointF(7, 9), QPointF(7, 4.5))
    p.drawLine(QPointF(7, 9), QPointF(11.5, 9))
    p.restore()


def _lines(p, ink, align):
    ys = [5, 9, 13, 17]
    widths = [14, 9, 14, 9]
    for y, w in zip(ys, widths):
        x = {"l": 4, "c": 11 - w / 2, "r": 18 - w}[align]
        p.drawLine(QPointF(x, y), QPointF(x + w, y))


def _valign(p, ink, where):
    p.drawLine(QPointF(4, {"t": 4, "m": 11, "b": 18}[where]), QPointF(18, {"t": 4, "m": 11, "b": 18}[where]))
    y0 = {"t": 6, "m": 7.5, "b": 5}[where]
    p.drawRect(QRectF(8, y0, 6, 8))


def _borders(p, ink, mode):
    p.setPen(QPen(QColor("#BFB8C4"), 1, Qt.DotLine))
    p.drawRect(QRectF(4, 4, 14, 14))
    p.drawLine(QPointF(11, 4), QPointF(11, 18))
    p.drawLine(QPointF(4, 11), QPointF(18, 11))
    p.setPen(QPen(ink, 2))
    if mode == "all":
        p.drawRect(QRectF(4, 4, 14, 14))
    elif mode == "bottom":
        p.drawLine(QPointF(4, 18), QPointF(18, 18))
    elif mode == "top":
        p.drawLine(QPointF(4, 4), QPointF(18, 4))
    elif mode == "left":
        p.drawLine(QPointF(4, 4), QPointF(4, 18))
    elif mode == "right":
        p.drawLine(QPointF(18, 4), QPointF(18, 18))


def _fillbucket(p, ink):
    p.save()
    p.translate(11, 9)
    p.rotate(-30)
    p.drawRect(QRectF(-5, -4, 9, 8))
    p.restore()
    p.drawLine(QPointF(5, 14), QPointF(9, 19))
    p.setBrush(ink)
    p.drawEllipse(QPointF(17, 13), 1.5, 2.2)


def _chart(p, ink):
    p.setBrush(ink)
    for i, h in enumerate((6, 11, 8, 14)):
        p.drawRect(QRectF(3.5 + i * 4.2, 18 - h, 3, h))


def _filter(p, ink):
    pg = QPolygonF([QPointF(4, 5), QPointF(18, 5), QPointF(12, 12), QPointF(12, 18), QPointF(10, 17), QPointF(10, 12)])
    p.drawPolygon(pg)


def _merge(p, ink):
    p.drawRect(QRectF(3, 6, 16, 10))
    p.drawLine(QPointF(7, 11), QPointF(15, 11))
    p.drawLine(QPointF(7, 11), QPointF(9, 9))
    p.drawLine(QPointF(7, 11), QPointF(9, 13))
    p.drawLine(QPointF(15, 11), QPointF(13, 9))
    p.drawLine(QPointF(15, 11), QPointF(13, 13))


def _wrap(p, ink):
    p.drawLine(QPointF(4, 6), QPointF(18, 6))
    path = QPainterPath()
    path.moveTo(4, 11)
    path.lineTo(15, 11)
    path.cubicTo(19, 11, 19, 16, 15, 16)
    path.lineTo(9, 16)
    p.drawPath(path)
    p.drawLine(QPointF(9, 16), QPointF(11.5, 13.8))
    p.drawLine(QPointF(9, 16), QPointF(11.5, 18.2))


def _freeze(p, ink):
    p.drawRect(QRectF(4, 4, 14, 14))
    p.setPen(QPen(ink, 2.4))
    p.drawLine(QPointF(4, 9), QPointF(18, 9))
    p.drawLine(QPointF(9, 4), QPointF(9, 18))


def _sort(p, ink, desc):
    _text(p, ink, "A", 9, True, rect=QRectF(1, 1, 12, 10))
    _text(p, ink, "Z", 9, True, rect=QRectF(1, 11, 12, 10))
    x = 17
    p.drawLine(QPointF(x, 5), QPointF(x, 17))
    if desc:
        p.drawLine(QPointF(x, 17), QPointF(x - 2.5, 14))
        p.drawLine(QPointF(x, 17), QPointF(x + 2.5, 14))
    else:
        p.drawLine(QPointF(x, 5), QPointF(x - 2.5, 8))
        p.drawLine(QPointF(x, 5), QPointF(x + 2.5, 8))


def _cf(p, ink):
    for i, col in enumerate(("#E06666", "#F6B26B", "#93C47D")):
        p.setBrush(QColor(col))
        p.setPen(Qt.NoPen)
        p.drawRect(QRectF(4, 4 + i * 5, 14, 4.2))


def _find(p, ink):
    p.drawEllipse(QPointF(9.5, 9.5), 5, 5)
    p.drawLine(QPointF(13.3, 13.3), QPointF(18, 18))


def _clear(p, ink):
    p.save()
    p.translate(11, 11)
    p.rotate(-35)
    p.drawRect(QRectF(-7, -4, 14, 8))
    p.drawLine(QPointF(-1, -4), QPointF(-1, 4))
    p.restore()
    p.drawLine(QPointF(5, 19), QPointF(17, 19))


def _decimals(p, ink, more):
    _text(p, ink, ".0", 10, True, rect=QRectF(1, 2, 13, 10))
    _text(p, ink, ".00" if more else ".0", 8, True, rect=QRectF(1, 11, 14, 9))
    p.setPen(QPen(ink, 1.6))
    if more:
        p.drawLine(QPointF(15, 14), QPointF(20, 14))
    p.drawLine(QPointF(15.5, 8), QPointF(20.5, 8))


def _indent(p, ink, out):
    for y in (5, 17):
        p.drawLine(QPointF(4, y), QPointF(18, y))
    for y in (9, 13):
        p.drawLine(QPointF(10, y), QPointF(18, y))
    if out:
        p.drawLine(QPointF(4, 11), QPointF(8, 8.5))
        p.drawLine(QPointF(4, 11), QPointF(8, 13.5))
    else:
        p.drawLine(QPointF(8, 11), QPointF(4, 8.5))
        p.drawLine(QPointF(8, 11), QPointF(4, 13.5))


def _print(p, ink):
    p.drawRect(QRectF(6, 3, 10, 5))
    p.drawRect(QRectF(3.5, 8, 15, 7))
    p.drawRect(QRectF(6, 12, 10, 7))


def _save(p, ink):
    p.drawRect(QRectF(4, 4, 14, 14))
    p.drawRect(QRectF(7, 4, 8, 5))
    p.drawRect(QRectF(7, 12, 8, 6))


def _open(p, ink):
    p.drawPolyline(QPolygonF([QPointF(3, 17), QPointF(3, 6), QPointF(9, 6), QPointF(11, 8), QPointF(17, 8), QPointF(17, 17), QPointF(3, 17)]))


def _new(p, ink):
    p.drawPolyline(QPolygonF([QPointF(5, 3), QPointF(13, 3), QPointF(17, 7), QPointF(17, 19), QPointF(5, 19), QPointF(5, 3)]))
    p.drawLine(QPointF(13, 3), QPointF(13, 7))
    p.drawLine(QPointF(13, 7), QPointF(17, 7))


def _paint_format(p, ink):
    p.drawRect(QRectF(4, 4, 11, 5))
    p.drawLine(QPointF(15, 6.5), QPointF(18, 6.5))
    p.drawLine(QPointF(18, 6.5), QPointF(18, 12))
    p.drawLine(QPointF(18, 12), QPointF(11, 12))
    p.drawLine(QPointF(11, 12), QPointF(11, 14))
    p.drawRect(QRectF(9.5, 14, 3, 5))


DRAW = {
    "undo": lambda p, i: _arrow(p, i, False), "redo": lambda p, i: _arrow(p, i, True),
    "bold": lambda p, i: _text(p, i, "B", 15, True), "italic": lambda p, i: _text(p, i, "I", 15, False, True),
    "underline": lambda p, i: _text(p, i, "U", 14, False, False, True), "strike": lambda p, i: _text(p, i, "S", 14, False, False, False, True),
    "alignl": lambda p, i: _lines(p, i, "l"), "alignc": lambda p, i: _lines(p, i, "c"), "alignr": lambda p, i: _lines(p, i, "r"),
    "valigntop": lambda p, i: _valign(p, i, "t"), "valignmid": lambda p, i: _valign(p, i, "m"), "valignbot": lambda p, i: _valign(p, i, "b"),
    "borders": lambda p, i: _borders(p, i, "all"), "b_all": lambda p, i: _borders(p, i, "all"), "b_bottom": lambda p, i: _borders(p, i, "bottom"),
    "b_top": lambda p, i: _borders(p, i, "top"), "b_left": lambda p, i: _borders(p, i, "left"), "b_right": lambda p, i: _borders(p, i, "right"),
    "b_none": lambda p, i: _borders(p, i, "none"),
    "fill": _fillbucket, "chart": _chart, "filter": _filter, "merge": _merge, "wrap": _wrap, "freeze": _freeze,
    "sortaz": lambda p, i: _sort(p, i, False), "sortza": lambda p, i: _sort(p, i, True), "cf": _cf, "find": _find, "clear": _clear,
    "decmore": lambda p, i: _decimals(p, i, True), "decless": lambda p, i: _decimals(p, i, False),
    "indent": lambda p, i: _indent(p, i, False), "outdent": lambda p, i: _indent(p, i, True),
    "sum": lambda p, i: _text(p, i, "Σ", 17, True), "fx": lambda p, i: _text(p, i, "fx", 13, True, True),
    "percent": lambda p, i: _text(p, i, "%", 15, True), "currency": lambda p, i: _text(p, i, "$", 15, True),
    "comma": lambda p, i: _text(p, i, "9,0", 11, True), "print": _print, "save": _save, "open": _open, "new": _new,
    "paintformat": _paint_format, "textcolor": lambda p, i: _text(p, i, "A", 15, True, rect=QRectF(0, -2, 22, 20)),
    "plus": lambda p, i: (p.drawLine(QPointF(11, 5), QPointF(11, 17)), p.drawLine(QPointF(5, 11), QPointF(17, 11))),
}


# ---- extra icons for the word processor
def _bullets(p, ink):
    for y in (6, 11, 16):
        p.setBrush(ink)
        p.drawEllipse(QRectF(3, y - 1.5, 3, 3))
        p.drawLine(QPointF(9, y), QPointF(19, y))


def _numbers(p, ink):
    for i, y in enumerate((6, 11, 16)):
        _text(p, ink, str(i + 1), size=7, bold=True, rect=QRectF(2, y - 4, 6, 8))
        p.drawLine(QPointF(10, y), QPointF(19, y))


def _justify(p, ink):
    for y in (5, 9, 13, 17):
        p.drawLine(QPointF(3, y), QPointF(19, y))


def _image(p, ink):
    p.drawRect(QRectF(3, 4, 16, 14))
    p.drawLine(QPointF(3, 15), QPointF(8, 10))
    p.drawLine(QPointF(8, 10), QPointF(12, 14))
    p.drawLine(QPointF(12, 14), QPointF(15, 11))
    p.drawLine(QPointF(15, 11), QPointF(19, 15))
    p.drawEllipse(QRectF(13, 6, 3, 3))


def _table(p, ink):
    p.drawRect(QRectF(3, 4, 16, 14))
    p.drawLine(QPointF(3, 9), QPointF(19, 9))
    p.drawLine(QPointF(3, 13.5), QPointF(19, 13.5))
    p.drawLine(QPointF(8.5, 4), QPointF(8.5, 18))
    p.drawLine(QPointF(13.5, 4), QPointF(13.5, 18))


def _link(p, ink):
    p.drawRoundedRect(QRectF(2.5, 8, 10, 6), 3, 3)
    p.drawRoundedRect(QRectF(9.5, 8, 10, 6), 3, 3)


def _pagebreak(p, ink):
    p.drawRect(QRectF(5, 2, 12, 6))
    p.drawRect(QRectF(5, 14, 12, 6))
    pen = QPen(ink, 1.2, Qt.DashLine)
    p.setPen(pen)
    p.drawLine(QPointF(2, 11), QPointF(20, 11))


def _sub(p, ink):
    _text(p, ink, "x", size=12, rect=QRectF(1, 2, 13, 15))
    _text(p, ink, "2", size=8, rect=QRectF(12, 9, 9, 12))


def _sup(p, ink):
    _text(p, ink, "x", size=12, rect=QRectF(1, 6, 13, 15))
    _text(p, ink, "2", size=8, rect=QRectF(12, 1, 9, 12))


def _highlight(p, ink):
    p.setBrush(QColor("#FFE66B"))
    p.setPen(Qt.NoPen)
    p.drawRect(QRectF(3, 15, 16, 5))
    p.setPen(QPen(ink, 1.6, Qt.SolidLine, Qt.RoundCap))
    p.setBrush(Qt.NoBrush)
    p.drawLine(QPointF(7, 12), QPointF(13, 3))
    p.drawLine(QPointF(13, 3), QPointF(16, 6))
    p.drawLine(QPointF(16, 6), QPointF(10, 14))


def _spacing(p, ink):
    p.drawLine(QPointF(10, 3), QPointF(10, 19))
    p.drawLine(QPointF(10, 3), QPointF(7, 6))
    p.drawLine(QPointF(10, 3), QPointF(13, 6))
    p.drawLine(QPointF(10, 19), QPointF(7, 16))
    p.drawLine(QPointF(10, 19), QPointF(13, 16))
    for y in (6, 11, 16):
        p.drawLine(QPointF(14, y), QPointF(20, y))


def _navpane(p, ink):
    p.drawRect(QRectF(3, 4, 16, 14))
    p.drawLine(QPointF(9, 4), QPointF(9, 18))
    for y in (8, 11, 14):
        p.drawLine(QPointF(4.5, y), QPointF(7.5, y))


def _pdf(p, ink):
    p.drawRect(QRectF(5, 3, 12, 16))
    _text(p, ink, "PDF", size=6, rect=QRectF(5, 8, 12, 8))


DRAW.update({"bullets": _bullets, "numbers": _numbers, "justify": _justify, "image": _image, "table": _table, "link": _link,
             "pagebreak": _pagebreak, "sub": _sub, "sup": _sup, "highlight": _highlight, "spacing": _spacing, "navpane": _navpane, "pdf": _pdf})
