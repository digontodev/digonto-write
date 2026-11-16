"""Page view (paper sheet + editor + zoom), find/replace and page setup dialogs."""
import math

from PySide6.QtCore import QEvent, QRectF, QSizeF, Qt, Signal
from PySide6.QtGui import QColor, QFont, QPainter, QPen, QTextCursor, QTextDocument
from PySide6.QtWidgets import (QMenu, QCheckBox, QComboBox, QDialog, QDoubleSpinBox, QFormLayout, QGraphicsScene, QGraphicsView, QGridLayout, QHBoxLayout, QLabel,
                               QLineEdit, QPushButton, QTextEdit, QVBoxLayout, QWidget)

from . import common as K


class Editor(QTextEdit):
    def __init__(self, owner):
        super().__init__()
        self.owner = owner
        self.setFrameShape(QTextEdit.NoFrame)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.setAcceptRichText(True)
        self.setTabChangesFocus(False)
        self.setStyleSheet("QTextEdit{background:white; color:#1B1040; selection-background-color:#D3BBE6; selection-color:#1B1040;}")
        self.viewport().setCursor(Qt.IBeamCursor)

    def paintEvent(self, e):
        super().paintEvent(e)
        pg = self.owner.page
        _, ch = pg.content_px()
        p = QPainter(self.viewport())
        pen = QPen(QColor("#C0B5C9"), 1, Qt.DashLine)
        p.setPen(pen)
        n = max(1, self.document().pageCount())
        for i in range(1, n):
            y = int(i * ch)
            p.drawLine(0, y, self.viewport().width(), y)
            p.setPen(QColor("#988BA3"))
            p.drawText(self.viewport().width() - 70, y - 3, f"page {i}")
            p.setPen(pen)
        p.end()

    def keyPressEvent(self, e):
        cur = self.textCursor()
        if e.key() in (Qt.Key_Tab, Qt.Key_Backtab) and cur.currentList() is not None and not (cur.currentTable() and False):
            self.owner.change_indent(1 if e.key() == Qt.Key_Tab else -1)
            return
        if e.key() == Qt.Key_Backspace and cur.currentList() is not None and cur.atBlockStart() and not cur.hasSelection() and cur.block().text() == "":
            self.owner.toggle_list(None)
            return
        super().keyPressEvent(e)

    def contextMenuEvent(self, e):
        owner = self.owner
        menu = self.createStandardContextMenu()
        cur = self.cursorForPosition(e.pos())
        info = owner.misspelled_at(cur) if owner.spell_on else None
        if info:
            word, start, length = info
            first = menu.actions()[0] if menu.actions() else None
            sugg = owner.speller.suggest(word)
            acts = []
            for sg in sugg:
                a = menu.addAction(sg)
                f = a.font()
                f.setBold(True)
                a.setFont(f)
                a.triggered.connect(lambda checked=False, sg=sg, st=start, ln=length: owner.replace_range(st, ln, sg))
                acts.append(a)
            if not sugg:
                a = menu.addAction("(no suggestions)")
                a.setEnabled(False)
                acts.append(a)
            acts.append(menu.addSeparator())
            a = menu.addAction("Ignore")
            a.triggered.connect(lambda: owner.spell_ignore(word, False))
            acts.append(a)
            a = menu.addAction("Add to dictionary")
            a.triggered.connect(lambda: owner.spell_ignore(word, True))
            acts.append(a)
            acts.append(menu.addSeparator())
            for a in acts:
                menu.removeAction(a)
                menu.insertAction(first, a)
        menu.exec(e.globalPos())

    def insertFromMimeData(self, src):
        if src.hasImage() and not src.hasHtml():
            from PySide6.QtGui import QImage
            img = src.imageData()
            if isinstance(img, QImage) and not img.isNull():
                self.owner.insert_qimage(img)
                return
        super().insertFromMimeData(src)

    def canInsertFromMimeData(self, src):
        return src.hasImage() or super().canInsertFromMimeData(src)


class Paper(QWidget):
    """white sheet: margins around the editor, optional header / footer text"""

    def __init__(self, owner, editor):
        super().__init__()
        self.owner = owner
        self.editor = editor
        editor.setParent(self)
        self.setAttribute(Qt.WA_OpaquePaintEvent, True)

    def paintEvent(self, e):
        p = QPainter(self)
        p.fillRect(self.rect(), QColor("white"))
        pg = self.owner.page
        t, r, b, l = [m * K.dpi() for m in pg.margins]
        font = QFont(K.body_font(9))
        p.setFont(font)
        p.setPen(QColor("#83788C"))
        n = max(1, self.editor.document().pageCount())
        if pg.header_on and pg.header:
            p.drawText(QRectF(l, 6, self.width() - l - r, t - 12), Qt.AlignCenter | Qt.AlignBottom, pg.header.replace("{page}", "1").replace("{pages}", str(n)))
        if pg.footer_on and pg.footer:
            p.drawText(QRectF(l, self.height() - b + 6, self.width() - l - r, b - 12), Qt.AlignCenter | Qt.AlignTop, pg.footer.replace("{page}", "1").replace("{pages}", str(n)))
        p.end()


class PageView(QGraphicsView):
    zoomed = Signal(float)

    def __init__(self, owner):
        super().__init__()
        self.owner = owner
        self.scene_ = QGraphicsScene(self)
        self.setScene(self.scene_)
        self.editor = Editor(owner)
        self.paper = Paper(owner, self.editor)
        self.proxy = self.scene_.addWidget(self.paper)
        self.setBackgroundBrush(QColor("#E2DCE7"))
        self.setFrameShape(QGraphicsView.NoFrame)
        self.setRenderHint(QPainter.TextAntialiasing, True)
        self.setAlignment(Qt.AlignHCenter | Qt.AlignTop)
        self.setViewportUpdateMode(QGraphicsView.FullViewportUpdate)
        self.zoom = 1.0
        self.editor.document().documentLayout().documentSizeChanged.connect(lambda s: self.relayout())

    def apply_page(self):
        pg = self.owner.page
        pw, ph = pg.paper_px()
        cw, ch = pg.content_px()
        doc = self.editor.document()
        doc.setDocumentMargin(0)
        doc.setPageSize(QSizeF(cw, ch))
        self.relayout()

    def relayout(self):
        pg = self.owner.page
        pw, ph = pg.paper_px()
        cw, ch = pg.content_px()
        t, r, b, l = [m * K.dpi() for m in pg.margins]
        doc = self.editor.document()
        pages = max(1, doc.pageCount())
        h = max(ch, doc.size().height())
        # editor holds all pages stacked; the sheet is as tall as the pages need
        eh = int(math.ceil(max(h, pages * ch)))
        self.editor.setGeometry(int(l), int(t), int(cw), eh)
        self.paper.resize(int(pw), int(eh + t + b))
        self.scene_.setSceneRect(-20, -20, pw + 40, eh + t + b + 40)
        self.paper.update()

    def set_zoom(self, z):
        z = max(0.25, min(4.0, z))
        self.zoom = z
        self.resetTransform()
        self.scale(z, z)
        self.zoomed.emit(z)

    def fit_width(self):
        pw, _ = self.owner.page.paper_px()
        self.set_zoom((self.viewport().width() - 40) / pw)

    def wheelEvent(self, e):
        if e.modifiers() & Qt.ControlModifier:
            self.set_zoom(self.zoom * (1.1 if e.angleDelta().y() > 0 else 1 / 1.1))
            e.accept()
        else:
            super().wheelEvent(e)

    def ensure_cursor_visible(self):
        r = self.editor.cursorRect()
        pt = self.editor.mapTo(self.paper, r.center())
        self.ensureVisible(QRectF(self.proxy.mapToScene(pt).x(), self.proxy.mapToScene(pt).y() - 20, 4, 40), 20, 60)


class FindReplace(QDialog):
    def __init__(self, win, replace=False):
        super().__init__(win)
        self.win = win
        self.setWindowTitle("Find and replace")
        self.setWindowFlag(Qt.Tool, True)
        g = QGridLayout(self)
        self.find = QLineEdit()
        self.rep = QLineEdit()
        g.addWidget(QLabel("Find"), 0, 0)
        g.addWidget(self.find, 0, 1, 1, 3)
        g.addWidget(QLabel("Replace with"), 1, 0)
        g.addWidget(self.rep, 1, 1, 1, 3)
        self.case = QCheckBox("Match case")
        self.whole = QCheckBox("Whole words")
        g.addWidget(self.case, 2, 1)
        g.addWidget(self.whole, 2, 2)
        self.msg = QLabel("")
        g.addWidget(self.msg, 3, 0, 1, 4)
        for i, (t, fn) in enumerate((("Find next", lambda: self.go(True)), ("Find previous", lambda: self.go(False)), ("Replace", self.replace_one), ("Replace all", self.replace_all))):
            b = QPushButton(t)
            b.clicked.connect(fn)
            g.addWidget(b, 4, i)
        self.find.returnPressed.connect(lambda: self.go(True))

    def flags(self, forward=True):
        f = QTextDocument.FindFlag(0)
        if self.case.isChecked():
            f |= QTextDocument.FindCaseSensitively
        if self.whole.isChecked():
            f |= QTextDocument.FindWholeWords
        if not forward:
            f |= QTextDocument.FindBackward
        return f

    def go(self, forward=True):
        ed = self.win.editor
        t = self.find.text()
        if not t:
            return False
        if ed.find(t, self.flags(forward)):
            self.msg.setText("")
            self.win.view.ensure_cursor_visible()
            return True
        cur = ed.textCursor()
        cur.movePosition(QTextCursor.Start if forward else QTextCursor.End)
        ed.setTextCursor(cur)
        if ed.find(t, self.flags(forward)):
            self.msg.setText("Continued from the other end of the document.")
            self.win.view.ensure_cursor_visible()
            return True
        self.msg.setText("Not found.")
        return False

    def replace_one(self):
        ed = self.win.editor
        c = ed.textCursor()
        sel = c.selectedText()
        t = self.find.text()
        if sel and ((sel == t) or (not self.case.isChecked() and sel.lower() == t.lower())):
            c.insertText(self.rep.text())
        self.go(True)

    def replace_all(self):
        ed = self.win.editor
        t = self.find.text()
        if not t:
            return
        doc = ed.document()
        cur = QTextCursor(doc)
        cur.beginEditBlock()
        n = 0
        pos = QTextCursor(doc)
        while True:
            found = doc.find(t, pos, self.flags(True))
            if found.isNull():
                break
            found.insertText(self.rep.text())
            pos = found
            n += 1
        cur.endEditBlock()
        self.msg.setText(f"Replaced {n} occurrence{'s' if n != 1 else ''}.")


class PageSetup(QDialog):
    def __init__(self, win):
        super().__init__(win)
        self.setWindowTitle("Page setup")
        pg = win.page
        f = QFormLayout(self)
        self.paper = QComboBox()
        self.paper.addItems(list(K.PAPERS))
        self.paper.setCurrentText(pg.paper)
        self.orient = QComboBox()
        self.orient.addItems(["Portrait", "Landscape"])
        self.orient.setCurrentIndex(1 if pg.landscape else 0)
        f.addRow("Paper", self.paper)
        f.addRow("Orientation", self.orient)
        self.m = []
        for name, v in zip(("Top", "Right", "Bottom", "Left"), pg.margins):
            sp = QDoubleSpinBox()
            sp.setRange(0.2, 4.0)
            sp.setSingleStep(0.1)
            sp.setSuffix(" in")
            sp.setValue(v)
            self.m.append(sp)
            f.addRow(name + " margin", sp)
        self.hon = QCheckBox("Show header")
        self.hon.setChecked(pg.header_on)
        self.header = QLineEdit(pg.header)
        self.fon = QCheckBox("Show footer")
        self.fon.setChecked(pg.footer_on)
        self.footer = QLineEdit(pg.footer)
        f.addRow(self.hon, self.header)
        f.addRow(self.fon, self.footer)
        f.addRow(QLabel("In header / footer, {page} and {pages} become page numbers."))
        row = QHBoxLayout()
        ok, cancel = QPushButton("OK"), QPushButton("Cancel")
        ok.setDefault(True)
        ok.clicked.connect(self.accept)
        cancel.clicked.connect(self.reject)
        row.addStretch()
        row.addWidget(ok)
        row.addWidget(cancel)
        f.addRow(row)

    def apply(self, pg):
        pg.paper = self.paper.currentText()
        pg.landscape = self.orient.currentIndex() == 1
        pg.margins = [s.value() for s in self.m]
        pg.header_on, pg.header = self.hon.isChecked(), self.header.text()
        pg.footer_on, pg.footer = self.fon.isChecked(), self.footer.text()
