"""Start screen (new / open on the left, recent files on the right) and the Open window with tabs - shared by Digonto Write and Digonto Sheets."""
import json
import os
import time

from PySide6.QtCore import QSettings, QSize, Qt, QUrl, Signal
from PySide6.QtGui import QColor, QFont, QPainter
from PySide6.QtWidgets import (QDialog, QFileDialog, QFrame, QHBoxLayout, QLabel, QListWidget, QListWidgetItem, QPushButton, QSizePolicy, QTabWidget,
                               QVBoxLayout, QWidget)

import digonto_ui as ui

GREEN = "#C2395C"


def recent_files(slug, limit=30):
    try:
        with open(os.path.join(ui.base_dir(), "recent.json"), encoding="utf-8") as f:
            items = [r for r in json.load(f) if isinstance(r, dict)]
    except (OSError, ValueError):
        return []
    out = []
    for r in items:
        if r.get("app") == slug and r.get("path") and os.path.isfile(r["path"]):
            out.append(r)
        if len(out) >= limit:
            break
    return out


def clear_recent(slug):
    p = os.path.join(ui.base_dir(), "recent.json")
    try:
        with open(p, encoding="utf-8") as f:
            items = [r for r in json.load(f) if isinstance(r, dict) and r.get("app") != slug]
        with open(p, "w", encoding="utf-8") as f:
            json.dump(items, f)
    except (OSError, ValueError):
        pass


def ago(t):
    d = time.time() - t
    if d < 90:
        return "just now"
    if d < 3600:
        return f"{int(d // 60)} min ago"
    if d < 86400:
        return f"{int(d // 3600)} h ago"
    return time.strftime("%d %b %Y", time.localtime(t))


class Tile(QFrame):
    clicked = Signal()

    def __init__(self, glyph, title, text):
        super().__init__()
        self.setObjectName("tile")
        self.setCursor(Qt.PointingHandCursor)
        self.setFixedSize(230, 150)
        self.setStyleSheet("#tile{background:white; border:1px solid #DDD3E9; border-radius:12px;} #tile:hover{border:1px solid #C2395C; background:#F7FCF9;}")
        v = QVBoxLayout(self)
        v.setContentsMargins(18, 14, 18, 14)
        g = QLabel(glyph)
        g.setStyleSheet(f"font-size:34px; font-weight:300; color:{GREEN};")
        t = QLabel(title)
        t.setStyleSheet("font-size:15px; font-weight:700; color:#1B1040;")
        d = QLabel(text)
        d.setWordWrap(True)
        d.setStyleSheet("font-size:12px; color:#65596E;")
        for w in (g, t, d):
            w.setAttribute(Qt.WA_TransparentForMouseEvents, True)
        v.addWidget(g)
        v.addWidget(t)
        v.addWidget(d, 1)

    def mousePressEvent(self, e):
        if e.button() == Qt.LeftButton:
            self.clicked.emit()


class StartScreen(QWidget):
    """3/4: what to do (tiles)   1/4: recent files"""
    open_recent = Signal(str)

    def __init__(self, slug, title, subtitle, tiles):
        super().__init__()
        self.slug = slug
        self.setStyleSheet("StartScreen{background:#F6F2FA;}")
        self.setAttribute(Qt.WA_StyledBackground, True)
        h = QHBoxLayout(self)
        h.setContentsMargins(28, 24, 28, 20)
        h.setSpacing(24)
        left = QVBoxLayout()
        t = QLabel(title)
        t.setStyleSheet("font-size:26px; font-weight:700; color:#1B1040;")
        st = QLabel(subtitle)
        st.setStyleSheet("font-size:13px; color:#65596E;")
        left.addWidget(t)
        left.addWidget(st)
        left.addSpacing(18)
        row = QHBoxLayout()
        row.setSpacing(16)
        for glyph, ttl, text, cb in tiles:
            tile = Tile(glyph, ttl, text)
            tile.clicked.connect(cb)
            row.addWidget(tile)
        row.addStretch(1)
        left.addLayout(row)
        left.addStretch(1)
        h.addLayout(left, 3)
        right = QFrame()
        right.setObjectName("recent")
        right.setStyleSheet("#recent{background:white; border:1px solid #DDD3E9; border-radius:12px;}")
        rv = QVBoxLayout(right)
        rv.setContentsMargins(14, 12, 14, 10)
        top = QHBoxLayout()
        rt = QLabel("Recent")
        rt.setStyleSheet("font-size:15px; font-weight:700; color:#1B1040;")
        top.addWidget(rt, 1)
        clr = QPushButton("Clear")
        clr.setFlat(True)
        clr.setStyleSheet("color:#65596E;")
        clr.clicked.connect(lambda: (clear_recent(slug), self.refresh()))
        top.addWidget(clr)
        rv.addLayout(top)
        self.lst = QListWidget()
        self.lst.setFrameShape(QFrame.NoFrame)
        self.lst.setStyleSheet("QListWidget{background:white; color:#1B1040;} QListWidget::item{padding:7px 4px; border-bottom:1px solid #EAE3F2;} "
                               "QListWidget::item:selected{background:#E8DBF3; color:#1B1040;}")
        self.lst.itemActivated.connect(lambda it: self.open_recent.emit(it.data(Qt.UserRole)))
        self.lst.itemClicked.connect(lambda it: self.open_recent.emit(it.data(Qt.UserRole)))
        rv.addWidget(self.lst, 1)
        self.empty = QLabel("Files you open or save will show here.")
        self.empty.setWordWrap(True)
        self.empty.setStyleSheet("color:#65596E; font-size:12px;")
        rv.addWidget(self.empty)
        h.addWidget(right, 1)
        self.refresh()

    def refresh(self):
        self.lst.clear()
        items = recent_files(self.slug)
        for r in items:
            it = QListWidgetItem(f"{os.path.basename(r['path'])}\n{os.path.dirname(r['path'])}   ·   {ago(r.get('time', 0))}")
            it.setData(Qt.UserRole, r["path"])
            it.setToolTip(r["path"])
            self.lst.addItem(it)
        self.empty.setVisible(not items)


class OpenDialog(QDialog):
    """Open window with tabs: This computer, Recent, Shortcuts (more tabs can be added later)"""

    def __init__(self, parent, slug, name_filter, title="Open"):
        super().__init__(parent)
        self.slug = slug
        self.path = None
        self.setWindowTitle(title)
        self.resize(860, 560)
        self.cfg = QSettings("Digonto", slug.replace("digonto-", "").title())
        v = QVBoxLayout(self)
        self.tabs = QTabWidget()
        v.addWidget(self.tabs)
        # --- This computer
        self.fd = QFileDialog()
        self.fd.setOption(QFileDialog.DontUseNativeDialog, True)
        self.fd.setWindowFlags(Qt.Widget)
        self.fd.setFileMode(QFileDialog.ExistingFile)
        self.fd.setAcceptMode(QFileDialog.AcceptOpen)
        self.fd.setNameFilter(name_filter)
        self.fd.setDirectory(self.cfg.value("open_dir", os.path.expanduser("~")))
        self.fd.fileSelected.connect(self.picked)
        self.fd.rejected.connect(self.reject)
        self.tabs.addTab(self.fd, "This computer")
        # --- Recent
        self.recent = QListWidget()
        for r in recent_files(slug, 100):
            it = QListWidgetItem(f"{os.path.basename(r['path'])}\n{os.path.dirname(r['path'])}   ·   {ago(r.get('time', 0))}")
            it.setData(Qt.UserRole, r["path"])
            self.recent.addItem(it)
        if not self.recent.count():
            self.recent.addItem("(nothing opened yet)")
            self.recent.item(0).setFlags(Qt.NoItemFlags)
        self.recent.itemActivated.connect(lambda it: it.data(Qt.UserRole) and self.picked(it.data(Qt.UserRole)))
        self.tabs.addTab(self.recent, "Recent")
        # --- Shortcuts
        sc = QWidget()
        sv = QVBoxLayout(sc)
        sv.addWidget(QLabel("Folders you use often. Double-click one to look inside it. They also appear in the side bar of \"This computer\"."))
        self.sc_list = QListWidget()
        sv.addWidget(self.sc_list, 1)
        row = QHBoxLayout()
        add = QPushButton("Add folder ...")
        add.clicked.connect(self.add_shortcut)
        rem = QPushButton("Remove")
        rem.clicked.connect(self.remove_shortcut)
        row.addWidget(add)
        row.addWidget(rem)
        row.addStretch(1)
        sv.addLayout(row)
        self.sc_list.itemActivated.connect(self.go_shortcut)
        self.tabs.addTab(sc, "Shortcuts")
        self.fill_shortcuts()

    def defaults(self):
        h = os.path.expanduser("~")
        out = [("Home", h)]
        for n in ("Desktop", "Documents", "Downloads"):
            p = os.path.join(h, n)
            if os.path.isdir(p):
                out.append((n, p))
        return out

    def user_shortcuts(self):
        v = self.cfg.value("open_shortcuts", [])
        if isinstance(v, str):
            v = [v] if v else []
        return [p for p in (v or []) if isinstance(p, str)]

    def fill_shortcuts(self):
        self.sc_list.clear()
        for n, p in self.defaults():
            it = QListWidgetItem(f"{n}   ({p})")
            it.setData(Qt.UserRole, p)
            it.setData(Qt.UserRole + 1, False)
            self.sc_list.addItem(it)
        for p in self.user_shortcuts():
            it = QListWidgetItem(f"{os.path.basename(p.rstrip('/\\\\')) or p}   ({p})")
            it.setData(Qt.UserRole, p)
            it.setData(Qt.UserRole + 1, True)
            self.sc_list.addItem(it)
        self.fd.setSidebarUrls([QUrl.fromLocalFile(p) for _, p in self.defaults()] + [QUrl.fromLocalFile(p) for p in self.user_shortcuts()])

    def add_shortcut(self):
        d = QFileDialog.getExistingDirectory(self, "Add a folder shortcut", os.path.expanduser("~"))
        if d:
            lst = self.user_shortcuts()
            if d not in lst:
                lst.append(d)
                self.cfg.setValue("open_shortcuts", lst)
            self.fill_shortcuts()

    def remove_shortcut(self):
        it = self.sc_list.currentItem()
        if it and it.data(Qt.UserRole + 1):
            lst = [p for p in self.user_shortcuts() if p != it.data(Qt.UserRole)]
            self.cfg.setValue("open_shortcuts", lst)
            self.fill_shortcuts()

    def go_shortcut(self, it):
        p = it.data(Qt.UserRole)
        if p and os.path.isdir(p):
            self.fd.setDirectory(p)
            self.tabs.setCurrentIndex(0)

    def picked(self, path):
        if path and os.path.isfile(path):
            self.path = path
            self.cfg.setValue("open_dir", os.path.dirname(path))
            self.accept()
