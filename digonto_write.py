#!/usr/bin/env python3
"""Digonto Write - word processor: DOCX, ODT, HTML, Markdown, PDF. PySide6 only."""
import datetime
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

from PySide6.QtCore import QMarginsF, QRectF, QSizeF, Qt, QTimer, QUrl
from PySide6.QtGui import (QAction, QColor, QFont, QFontDatabase, QImage, QKeySequence, QPageLayout, QPageSize, QPainter, QPdfWriter, QTextBlockFormat,
                           QTextCharFormat, QTextCursor, QTextDocument, QTextDocumentWriter, QTextFormat, QTextFrameFormat, QTextLength, QTextListFormat,
                           QTextTableFormat)
from PySide6.QtWidgets import (QApplication, QColorDialog, QComboBox, QDialog, QDockWidget, QFileDialog, QFontComboBox, QFormLayout, QHBoxLayout, QInputDialog,
                               QLabel, QListWidget, QListWidgetItem, QMainWindow, QMenu, QMessageBox, QPushButton, QSlider, QSpinBox, QToolBar, QToolButton,
                               QVBoxLayout, QWidget, QCheckBox, QStackedWidget)

import digonto_ui as ui
import digonto_office as office
from writekit import __version__ as VERSION
from writekit import common as K
from writekit import ddoc, docx, odt
from writekit.spell import Speller
from writekit.editor import FindReplace, PageSetup, PageView
from writekit.icons import icon

APP_NAME = "Digonto Write"
SLUG = "digonto-write"
OPEN_FILTER = "Documents (*.docx *.ddoc *.odt *.html *.htm *.md *.markdown *.txt);;Word document (*.docx);;Digonto document (*.ddoc);;OpenDocument text (*.odt);;Web page (*.html *.htm);;Markdown (*.md *.markdown);;Text (*.txt);;All files (*)"
SIZES = [8, 9, 10, 10.5, 11, 12, 14, 16, 18, 20, 24, 28, 32, 36, 48, 72]


def mk_action(win, text, fn, shortcut=None, icon_name=None, tip=None, checkable=False):
    a = QAction(text, win)
    if shortcut:
        a.setShortcut(shortcut)
    if icon_name:
        a.setIcon(icon(icon_name))
    a.setToolTip(tip or text)
    a.setStatusTip(tip or text)
    a.setCheckable(checkable)
    a.triggered.connect(lambda checked=False: fn())
    win.addAction(a)
    return a


class WriteWindow(QMainWindow):
    def __init__(self, path=None):
        super().__init__()
        self.page = K.Page()
        self.path = None
        self.meta = {"title": "", "author": ""}
        self.find_dlg = None
        self._sync = False
        self.speller = Speller("en")
        self.spell_on = True
        self._spell_cache = {}
        self._spell_hits = []
        self.spell_timer = QTimer(self)
        self.spell_timer.setSingleShot(True)
        self.spell_timer.timeout.connect(self.refresh_spelling)
        self.view = PageView(self)
        self.editor = self.view.editor
        self.setWindowIcon(ui.app_icon(HERE, SLUG))
        self.new_document(first=True)
        self.build_actions()
        self.build_menu()
        central = QWidget()
        cl = QVBoxLayout(central)
        cl.setContentsMargins(0, 0, 0, 0)
        cl.setSpacing(0)
        cl.addWidget(ui.make_header(APP_NAME, "Word processor: DOCX, ODT, HTML, Markdown, PDF", ui.app_icon(HERE, SLUG), self.about))
        self.tb1, self.tb2 = self.make_toolbar(), self.make_toolbar()
        self.work = QWidget()
        wl = QVBoxLayout(self.work)
        wl.setContentsMargins(0, 0, 0, 0)
        wl.setSpacing(0)
        wl.addWidget(self.tb1)
        wl.addWidget(self.tb2)
        self.build_toolbars()
        wl.addWidget(self.view, 1)
        self.start = ui.StartScreen(
            "Letters, reports and documents - DOCX, ODT, HTML, Markdown and PDF",
            [("Blank document", "new", self.start_new, True), ("Open …", "open", self.file_open, False)],
            "or drop a document here", lambda: [r["path"] for r in office.recent_files(SLUG)], self.open_path)
        self.stack = QStackedWidget()
        self.stack.addWidget(self.start)
        self.stack.addWidget(self.work)
        self.rail = ui.Rail(
            [("new", "new", "New document (Ctrl+N)", self.start_new),
             ("open", "open", "Open (Ctrl+O)", self.file_open),
             ("save", "save", "Save (Ctrl+S)", self.file_save),
             ("export", "export", "Save as / export", self.rail_export),
             ("print", "print", "Print (Ctrl+P)", self.print_doc),
             None,
             ("find", "search", "Find and replace (Ctrl+F)", lambda: self.show_find(False)),
             ("nav", "pages", "Navigation pane - headings of the document (Ctrl+F10)", self.a_nav.trigger)],
            [("settings", "settings", "Settings and help", self.rail_settings)])
        body = QHBoxLayout()
        body.setSpacing(0)
        body.addWidget(self.rail)
        body.addWidget(self.stack, 1)
        cl.addLayout(body, 1)
        self.setCentralWidget(central)
        self.build_status()
        self.build_nav()
        self.connect_signals()
        self.view.apply_page()
        self.update_title()
        self.spell_timer.start(300)
        ui.fit_window(self, 1180, 860)
        self.show_start()
        QTimer.singleShot(0, self.view.fit_width_soft if hasattr(self.view, "fit_width_soft") else self.initial_zoom)
        if path and os.path.isfile(path):
            QTimer.singleShot(0, lambda: self.open_path(path))

    # ------------------------------------------------------------------ start screen
    def rail_export(self):
        m = QMenu(self)
        m.addAction("Save as …", self.file_save_as)
        m.addAction("Export PDF …", self.export_pdf)
        b = self.rail.button("export")
        m.exec(b.mapToGlobal(b.rect().topRight()))

    def rail_settings(self):
        m = QMenu(self)
        m.addAction("Page setup …", self.a_setup.trigger)
        m.addAction("Spelling", self.a_spell.trigger)
        m.addSeparator()
        m.addAction("Keyboard shortcuts", lambda: ui.show_all_shortcuts(self, APP_NAME))
        m.addAction("About Digonto Write", self.about)
        b = self.rail.button("settings")
        m.exec(b.mapToGlobal(b.rect().topRight()))

    def _rail_state(self, editing):
        self.rail.set_enabled(["save", "export", "print", "find", "nav"], editing)

    def show_start(self):
        self.start.refresh()
        self._rail_state(False)
        self.stack.setCurrentWidget(self.start)
        self.statusBar().setVisible(False)
        self.setWindowTitle(APP_NAME)

    def show_editor(self):
        self._rail_state(True)
        self.stack.setCurrentWidget(self.work)
        self.statusBar().setVisible(True)
        self.update_title()
        QTimer.singleShot(0, self.initial_zoom)
        self.editor.setFocus()

    def on_start(self):
        return hasattr(self, "stack") and self.stack.currentWidget() is self.start

    def start_new(self):
        self.page = K.Page()
        self.path = None
        self.new_document()
        self.view.apply_page()
        self.show_editor()

    def close_document(self):
        if not self.maybe_save():
            return
        self.path = None
        self.page = K.Page()
        self.new_document()
        self.view.apply_page()
        self.show_start()

    def initial_zoom(self):
        self.view.set_zoom(1.0 if self.view.viewport().width() > self.page.paper_px()[0] + 60 else (self.view.viewport().width() - 40) / self.page.paper_px()[0])
        self.zoom_slider.setValue(int(self.view.zoom * 100))

    # ------------------------------------------------------------------ document
    def new_document(self, first=False):
        doc = QTextDocument()
        doc.setDefaultFont(K.body_font(11))
        doc.setDocumentMargin(0)
        doc.setDefaultStyleSheet("")
        doc.setUndoRedoEnabled(True)
        cur = QTextCursor(doc)
        cur.setBlockFormat(self.preset_block("Normal"))
        cur.setBlockCharFormat(self.preset_char("Normal"))
        self.set_doc(doc, first)
        doc.setModified(False)

    def set_doc(self, doc, first=False):
        old = self.editor.document() if not first or True else None
        self.editor.setDocument(doc)
        doc.setParent(self.editor)
        lay = doc.documentLayout()
        lay.documentSizeChanged.connect(lambda s: (self.view.relayout(), self.update_stats()))
        doc.contentsChanged.connect(self.on_changed)
        doc.modificationChanged.connect(lambda m: self.update_title())
        if not first:
            self.view.apply_page()
            self.update_stats()
            self.refresh_nav()

    def preset_block(self, name):
        p = K.PRESETS[name]
        bf = QTextBlockFormat()
        bf.setTopMargin(K.pt_px(p["before"]))
        bf.setBottomMargin(K.pt_px(p["after"]))
        bf.setLineHeight(float(p["line"]), QTextBlockFormat.LineHeightTypes.ProportionalHeight.value)
        bf.setLeftMargin(K.pt_px(p["indent"]))
        if p["level"]:
            bf.setHeadingLevel(p["level"])
        elif name != "Normal":
            bf.setProperty(K.PROP_STYLE, name)
        if p["bg"]:
            bf.setBackground(QColor(p["bg"]))
        return bf

    def preset_char(self, name):
        p = K.PRESETS[name]
        cf = QTextCharFormat()
        cf.setFontPointSize(p["size"])
        cf.setFontWeight(700 if p["bold"] else 400)
        cf.setFontItalic(p["italic"])
        if p["color"]:
            cf.setForeground(QColor(p["color"]))
        if p["family"] == "mono":
            cf.setFontFamilies(K.MONO_FAMILIES)
        return cf

    # ------------------------------------------------------------------ actions
    def build_actions(self):
        A = lambda *a, **k: mk_action(self, *a, **k)
        self.a_new = A("New", self.file_new, QKeySequence.New, "new")
        self.a_open = A("Open...", self.file_open, QKeySequence.Open, "open")
        self.a_save = A("Save", self.file_save, QKeySequence.Save, "save")
        self.a_saveas = A("Save as...", self.file_save_as, "Ctrl+Shift+S")
        self.a_pdf = A("Export PDF...", self.export_pdf, "Ctrl+Shift+E", "pdf")
        self.a_print = A("Print...", self.print_doc, QKeySequence.Print, "print")
        self.a_setup = A("Page setup...", self.page_setup)
        self.a_undo = A("Undo", self.editor.undo, QKeySequence.Undo, "undo")
        self.a_redo = A("Redo", self.editor.redo, QKeySequence.Redo, "redo")
        self.a_cut = A("Cut", self.editor.cut, QKeySequence.Cut)
        self.a_copy = A("Copy", self.editor.copy, QKeySequence.Copy)
        self.a_paste = A("Paste", self.editor.paste, QKeySequence.Paste)
        self.a_all = A("Select all", self.editor.selectAll, QKeySequence.SelectAll)
        self.a_find = A("Find...", lambda: self.show_find(False), QKeySequence.Find, "find")
        self.a_replace = A("Replace...", lambda: self.show_find(True), "Ctrl+H")
        self.a_bold = A("Bold", lambda: self.toggle_char("b"), "Ctrl+B", "bold", checkable=True)
        self.a_italic = A("Italic", lambda: self.toggle_char("i"), "Ctrl+I", "italic", checkable=True)
        self.a_under = A("Underline", lambda: self.toggle_char("u"), "Ctrl+U", "underline", checkable=True)
        self.a_strike = A("Strikethrough", lambda: self.toggle_char("s"), None, "strike", checkable=True)
        self.a_sub = A("Subscript", lambda: self.set_valign(QTextCharFormat.AlignSubScript), "Ctrl+,", "sub", checkable=True)
        self.a_sup = A("Superscript", lambda: self.set_valign(QTextCharFormat.AlignSuperScript), "Ctrl+.", "sup", checkable=True)
        self.a_left = A("Align left", lambda: self.align(Qt.AlignLeft), "Ctrl+L", "alignl", checkable=True)
        self.a_center = A("Center", lambda: self.align(Qt.AlignHCenter), "Ctrl+E", "alignc", checkable=True)
        self.a_right = A("Align right", lambda: self.align(Qt.AlignRight), "Ctrl+R", "alignr", checkable=True)
        self.a_just = A("Justify", lambda: self.align(Qt.AlignJustify), "Ctrl+J", "justify", checkable=True)
        self.a_bullets = A("Bulleted list", lambda: self.toggle_list(QTextListFormat.ListDisc), "Ctrl+Shift+8", "bullets", checkable=True)
        self.a_numbers = A("Numbered list", lambda: self.toggle_list(QTextListFormat.ListDecimal), "Ctrl+Shift+7", "numbers", checkable=True)
        self.a_indent = A("Increase indent", lambda: self.change_indent(1), "Ctrl+]", "indent")
        self.a_outdent = A("Decrease indent", lambda: self.change_indent(-1), "Ctrl+[", "outdent")
        self.a_color = A("Text color", self.pick_color, None, "textcolor")
        self.a_hilite = A("Highlight", self.pick_highlight, None, "highlight")
        self.a_clear = A("Clear formatting", self.clear_format, "Ctrl+Space", "clear")
        self.a_image = A("Picture...", self.insert_image, None, "image")
        self.a_table = A("Table...", self.insert_table, None, "table")
        self.a_link = A("Link...", self.insert_link, "Ctrl+K", "link")
        self.a_break = A("Page break", self.insert_break, "Ctrl+Return", "pagebreak")
        self.a_hr = A("Horizontal line", self.insert_hr)
        self.a_date = A("Date and time", self.insert_date)
        self.a_nav = A("Navigation pane", lambda: self.nav.setVisible(not self.nav.isVisible()), "Ctrl+F10", "navpane")
        self.a_fit = A("Fit width", lambda: (self.view.fit_width(), self.zoom_slider.setValue(int(self.view.zoom * 100))))
        self.a_100 = A("Zoom 100 %", lambda: self.zoom_to(100), "Ctrl+0")
        self.a_in = A("Zoom in", lambda: self.zoom_to(self.view.zoom * 100 * 1.15), "Ctrl+=")
        self.a_out = A("Zoom out", lambda: self.zoom_to(self.view.zoom * 100 / 1.15), "Ctrl+-")
        self.a_props = A("Document properties...", self.doc_props)
        self.a_grow = A("Grow font", lambda: self.bump_size(1), "Ctrl+Shift+.")
        self.a_shrink = A("Shrink font", lambda: self.bump_size(-1), "Ctrl+Shift+,")
        self.a_copyfmt = A("Copy format", self.copy_format, "Ctrl+Shift+C")
        self.a_pastefmt = A("Paste format", self.paste_format, "Ctrl+Shift+V")
        self.a_marks = A("Formatting marks", self.toggle_marks, None, checkable=True)
        self.a_spell = A("Check spelling as you type (English)", self.toggle_spell, None, checkable=True)
        self.a_spell.setChecked(True)
        self.a_nextspell = A("Go to next misspelled word", self.next_misspelling, "F7")
        self.a_wc = A("Word count...", self.word_count)

    def build_menu(self):
        mb = self.menuBar()
        self.a_close = mk_action(self, "Close project", self.close_document, "Ctrl+W")
        ui.file_menu(self, extra=[self.a_new, self.a_open, self.a_save, self.a_saveas, self.a_pdf, self.a_setup, self.a_print, self.a_wc, self.a_props], before_exit=[self.a_close])
        m = mb.addMenu("Edit")
        for a in (self.a_undo, self.a_redo, None, self.a_cut, self.a_copy, self.a_paste, self.a_all, None, self.a_find, self.a_replace):
            m.addAction(a) if a else m.addSeparator()
        m = mb.addMenu("View")
        for a in (self.a_nav, self.a_marks, self.a_spell, self.a_nextspell, None, self.a_fit, self.a_100, self.a_in, self.a_out):
            m.addAction(a) if a else m.addSeparator()
        m = mb.addMenu("Insert")
        for a in (self.a_image, self.a_table, self.a_link, self.a_break, self.a_hr, self.a_date):
            m.addAction(a)
        m = mb.addMenu("Format")
        for a in (self.a_bold, self.a_italic, self.a_under, self.a_strike, self.a_sub, self.a_sup, None, self.a_left, self.a_center, self.a_right, self.a_just, None,
                  self.a_bullets, self.a_numbers, self.a_indent, self.a_outdent, None, self.a_grow, self.a_shrink, self.a_copyfmt, self.a_pastefmt, None, self.a_clear):
            m.addAction(a) if a else m.addSeparator()
        cm = m.addMenu("Change case")
        for t, fn in (("UPPERCASE", str.upper), ("lowercase", str.lower), ("Title Case", str.title), ("Sentence case", lambda x: x[:1].upper() + x[1:].lower())):
            cm.addAction(t, lambda fn=fn: self.change_case(fn))
        sp = m.addMenu("Line spacing")
        for v in (1.0, 1.15, 1.5, 2.0, 2.5, 3.0):
            sp.addAction(f"{v}", lambda v=v: self.line_spacing(v))
        m = mb.addMenu("Table")
        for t, fn in (("Insert row above", lambda: self.table_op("row_above")), ("Insert row below", lambda: self.table_op("row_below")),
                      ("Insert column left", lambda: self.table_op("col_left")), ("Insert column right", lambda: self.table_op("col_right")), (None, None),
                      ("Delete row", lambda: self.table_op("del_row")), ("Delete column", lambda: self.table_op("del_col")), ("Delete table", lambda: self.table_op("del_table")),
                      (None, None), ("Merge cells", lambda: self.table_op("merge")), ("Split cell", lambda: self.table_op("split")),
                      ("Toggle borders", lambda: self.table_op("borders")), ("Shade cell...", lambda: self.table_op("shade"))):
            m.addAction(t, fn) if t else m.addSeparator()
        m = mb.addMenu("Help")
        m.addAction("About", self.about)

    def make_toolbar(self):
        tb = QToolBar()
        tb.setMovable(False)
        tb.setIconSize(tb.iconSize().__class__(20, 20))
        tb.setStyleSheet("QToolBar{background:#F3F8F5; border-bottom:1px solid #DCD4E3; spacing:2px; padding:2px 6px;} QToolButton{padding:3px; border-radius:4px;}"
                         "QToolButton:hover{background:#E6DAEF;} QToolButton:checked{background:#D3BBE6;}")
        return tb

    def build_toolbars(self):
        t1, t2 = self.tb1, self.tb2
        for a in (self.a_undo, self.a_redo):
            t1.addAction(a)
        t1.addSeparator()
        self.style_box = QComboBox()
        self.style_box.addItems(list(K.PRESETS))
        self.style_box.setMinimumWidth(110)
        self.style_box.activated.connect(lambda i: self.apply_style(self.style_box.itemText(i)))
        t1.addWidget(self.style_box)
        self.font_box = QFontComboBox()
        self.font_box.setMaximumWidth(190)
        self.font_box.activated.connect(lambda i: self.merge_char(lambda f: f.setFontFamilies([self.font_box.currentFont().family()])))
        t1.addWidget(self.font_box)
        self.size_box = QComboBox()
        self.size_box.setEditable(True)
        self.size_box.addItems([str(s).rstrip("0").rstrip(".") if isinstance(s, float) else str(s) for s in SIZES])
        self.size_box.setMaximumWidth(70)
        self.size_box.activated.connect(lambda i: self.set_size(self.size_box.currentText()))
        self.size_box.lineEdit().returnPressed.connect(lambda: self.set_size(self.size_box.currentText()))
        t1.addWidget(self.size_box)
        t1.addSeparator()
        for a in (self.a_bold, self.a_italic, self.a_under, self.a_strike, self.a_sub, self.a_sup, self.a_color, self.a_hilite, self.a_clear):
            t1.addAction(a)
        for a in (self.a_left, self.a_center, self.a_right, self.a_just):
            t2.addAction(a)
        t2.addSeparator()
        for a in (self.a_bullets, self.a_numbers, self.a_outdent, self.a_indent):
            t2.addAction(a)
        sp = QToolButton()
        sp.setIcon(icon("spacing"))
        sp.setToolTip("Line spacing")
        sp.setPopupMode(QToolButton.InstantPopup)
        mn = QMenu(sp)
        for v in (1.0, 1.15, 1.5, 2.0, 2.5, 3.0):
            mn.addAction(f"{v}", lambda v=v: self.line_spacing(v))
        mn.addSeparator()
        mn.addAction("Space before paragraph...", lambda: self.para_space(True))
        mn.addAction("Space after paragraph...", lambda: self.para_space(False))
        sp.setMenu(mn)
        t2.addWidget(sp)
        t2.addSeparator()
        for a in (self.a_image, self.a_table, self.a_link, self.a_break, self.a_nav):
            t2.addAction(a)
        tm = QToolButton()
        tm.setText("Table tools")
        tm.setPopupMode(QToolButton.InstantPopup)
        tmm = QMenu(tm)
        for t, op in (("Row above", "row_above"), ("Row below", "row_below"), ("Column left", "col_left"), ("Column right", "col_right"), ("Delete row", "del_row"),
                      ("Delete column", "del_col"), ("Merge cells", "merge"), ("Split cell", "split"), ("Toggle borders", "borders"), ("Shade cell...", "shade"),
                      ("Delete table", "del_table")):
            tmm.addAction(t, lambda op=op: self.table_op(op))
        tm.setMenu(tmm)
        t2.addWidget(tm)

    def build_status(self):
        sb = self.statusBar()
        self.lbl_stats = QLabel("")
        self.lbl_page = QLabel("")
        sb.addWidget(self.lbl_page)
        sb.addWidget(self.lbl_stats, 1)
        self.zoom_slider = QSlider(Qt.Horizontal)
        self.zoom_slider.setRange(25, 300)
        self.zoom_slider.setValue(100)
        self.zoom_slider.setFixedWidth(150)
        self.zoom_slider.valueChanged.connect(self.zoom_to)
        self.lbl_zoom = QLabel("100 %")
        sb.addPermanentWidget(self.zoom_slider)
        sb.addPermanentWidget(self.lbl_zoom)
        self.view.zoomed.connect(lambda z: self.lbl_zoom.setText(f"{int(z * 100)} %"))

    def build_nav(self):
        self.nav = QDockWidget("Navigation", self)
        self.nav.setObjectName("nav")
        self.nav_list = QListWidget()
        self.nav_list.itemClicked.connect(self.goto_heading)
        self.nav.setWidget(self.nav_list)
        self.addDockWidget(Qt.LeftDockWidgetArea, self.nav)
        self.nav.setMinimumWidth(180)
        self.nav.hide()
        self.nav_timer = QTimer(self)
        self.nav_timer.setSingleShot(True)
        self.nav_timer.timeout.connect(self.refresh_nav)

    def connect_signals(self):
        self.editor.cursorPositionChanged.connect(self.sync_ui)
        self.editor.selectionChanged.connect(self.sync_ui)
        self.editor.currentCharFormatChanged.connect(lambda f: self.sync_ui())
        self.editor.cursorPositionChanged.connect(lambda: QTimer.singleShot(0, self.view.ensure_cursor_visible))

    # ------------------------------------------------------------------ state
    # ---- spelling (English)
    def refresh_spelling(self):
        from PySide6.QtWidgets import QTextEdit
        hits = []
        sels = []
        if self.spell_on:
            self.speller.load()
            doc = self.editor.document()
            fmt = QTextCharFormat()
            fmt.setUnderlineStyle(QTextCharFormat.SpellCheckUnderline)
            fmt.setUnderlineColor(QColor("#D93025"))
            b = doc.begin()
            seen = {}
            while b.isValid():
                text = b.text()
                if text.strip() and K.block_style_name(b.blockFormat()) != "Code":
                    key = text
                    if key not in self._spell_cache:
                        self._spell_cache[key] = self.speller.check_text(text)
                    seen[key] = self._spell_cache[key]
                    for st, ln in seen[key]:
                        c = QTextCursor(b)
                        c.setPosition(b.position() + st)
                        c.setPosition(b.position() + st + ln, QTextCursor.KeepAnchor)
                        if c.charFormat().isAnchor():
                            continue
                        sel = QTextEdit.ExtraSelection()
                        sel.cursor = c
                        sel.format = fmt
                        sels.append(sel)
                        hits.append(b.position() + st)
                b = b.next()
            if len(self._spell_cache) > 5000:
                self._spell_cache = seen
        self._spell_hits = hits
        self.editor.setExtraSelections(sels)

    def misspelled_at(self, cur):
        b = cur.block()
        pos = cur.position() - b.position()
        for st, ln in self.speller.check_text(b.text()):
            if st <= pos <= st + ln:
                return b.text()[st:st + ln], b.position() + st, ln
        return None

    def replace_range(self, start, length, text):
        c = QTextCursor(self.editor.document())
        c.setPosition(start)
        c.setPosition(start + length, QTextCursor.KeepAnchor)
        fmt = c.charFormat()
        c.insertText(text, fmt)
        self.refresh_spelling()

    def spell_ignore(self, word, add):
        if add:
            self.speller.add_personal(word)
        else:
            self.speller.ignore.add(word.lower())
        self._spell_cache.clear()
        self.refresh_spelling()

    def toggle_spell(self):
        self.spell_on = self.a_spell.isChecked()
        self.refresh_spelling()
        self.statusBar().showMessage("Spell check " + ("on" if self.spell_on else "off"), 2500)

    def next_misspelling(self):
        if not self.spell_on:
            self.a_spell.setChecked(True)
            self.toggle_spell()
        pos = self.editor.textCursor().selectionEnd()
        nxt = next((h for h in sorted(self._spell_hits) if h >= pos), None)
        if nxt is None and self._spell_hits:
            nxt = min(self._spell_hits)
        if nxt is None:
            self.statusBar().showMessage("No spelling mistakes found.", 3000)
            return
        c = QTextCursor(self.editor.document())
        c.setPosition(nxt)
        c.select(QTextCursor.WordUnderCursor)
        self.editor.setTextCursor(c)
        self.view.ensure_cursor_visible()
        self.editor.setFocus()

    def on_changed(self):
        if self.spell_on:
            self.spell_timer.start(700)
        self.update_stats()
        if self.nav.isVisible():
            self.nav_timer.start(400)

    def update_title(self):
        if self.on_start():
            self.setWindowTitle(APP_NAME)
            return
        name = os.path.basename(self.path) if self.path else "Untitled"
        mod = "*" if self.editor.document().isModified() else ""
        self.setWindowTitle(f"{mod}{name} - {APP_NAME}")

    def update_stats(self):
        doc = self.editor.document()
        text = doc.toPlainText()
        words = len(re.findall(r"\S+", text))
        self.lbl_stats.setText(f"   {words} words   {max(0, len(text))} characters   {max(1, doc.pageCount())} page(s)")
        self.sync_page_label()

    def sync_page_label(self):
        _, ch = self.page.content_px()
        y = self.editor.cursorRect().top()
        self.lbl_page.setText(f"Page {int(y // max(1, ch)) + 1}")

    def sync_ui(self):
        if self._sync:
            return
        self._sync = True
        try:
            cur = self.editor.textCursor()
            f = cur.charFormat()
            self.a_bold.setChecked(f.fontWeight() >= 600)
            self.a_italic.setChecked(f.fontItalic())
            self.a_under.setChecked(f.fontUnderline())
            self.a_strike.setChecked(f.fontStrikeOut())
            va = f.verticalAlignment()
            self.a_sub.setChecked(va == QTextCharFormat.AlignSubScript)
            self.a_sup.setChecked(va == QTextCharFormat.AlignSuperScript)
            al = cur.blockFormat().alignment()
            self.a_center.setChecked(bool(al & Qt.AlignHCenter))
            self.a_right.setChecked(bool(al & Qt.AlignRight))
            self.a_just.setChecked(bool(al & Qt.AlignJustify))
            self.a_left.setChecked(not (al & (Qt.AlignHCenter | Qt.AlignRight | Qt.AlignJustify)))
            lst = cur.currentList()
            st = lst.format().style() if lst else None
            self.a_bullets.setChecked(st in (QTextListFormat.ListDisc, QTextListFormat.ListCircle, QTextListFormat.ListSquare))
            self.a_numbers.setChecked(st in (QTextListFormat.ListDecimal, QTextListFormat.ListLowerAlpha, QTextListFormat.ListUpperAlpha,
                                             QTextListFormat.ListLowerRoman, QTextListFormat.ListUpperRoman))
            self.style_box.setCurrentText(K.block_style_name(cur.blockFormat()))
            fam = K.char_family(f) or K.BODY_FAMILIES[0]
            self.font_box.setCurrentFont(QFont(fam))
            sz = f.fontPointSize() or 11
            self.size_box.setEditText(("%g" % sz))
            self.sync_page_label()
        finally:
            self._sync = False

    def zoom_to(self, pct):
        pct = max(25, min(300, int(pct)))
        self.view.set_zoom(pct / 100.0)
        if self.zoom_slider.value() != pct:
            self.zoom_slider.blockSignals(True)
            self.zoom_slider.setValue(pct)
            self.zoom_slider.blockSignals(False)

    # ------------------------------------------------------------------ formatting
    def merge_char(self, fn):
        cur = self.editor.textCursor()
        f = QTextCharFormat()
        fn(f)
        if not cur.hasSelection():
            cur.select(QTextCursor.WordUnderCursor) if False else None
            self.editor.mergeCurrentCharFormat(f)
        else:
            cur.mergeCharFormat(f)
            self.editor.mergeCurrentCharFormat(f)
        self.editor.setFocus()

    def toggle_char(self, what):
        cur = self.editor.textCursor()
        f = cur.charFormat()
        if what == "b":
            on = f.fontWeight() < 600
            self.merge_char(lambda x: x.setFontWeight(700 if on else 400))
        elif what == "i":
            self.merge_char(lambda x, on=not f.fontItalic(): x.setFontItalic(on))
        elif what == "u":
            self.merge_char(lambda x, on=not f.fontUnderline(): x.setFontUnderline(on))
        elif what == "s":
            self.merge_char(lambda x, on=not f.fontStrikeOut(): x.setFontStrikeOut(on))

    def set_valign(self, va):
        cur = self.editor.textCursor()
        now = cur.charFormat().verticalAlignment()
        self.merge_char(lambda f: f.setVerticalAlignment(QTextCharFormat.AlignNormal if now == va else va))

    def bump_size(self, d):
        cur = self.editor.textCursor()
        sz = cur.charFormat().fontPointSize() or 11
        steps = SIZES
        if d > 0:
            new = next((v for v in steps if v > sz + 0.01), sz + 2)
        else:
            new = next((v for v in reversed(steps) if v < sz - 0.01), max(1, sz - 1))
        self.merge_char(lambda f: f.setFontPointSize(float(new)))

    def copy_format(self):
        cur = self.editor.textCursor()
        self._fmt_clip = (QTextCharFormat(cur.charFormat()), QTextBlockFormat(cur.blockFormat()))
        self.statusBar().showMessage("Format copied - select text and use Paste format (Ctrl+Shift+V)", 4000)

    def paste_format(self):
        if not getattr(self, "_fmt_clip", None):
            return
        cf, bf = self._fmt_clip
        cf = QTextCharFormat(cf)
        cf.setAnchor(False)
        cf.setAnchorHref("")
        cur = self.editor.textCursor()
        cur.beginEditBlock()
        if cur.hasSelection():
            cur.setCharFormat(cf)
        else:
            self.editor.setCurrentCharFormat(cf)
        for b in self.selected_blocks():
            c = QTextCursor(b)
            nb = QTextBlockFormat(b.blockFormat())
            nb.setAlignment(bf.alignment())
            nb.setTopMargin(bf.topMargin())
            nb.setBottomMargin(bf.bottomMargin())
            c.setBlockFormat(nb)
        cur.endEditBlock()

    def change_case(self, fn):
        cur = self.editor.textCursor()
        if not cur.hasSelection():
            cur.select(QTextCursor.WordUnderCursor)
        if not cur.hasSelection():
            return
        start, end = sorted((cur.position(), cur.anchor()))
        doc = self.editor.document()
        cur.beginEditBlock()
        # keep the character formats: replace run by run
        c = QTextCursor(doc)
        for b in self.selected_blocks():
            it = b.begin()
            runs = []
            while not it.atEnd():
                fr = it.fragment()
                it += 1
                a, z = max(start, fr.position()), min(end, fr.position() + fr.length())
                if z > a and not fr.charFormat().isImageFormat():
                    runs.append((a, z, fr.charFormat()))
            for a, z, f in reversed(runs):
                c.setPosition(a)
                c.setPosition(z, QTextCursor.KeepAnchor)
                c.insertText(fn(c.selectedText()), f)
        cur.endEditBlock()

    def toggle_marks(self):
        doc = self.editor.document()
        o = doc.defaultTextOption()
        from PySide6.QtGui import QTextOption
        fl = o.flags()
        flag = QTextOption.ShowTabsAndSpaces | QTextOption.ShowLineAndParagraphSeparators
        o.setFlags(fl | flag if self.a_marks.isChecked() else fl & ~flag)
        doc.setDefaultTextOption(o)

    def word_count(self):
        doc = self.editor.document()
        t = doc.toPlainText()
        cur = self.editor.textCursor()
        sel = cur.selectedText()
        words = len(re.findall(r"\S+", t))
        QMessageBox.information(self, "Word count", f"Pages: {max(1, doc.pageCount())}\nWords: {words}\nCharacters (with spaces): {len(t)}\n"
                                f"Characters (no spaces): {len(re.sub(r'\s', '', t))}\nParagraphs: {doc.blockCount()}"
                                + (f"\n\nSelection: {len(re.findall(r'\S+', sel))} words" if sel else ""))

    def set_size(self, text):
        try:
            v = float(text)
        except ValueError:
            return
        if 1 <= v <= 400:
            self.merge_char(lambda f: f.setFontPointSize(v))

    def pick_color(self):
        c = QColorDialog.getColor(QColor("#000000"), self, "Text color")
        if c.isValid():
            self.merge_char(lambda f: f.setForeground(c))

    def pick_highlight(self):
        c = QColorDialog.getColor(QColor("#FFE66B"), self, "Highlight color (cancel to remove)")
        if c.isValid():
            self.merge_char(lambda f: f.setBackground(c))
        else:
            self.merge_char(lambda f: f.setBackground(Qt.transparent))
            cur = self.editor.textCursor()
            if cur.hasSelection():
                cf = QTextCharFormat()
                cf.clearBackground()
                cur.mergeCharFormat(cf)

    def align(self, a):
        self.editor.setAlignment(a)
        self.sync_ui()
        self.editor.setFocus()

    def selected_blocks(self):
        cur = self.editor.textCursor()
        doc = self.editor.document()
        start, end = sorted((cur.position(), cur.anchor()))
        b = doc.findBlock(start)
        out = []
        while b.isValid() and b.position() <= end:
            out.append(b)
            b = b.next()
        return out

    def apply_style(self, name):
        cur = self.editor.textCursor()
        cur.beginEditBlock()
        pr = K.PRESETS[name]
        for b in self.selected_blocks():
            c = QTextCursor(b)
            old = b.blockFormat()
            nf = self.preset_block(name)
            nf.setAlignment(old.alignment())
            if b.textList() is not None:
                nf.setLeftMargin(old.leftMargin())
            c.setBlockFormat(nf)
            c.select(QTextCursor.BlockUnderCursor) if False else None
            c.setPosition(b.position())
            c.setPosition(b.position() + max(0, b.length() - 1), QTextCursor.KeepAnchor)
            cf = self.preset_char(name)
            # keep character-level family / size choices of body text only for Normal
            c.mergeCharFormat(cf)
            c.setBlockCharFormat(cf)
        cur.endEditBlock()
        self.editor.setFocus()
        self.refresh_nav()

    def clear_format(self):
        cur = self.editor.textCursor()
        if cur.hasSelection():
            cur.beginEditBlock()
            sel = QTextCursor(cur)
            start, end = sorted((cur.position(), cur.anchor()))
            doc = self.editor.document()
            for b in self.selected_blocks():
                name = K.block_style_name(b.blockFormat())
                c = QTextCursor(doc)
                c.setPosition(max(start, b.position()))
                c.setPosition(min(end, b.position() + b.length() - 1), QTextCursor.KeepAnchor)
                c.setCharFormat(self.preset_char(name))
            cur.endEditBlock()
        else:
            self.editor.setCurrentCharFormat(self.preset_char(K.block_style_name(cur.blockFormat())))
        self.editor.setFocus()

    def line_spacing(self, v):
        cur = self.editor.textCursor()
        cur.beginEditBlock()
        for b in self.selected_blocks():
            c = QTextCursor(b)
            bf = b.blockFormat()
            bf.setLineHeight(v * 100.0, QTextBlockFormat.LineHeightTypes.ProportionalHeight.value)
            c.setBlockFormat(bf)
        cur.endEditBlock()

    def para_space(self, before):
        cur = self.editor.textCursor()
        bf = cur.blockFormat()
        v, ok = QInputDialog.getDouble(self, "Paragraph spacing", "Points " + ("before" if before else "after") + " the paragraph:",
                                       K.px_pt(bf.topMargin() if before else bf.bottomMargin()), 0, 200, 1)
        if not ok:
            return
        cur.beginEditBlock()
        for b in self.selected_blocks():
            c = QTextCursor(b)
            f = b.blockFormat()
            (f.setTopMargin if before else f.setBottomMargin)(K.pt_px(v))
            c.setBlockFormat(f)
        cur.endEditBlock()

    def toggle_list(self, style):
        cur = self.editor.textCursor()
        cur.beginEditBlock()
        cur_list = cur.currentList()
        same = cur_list is not None and (style is None or cur_list.format().style() == style)
        for b in self.selected_blocks():
            c = QTextCursor(b)
            lst = b.textList()
            if same or style is None:
                if lst is not None:
                    lst.remove(b)
                    bf = c.blockFormat()
                    bf.setIndent(0)
                    bf.setLeftMargin(0)
                    bf.setTextIndent(0)
                    c.setBlockFormat(bf)
            else:
                lf = QTextListFormat()
                lf.setStyle(style)
                lf.setIndent(lst.format().indent() if lst is not None else 1)
                c.createList(lf)
        cur.endEditBlock()
        self.sync_ui()
        self.editor.setFocus()

    def change_indent(self, d):
        cur = self.editor.textCursor()
        cur.beginEditBlock()
        for b in self.selected_blocks():
            c = QTextCursor(b)
            lst = b.textList()
            if lst is not None:
                lf = lst.format()
                lvl = max(1, min(9, lf.indent() + d))
                if lvl == lf.indent():
                    continue
                nf = QTextListFormat(lf)
                nf.setIndent(lvl)
                if lvl > 1 and lf.style() == QTextListFormat.ListDisc:
                    nf.setStyle(QTextListFormat.ListCircle if lvl % 3 == 2 else QTextListFormat.ListSquare)
                elif lvl == 1 and lf.style() in (QTextListFormat.ListCircle, QTextListFormat.ListSquare):
                    nf.setStyle(QTextListFormat.ListDisc)
                c.createList(nf)
            else:
                bf = b.blockFormat()
                bf.setLeftMargin(max(0.0, bf.leftMargin() + d * K.pt_px(36)))
                c.setBlockFormat(bf)
        cur.endEditBlock()
        self.sync_ui()

    # ------------------------------------------------------------------ insert
    def insert_qimage(self, img, name=None):
        if img.isNull():
            return
        cw, _ = self.page.content_px()
        w = img.width() * K.dpi() / 96.0
        h = img.height() * K.dpi() / 96.0
        if w > cw:
            h, w = h * cw / w, cw
        res = name or f"img{id(img)}_{self.editor.document().revision()}"
        self.editor.document().addResource(QTextDocument.ImageResource, QUrl(res), img)
        from PySide6.QtGui import QTextImageFormat
        f = QTextImageFormat()
        f.setName(res)
        f.setWidth(w)
        f.setHeight(h)
        self.editor.textCursor().insertImage(f)

    def insert_image(self):
        path, _ = QFileDialog.getOpenFileName(self, "Insert picture", "", "Pictures (*.png *.jpg *.jpeg *.gif *.bmp *.webp *.svg);;All files (*)")
        if path:
            img = QImage(path)
            if img.isNull():
                QMessageBox.warning(self, APP_NAME, "This picture could not be opened.")
                return
            self.insert_qimage(img)

    def insert_table(self):
        d = QDialog(self)
        d.setWindowTitle("Insert table")
        f = QFormLayout(d)
        r, c = QSpinBox(), QSpinBox()
        r.setRange(1, 100)
        c.setRange(1, 20)
        r.setValue(3)
        c.setValue(3)
        bd = QCheckBox("Borders")
        bd.setChecked(True)
        f.addRow("Rows", r)
        f.addRow("Columns", c)
        f.addRow(bd)
        ok = ui.primary(QPushButton("Insert"))
        ok.clicked.connect(d.accept)
        f.addRow(ok)
        if d.exec() != QDialog.Accepted:
            return
        self.make_table(r.value(), c.value(), bd.isChecked())

    def make_table(self, rows, cols, border=True):
        tf = QTextTableFormat()
        tf.setBorder(1 if border else 0)
        if border:
            tf.setBorderBrush(QColor("#808080"))
        tf.setCellPadding(4)
        tf.setCellSpacing(0)
        tf.setBorderCollapse(True)
        tf.setWidth(QTextLength(QTextLength.PercentageLength, 100))
        tf.setColumnWidthConstraints([QTextLength(QTextLength.PercentageLength, 100.0 / cols)] * cols)
        cur = self.editor.textCursor()
        cur.beginEditBlock()
        if cur.block().text():
            cur.insertBlock()
        t = cur.insertTable(rows, cols, tf)
        cur.endEditBlock()
        # a paragraph must remain after the table
        last = QTextCursor(self.editor.document())
        last.movePosition(QTextCursor.End)
        if last.currentTable() is not None:
            last.insertBlock()
        c2 = t.cellAt(0, 0).firstCursorPosition()
        self.editor.setTextCursor(c2)

    def table_op(self, op):
        cur = self.editor.textCursor()
        t = cur.currentTable()
        if t is None:
            self.statusBar().showMessage("Put the cursor inside a table first.", 3000)
            return
        cell = t.cellAt(cur)
        r, c = cell.row(), cell.column()
        if op == "row_above":
            t.insertRows(r, 1)
        elif op == "row_below":
            t.insertRows(r + cell.rowSpan(), 1)
        elif op == "col_left":
            t.insertColumns(c, 1)
        elif op == "col_right":
            t.insertColumns(c + cell.columnSpan(), 1)
        elif op == "del_row":
            if t.rows() > 1:
                t.removeRows(r, 1)
            else:
                self.table_op("del_table")
        elif op == "del_col":
            if t.columns() > 1:
                t.removeColumns(c, 1)
            else:
                self.table_op("del_table")
        elif op == "del_table":
            start = t.firstPosition() - 1
            end = t.lastPosition() + 1
            dc = QTextCursor(self.editor.document())
            dc.setPosition(start)
            dc.setPosition(end, QTextCursor.KeepAnchor)
            dc.removeSelectedText()
        elif op == "merge":
            if cur.hasSelection():
                t.mergeCells(cur)
        elif op == "split":
            if cell.rowSpan() > 1 or cell.columnSpan() > 1:
                t.splitCell(r, c, 1, 1)
        elif op == "borders":
            f = t.format()
            f.setBorder(0 if f.border() > 0 else 1)
            f.setBorderBrush(QColor("#808080"))
            t.setFormat(f)
        elif op == "shade":
            col = QColorDialog.getColor(QColor("#EFE7F5"), self, "Cell shading")
            if col.isValid():
                cells = [cell]
                if cur.hasSelection():
                    r0, c0, nr, nc = cur.selectedTableCells()
                    cells = [t.cellAt(rr, cc) for rr in range(r0, r0 + nr) for cc in range(c0, c0 + nc)]
                for ce in cells:
                    cf = ce.format().toTableCellFormat()
                    cf.setBackground(col)
                    ce.setFormat(cf)

    def insert_link(self):
        cur = self.editor.textCursor()
        sel = cur.selectedText()
        url, ok = QInputDialog.getText(self, "Link", "Address (https://...):", text=cur.charFormat().anchorHref() if cur.charFormat().isAnchor() else "https://")
        if not ok:
            return
        if not url.strip() or url.strip() == "https://":
            f = QTextCharFormat()
            f.setAnchor(False)
            f.setFontUnderline(False)
            f.setForeground(QColor("black"))
            cur.mergeCharFormat(f)
            return
        f = QTextCharFormat()
        f.setAnchor(True)
        f.setAnchorHref(url.strip())
        f.setFontUnderline(True)
        f.setForeground(QColor("#0563C1"))
        if cur.hasSelection():
            cur.mergeCharFormat(f)
        else:
            cur.insertText(url.strip(), f)
            cur.insertText(" ", QTextCharFormat())

    def insert_break(self):
        cur = self.editor.textCursor()
        cur.insertBlock()
        bf = cur.blockFormat()
        bf.setPageBreakPolicy(QTextFormat.PageBreakFlag.PageBreak_AlwaysBefore)
        cur.setBlockFormat(bf)

    def insert_hr(self):
        cur = self.editor.textCursor()
        cur.insertHtml("<hr>")

    def insert_date(self):
        self.editor.textCursor().insertText(datetime.datetime.now().strftime("%Y-%m-%d %H:%M"))

    # ------------------------------------------------------------------ find / nav
    def show_find(self, replace):
        if self.find_dlg is None:
            self.find_dlg = FindReplace(self)
        sel = self.editor.textCursor().selectedText()
        if sel:
            self.find_dlg.find.setText(sel)
        self.find_dlg.show()
        self.find_dlg.raise_()
        self.find_dlg.find.setFocus()
        self.find_dlg.find.selectAll()

    def refresh_nav(self):
        self.nav_list.clear()
        b = self.editor.document().begin()
        while b.isValid():
            lvl = b.blockFormat().headingLevel()
            if lvl and b.text().strip():
                it = QListWidgetItem("    " * (lvl - 1) + b.text().strip()[:80])
                it.setData(Qt.UserRole, b.position())
                self.nav_list.addItem(it)
            b = b.next()

    def goto_heading(self, item):
        c = self.editor.textCursor()
        c.setPosition(item.data(Qt.UserRole))
        self.editor.setTextCursor(c)
        self.view.ensure_cursor_visible()
        self.editor.setFocus()

    # ------------------------------------------------------------------ files
    def maybe_save(self):
        if not self.editor.document().isModified():
            return True
        r = QMessageBox.question(self, APP_NAME, "Save changes to this document first?", QMessageBox.Save | QMessageBox.Discard | QMessageBox.Cancel)
        if r == QMessageBox.Cancel:
            return False
        if r == QMessageBox.Save:
            return self.file_save()
        return True

    def file_new(self):
        if not self.on_start() and not self.maybe_save():
            return
        self.start_new()

    def file_open(self):
        if not self.on_start() and not self.maybe_save():
            return
        d = office.OpenDialog(self, SLUG, OPEN_FILTER)
        if d.exec() == QDialog.Accepted and d.path:
            self.open_path(d.path)

    def open_path(self, path):
        ext = os.path.splitext(path)[1].lower()
        try:
            if ext == ".docx":
                doc, page = docx.read_docx(path)
                self.page = page
            elif ext == ".odt":
                doc, page = odt.read_odt(path)
                self.page = page
            elif ext == ".ddoc":
                doc, page = ddoc.read_ddoc(path)
                self.page = page
            else:
                doc = QTextDocument()
                doc.setDefaultFont(K.body_font(11))
                with open(path, "rb") as fh:
                    raw = fh.read()
                try:
                    text = raw.decode("utf-8-sig")
                except UnicodeDecodeError:
                    text = raw.decode("latin-1")
                if ext in (".html", ".htm"):
                    doc.setBaseUrl(QUrl.fromLocalFile(os.path.dirname(path) + "/"))
                    doc.setHtml(text)
                elif ext in (".md", ".markdown"):
                    doc.setMarkdown(text)
                else:
                    doc.setPlainText(text)
                self.page = K.Page()
            doc.setDefaultFont(K.body_font(11))
        except Exception as e:  # noqa
            QMessageBox.warning(self, APP_NAME, f"This file could not be opened.\n\n{e}")
            return
        self.path = path if ext in (".docx", ".ddoc", ".odt", ".html", ".htm", ".md", ".markdown", ".txt") else None
        self.set_doc(doc)
        doc.setModified(False)
        self.view.apply_page()
        self.initial_zoom()
        self.show_editor()
        self.refresh_nav()
        self.spell_timer.start(300)
        ui.add_recent(SLUG, path)
        self.statusBar().showMessage("Opened " + os.path.basename(path), 4000)
        fams = self.fonts_used(doc)
        if any(not ui.font_installed(x) for x in fams):
            QTimer.singleShot(150, lambda: ui.note_missing_fonts(self, fams))

    @staticmethod
    def fonts_used(doc):
        """every font family the document's text asks for"""
        fams = set()
        b = doc.begin()
        while b.isValid():
            it = b.begin()
            while not it.atEnd():
                fr = it.fragment()
                if fr.isValid():
                    cf = fr.charFormat()
                    fl = cf.fontFamilies() if hasattr(cf, "fontFamilies") else None
                    if fl:
                        fams.add(str(fl[0]))
                    elif cf.fontFamily():
                        fams.add(cf.fontFamily())
                it += 1
            b = b.next()
        return fams

    def file_save(self):
        if not self.path or os.path.splitext(self.path)[1].lower() not in (".docx", ".ddoc", ".html", ".md", ".txt", ".odt"):
            return self.file_save_as()
        return self.write_to(self.path)

    def file_save_as(self):
        path, flt = QFileDialog.getSaveFileName(self, "Save as", self.path or "Untitled.docx",
                                                "Word document (*.docx);;Digonto document (*.ddoc);;OpenDocument text (*.odt);;Web page (*.html);;Markdown (*.md);;Text (*.txt);;PDF (*.pdf)")
        if not path:
            return False
        ext = os.path.splitext(path)[1].lower()
        if not ext:
            ext = {"docx": ".docx", "ddoc": ".ddoc", "odt": ".odt", "html": ".html", "md": ".md", "txt": ".txt", "pdf": ".pdf"}.get(flt.split("*.")[1].split(")")[0], ".docx")
            path += ext
        if ext == ".pdf":
            return self.write_pdf(path)
        ok = self.write_to(path)
        if ok and ext in (".docx", ".ddoc", ".html", ".md", ".txt", ".odt"):
            self.path = path
            self.update_title()
        return ok

    def write_to(self, path):
        ext = os.path.splitext(path)[1].lower()
        doc = self.editor.document()
        try:
            if ext == ".docx":
                docx.write_docx(doc, path, self.page, self.meta)
            elif ext == ".ddoc":
                ddoc.write_ddoc(doc, path, self.page, self.meta)
            elif ext == ".odt":
                w = QTextDocumentWriter(path, b"odf")
                if not w.write(doc):
                    raise OSError("Qt could not write ODT")
            elif ext in (".html", ".htm"):
                with open(path, "w", encoding="utf-8") as fh:
                    fh.write(doc.toHtml())
            elif ext in (".md", ".markdown"):
                with open(path, "w", encoding="utf-8") as fh:
                    fh.write(doc.toMarkdown())
            elif ext == ".pdf":
                return self.write_pdf(path)
            else:
                with open(path, "w", encoding="utf-8") as fh:
                    fh.write(doc.toPlainText())
        except Exception as e:  # noqa
            QMessageBox.warning(self, APP_NAME, f"The file could not be saved.\n\n{e}")
            return False
        if ext in (".docx", ".ddoc", ".html", ".htm", ".md", ".markdown", ".txt", ".odt"):
            doc.setModified(False)
        ui.add_recent(SLUG, path)
        self.statusBar().showMessage("Saved " + os.path.basename(path), 4000)
        if ext in (".html", ".md", ".txt"):
            self.statusBar().showMessage("Saved " + os.path.basename(path) + " (this format keeps less layout than DOCX)", 6000)
        return True

    # ------------------------------------------------------------------ pdf / print
    def paint_pages(self, device, resolution):
        """draw every page on a QPagedPaintDevice: same layout as on screen, margins and header / footer per page"""
        doc = self.editor.document()
        pg = self.page
        cw, ch = pg.content_px()
        t, r, b, l = [m * resolution for m in pg.margins]
        scale = resolution / K.dpi()
        n = max(1, doc.pageCount())
        painter = QPainter(device)
        painter.setRenderHint(QPainter.TextAntialiasing, True)
        painter.setRenderHint(QPainter.Antialiasing, True)
        pw_in, ph_in = pg.size_in()
        for i in range(n):
            if i > 0:
                device.newPage()
            painter.save()
            painter.translate(l, t)
            painter.scale(scale, scale)
            painter.setClipRect(QRectF(0, 0, cw, ch))
            painter.translate(0, -i * ch)
            doc.drawContents(painter, QRectF(0, i * ch, cw, ch))
            painter.restore()
            f = K.body_font(9)
            painter.setFont(f)
            painter.setPen(QColor("#555555"))
            if pg.header_on and pg.header:
                painter.drawText(QRectF(l, 0, pw_in * resolution - l - r, t * 0.8), Qt.AlignCenter | Qt.AlignBottom, pg.header.replace("{page}", str(i + 1)).replace("{pages}", str(n)))
            if pg.footer_on and pg.footer:
                painter.drawText(QRectF(l, ph_in * resolution - b * 0.8, pw_in * resolution - l - r, b * 0.8), Qt.AlignCenter | Qt.AlignTop,
                                 pg.footer.replace("{page}", str(i + 1)).replace("{pages}", str(n)))
        painter.end()

    def write_pdf(self, path):
        try:
            w = QPdfWriter(path)
            pw, ph = self.page.size_in()
            w.setPageSize(QPageSize(QSizeF(pw * 25.4, ph * 25.4), QPageSize.Millimeter))
            w.setPageMargins(QMarginsF(0, 0, 0, 0))
            w.setResolution(600)
            w.setTitle(self.meta.get("title") or os.path.basename(path))
            self.paint_pages(w, 600)
        except Exception as e:  # noqa
            QMessageBox.warning(self, APP_NAME, f"The PDF could not be written.\n\n{e}")
            return False
        self.statusBar().showMessage("PDF written: " + os.path.basename(path), 5000)
        return True

    def export_pdf(self):
        base = os.path.splitext(self.path)[0] + ".pdf" if self.path else "Untitled.pdf"
        path, _ = QFileDialog.getSaveFileName(self, "Export PDF", base, "PDF (*.pdf)")
        if path:
            self.write_pdf(path if path.lower().endswith(".pdf") else path + ".pdf")

    def print_doc(self):
        try:
            from PySide6.QtPrintSupport import QPrintDialog, QPrinter
        except ImportError:
            QMessageBox.information(self, APP_NAME, "Printing is not available here. Export a PDF and print that.")
            return
        pr = QPrinter(QPrinter.HighResolution)
        pw, ph = self.page.size_in()
        pr.setPageSize(QPageSize(QSizeF(pw * 25.4, ph * 25.4), QPageSize.Millimeter))
        pr.setPageMargins(QMarginsF(0, 0, 0, 0))
        dlg = QPrintDialog(pr, self)
        if dlg.exec() == QDialog.Accepted:
            self.paint_pages(pr, pr.resolution())

    # ------------------------------------------------------------------ misc
    def page_setup(self):
        d = PageSetup(self)
        if d.exec() == QDialog.Accepted:
            d.apply(self.page)
            self.view.apply_page()
            self.editor.document().setModified(True)
            self.update_stats()
            self.update_title()

    def doc_props(self):
        t, ok = QInputDialog.getText(self, "Document title", "Title:", text=self.meta.get("title", ""))
        if ok:
            self.meta["title"] = t
            a, ok2 = QInputDialog.getText(self, "Author", "Author:", text=self.meta.get("author", ""))
            if ok2:
                self.meta["author"] = a

    def about(self):
        QMessageBox.about(self, "About " + APP_NAME,
                          f"<b>{APP_NAME}</b> {VERSION}<br>Word processor: opens and saves DOCX and ODT, saves HTML, Markdown, text and PDF.<br><br>"
                          "Layout: the sheet on screen is one continuous page with dashed page-break lines. Margins, headers and footers are applied per page in "
                          "PDF, print and DOCX.<br>Spell check: English only.")

    def closeEvent(self, e):
        if self.maybe_save():
            e.accept()
            ui.force_exit_soon()
        else:
            e.ignore()


def main():
    if "--version" in sys.argv:
        print(VERSION)
        return
    ui.mac_app_name(APP_NAME)
    app = QApplication(sys.argv)
    if ui.forward_to_running(SLUG, sys.argv[1:]):
        os._exit(0)
    ui.setup_app(app, APP_NAME, SLUG, ui.app_icon(HERE, SLUG), theme=True)
    path = next((a for a in sys.argv[1:] if os.path.isfile(a)), None)
    w = WriteWindow(path)
    w.show()
    _extra = []

    def _new_window(p):
        x = WriteWindow(p)
        x.show()
        _extra.append(x)
        return x
    ui.serve_single(SLUG, w, _new_window)
    os._exit(app.exec())


if __name__ == "__main__":
    main()
