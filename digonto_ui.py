"""Shared look of the Digonto programs (same green header, About button and Fusion style as Digonto PDF)."""
import json
import os
import sys
import time

from PySide6.QtCore import QEvent, QObject, QSize, QTimer, Qt
from PySide6.QtGui import QColor, QIcon, QPalette, QPixmap
from PySide6.QtWidgets import (QMenu, QApplication, QComboBox, QHBoxLayout, QLabel, QPushButton, QStyledItemDelegate, QVBoxLayout,
                               QWidget)

GREEN = "#C2395C"


def app_icon(here, slug):
    for n in (256, 128, 64):
        p = os.path.join(here, "assets", f"{slug}-{n}.png")
        if os.path.isfile(p):
            return QIcon(p)
    return QIcon()


def _banner_pixmap(h=76):
    p = os.path.join(os.path.dirname(os.path.abspath(__file__)), "assets", "digonto-banner.png")
    pm = QPixmap(p)
    if pm.isNull():
        return None
    pm = pm.scaledToHeight(h * 2, Qt.SmoothTransformation)     # 2x for sharpness
    pm.setDevicePixelRatio(2.0)
    return pm


OFFLINE_NOTE = {
    "Digonto Audio": "Digonto Audio works completely on your computer. Your sound files never leave it.",
    "Digonto Images": "Digonto Images never connects to the internet. Your pictures stay on your computer.",
    "Digonto Vector": "Digonto Vector never connects to the internet. Your drawings stay on your computer.",
    "Digonto Logo": "Digonto Logo never connects to the internet. Your logos stay on your computer.",
    "Digonto QR": "Digonto QR never connects to the internet. Your codes are made on your computer.",
    "Digonto Write": "Digonto Write never connects to the internet. Your documents stay on your computer.",
    "Digonto Sheets": "Digonto Sheets never connects to the internet. Your spreadsheets stay on your computer.",
    "Digonto PDF": "Digonto PDF never connects to the internet. Your files stay on your computer.",
}


POPUP_SIZE = (480, 400)          # Quick tips, Shortcuts and About: the same size in every program


def about_dialog(parent, title, text, icon=None):
    """the same About window in every Digonto program: dusk header (banner, name, version), then the description"""
    import re
    from PySide6.QtWidgets import QDialog
    name = QApplication.applicationDisplayName() or title
    version = ""
    m = re.search(r"<h3>(.*?)</h3>", text, re.S) or re.search(r"<b>(.*?)</b>(?: *[0-9][0-9.]*)?(?:<br>)?", text, re.S)
    if m:
        head = re.sub(r"<[^>]+>", "", m.group(0)).strip()
        mv = re.search(r"\bv?([0-9][0-9A-Za-z.\-]*)\s*$", head)
        if mv:
            version = mv.group(1)
        text = text.replace(m.group(0), "", 1)
    text = re.sub(r"^(\s*<br>)+", "", text.strip())
    text = re.sub(r"<h3>|</h3>", "", text)
    note = OFFLINE_NOTE.get(name, "")
    if note and note.split(".")[0] not in re.sub(r"<[^>]+>", "", text):
        text += ("<p>" + note + "</p>") if "<p>" in text else ("<br><br>" + note)
    dlg = QDialog(parent)
    dlg.setWindowTitle("About " + name)
    dlg.setStyleSheet("QDialog { background:#F6F2FA; } QLabel { color:#1B1040; }")
    lay = QVBoxLayout(dlg)
    lay.setContentsMargins(0, 0, 0, 0)
    lay.setSpacing(0)
    head = QWidget()
    head.setObjectName("abouthead")
    head.setStyleSheet("#abouthead { background: qlineargradient(x1:0, y1:0, x2:1, y2:0, "
                       "stop:0 #1D1548, stop:0.55 #4A1F6E, stop:1 #8A2150); }")
    hl = QHBoxLayout(head)
    hl.setContentsMargins(18, 14, 26, 14)
    hl.setSpacing(14)
    bp = _banner_pixmap(58)
    if bp is not None:
        b = QLabel()
        b.setPixmap(bp)
        hl.addWidget(b)
        bar = QWidget()
        bar.setFixedSize(2, 52)
        bar.setStyleSheet("background:rgba(255,255,255,0.25);")
        hl.addWidget(bar)
    t = QLabel(f"<span style='font-size:18px; font-weight:700; color:white'>{name}</span>"
               + (f"<br><span style='font-size:13px; color:#E9D5EE'>Version {version}</span>" if version else "")
               + "<br><span style='font-size:12px; color:#E9D5EE'>Part of the Digonto family of programs</span>")
    hl.addWidget(t)
    hl.addStretch()
    lay.addWidget(head)
    body = QLabel("<div style='font-size:13px'>" + text.replace("<p>", "<p style='margin:0 0 9px 0'>") + "</div>")
    body.setWordWrap(True)
    body.setTextFormat(Qt.RichText)
    body.setOpenExternalLinks(False)
    body.setContentsMargins(22, 16, 22, 6)
    body.setAlignment(Qt.AlignTop | Qt.AlignLeft)
    from PySide6.QtWidgets import QScrollArea
    sc = QScrollArea()
    sc.setWidgetResizable(True)
    sc.setFrameShape(QScrollArea.NoFrame)
    sc.setStyleSheet("QScrollArea, QScrollArea > QWidget > QWidget { background:#F6F2FA; }")
    sc.setWidget(body)
    lay.addWidget(sc, 1)
    row = QHBoxLayout()
    row.setContentsMargins(22, 6, 22, 16)
    row.addStretch()
    ok = QPushButton("OK")
    ok.setCursor(Qt.PointingHandCursor)
    ok.setDefault(True)
    ok.setStyleSheet("QPushButton{background:qlineargradient(x1:0,y1:0,x2:1,y2:0,stop:0 #FF6F8E,stop:1 #FFB05A); color:#2A1241; "
                     "border:1px solid #FF6F8E; border-radius:8px; padding:7px 26px; font-size:13px; font-weight:600;}"
                     "QPushButton:hover{background:qlineargradient(x1:0,y1:0,x2:1,y2:0,stop:0 #FF86A1,stop:1 #FFC273);}")
    ok.clicked.connect(dlg.accept)
    row.addWidget(ok)
    lay.addLayout(row)
    dlg.setFixedSize(*POPUP_SIZE)
    dlg.exec()


def _styled_question(parent, title, text, buttons=None, default=None, labels=None):
    """a Digonto-styled replacement for QMessageBox.question (the native one was cut off on macOS)"""
    from PySide6.QtWidgets import QDialog, QMessageBox as MB
    SB = MB.StandardButton
    buttons = buttons if buttons is not None else (SB.Yes | SB.No)
    names = [(SB.Save, "Save"), (SB.Discard, "Don't Save"), (SB.Yes, "Yes"), (SB.No, "No"), (SB.Ok, "OK"), (SB.Cancel, "Cancel")]
    dlg = QDialog(parent)
    dlg.setWindowTitle(title or "Digonto")
    dlg.setStyleSheet("QDialog { background:#F6F2FA; } QLabel { color:#1B1040; font-size:13px; }")
    lay = QVBoxLayout(dlg)
    lay.setContentsMargins(24, 20, 24, 18)
    lay.setSpacing(16)
    lb = QLabel(text)
    lb.setWordWrap(True)
    lb.setMinimumWidth(320)
    lb.setMaximumWidth(460)
    lay.addWidget(lb)
    row = QHBoxLayout()
    row.setSpacing(8)
    row.addStretch()
    result = {"v": SB.Cancel if (buttons & SB.Cancel) else SB.No}
    def pick(b):
        result["v"] = b
        dlg.accept()
    first = None
    for b, label in reversed(names):                 # Cancel, OK, No, Yes, Don't Save, Save (left to right after reversing again)
        pass
    for b, label in [x for x in names if x[0] in (SB.Discard, SB.No, SB.Cancel)] + [x for x in names if x[0] in (SB.Save, SB.Yes, SB.Ok)]:
        if not (buttons & b):
            continue
        btn = QPushButton((labels or {}).get(b, label))
        btn.setMinimumWidth(96)
        btn.setCursor(Qt.PointingHandCursor)
        primary = (default == b) if default not in (None, SB.NoButton) else b in (SB.Save, SB.Yes, SB.Ok)
        if primary:
            btn.setStyleSheet("QPushButton{background:qlineargradient(x1:0,y1:0,x2:1,y2:0,stop:0 #FF6F8E,stop:1 #FFB05A); color:#2A1241; "
                              "border:1px solid #FF6F8E; border-radius:7px; padding:7px 18px; font-size:13px; font-weight:600;}")
            btn.setDefault(True)
        else:
            btn.setStyleSheet("QPushButton{background:white; color:#1B1040; border:1px solid #D0C4E1; border-radius:7px; padding:7px 18px; font-size:13px;}"
                              "QPushButton:hover{background:#EDE6F4;}")
        btn.clicked.connect(lambda _=False, bb=b: pick(bb))
        row.addWidget(btn)
    lay.addLayout(row)
    dlg.exec()
    return result["v"]


def print_pages(parent, n_pages, render_page, title="Digonto"):
    """system print dialog -> render_page(index, painter, page_rect_in_device_pixels) for each chosen page"""
    from PySide6.QtGui import QPainter
    from PySide6.QtWidgets import QDialog, QMessageBox
    from PySide6.QtPrintSupport import QAbstractPrintDialog, QPrintDialog, QPrinter
    pr = QPrinter(QPrinter.HighResolution)
    pr.setDocName(title)
    dlg = QPrintDialog(pr, None)
    dlg.setMinMax(1, max(1, n_pages))
    if n_pages > 1:
        dlg.setOption(QAbstractPrintDialog.PrintPageRange, True)
    if dlg.exec() != QDialog.Accepted:
        return False
    first, last = 1, n_pages
    if n_pages > 1 and pr.printRange() == QPrinter.PageRange and pr.fromPage() > 0:
        first, last = pr.fromPage(), pr.toPage()
    p = QPainter()
    if not p.begin(pr):
        QMessageBox.warning(parent, title, "The printer could not be started.")
        return False
    try:
        for i in range(first - 1, last):
            if i > first - 1:
                pr.newPage()
            render_page(i, p, pr.pageRect(QPrinter.DevicePixel))
    finally:
        p.end()
    return True


def fit_rect(w, h, rect):
    """largest w:h rectangle centred in rect"""
    from PySide6.QtCore import QRectF
    s = min(rect.width() / max(w, 1e-9), rect.height() / max(h, 1e-9))
    tw, th = w * s, h * s
    return QRectF(rect.x() + (rect.width() - tw) / 2, rect.y() + (rect.height() - th) / 2, tw, th)


def install_dialogs():
    from PySide6.QtWidgets import QMessageBox as _MB
    _MB.question = staticmethod(_styled_question)
    _decouple_dialogs()


_DG_LIVE = set()


class _DgCentre(QObject):
    """a popup that has a parent can be dragged together with it (seen on Mac and Linux). So popups are free windows, centred over the window they came from."""
    def eventFilter(self, o, e):
        if e.type() == QEvent.Show and not getattr(o, "_dg_done", False):
            o._dg_done = True
            par = getattr(o, "_dg_parent", None)
            try:
                if par is not None:
                    top = par.window()
                    g = top.frameGeometry()
                    o.move(g.center().x() - o.width() // 2, g.center().y() - o.height() // 2)
            except Exception:
                pass
        return False


def _decouple_dialogs():
    from PySide6.QtWidgets import QDialog as _D, QMessageBox as _M
    if getattr(_D, "_dg_patched", False):
        return

    def wrap(cls):
        orig = cls.__init__

        def init(self, *a, **k):
            par = k.pop("parent", None)
            a = list(a)
            for i, x in enumerate(a):
                if isinstance(x, QWidget):
                    par = x
                    a[i] = None
                    break
            else:
                if par is not None:
                    k["parent"] = None
            orig(self, *a, **k)
            self._dg_parent = par
            if par is not None:
                self.setWindowModality(Qt.ApplicationModal)
                self.setWindowFlag(Qt.WindowStaysOnTopHint, True)       # a free window must not slip behind the program
                f = _DgCentre(self)
                self.installEventFilter(f)
                _DG_LIVE.add(self)
                self.finished.connect(lambda *_: QTimer.singleShot(0, lambda: _DG_LIVE.discard(self)))
        cls.__init__ = init
    wrap(_D)
    wrap(_M)
    _D._dg_patched = True


def install_about(icon=None):
    from PySide6.QtWidgets import QMessageBox as _MB
    _MB.about = staticmethod(lambda parent, title, text: about_dialog(parent, title, text, icon))


def make_header(title, subtitle, icon, on_about, right_widget=None, slim=True):
    """slim Digonto header: dark dusk gradient, this program's icon and name (View > Hide header removes it)"""
    header = QWidget()
    header.setObjectName("header")
    header.setToolTip(subtitle)
    if slim:
        header.setFixedHeight(34)
    header.setStyleSheet("#header { background: qlineargradient(x1:0, y1:0, x2:1, y2:0, "
                         "stop:0 #1D1548, stop:0.55 #4A1F6E, stop:1 #8A2150); }")
    hl = QHBoxLayout(header)
    hl.setContentsMargins(10, 2, 10, 2) if slim else hl.setContentsMargins(14, 6, 14, 6)
    hl.setSpacing(10 if slim else 12)
    logo = QLabel()
    logo.setPixmap(icon.pixmap(QSize(24, 24) if slim else QSize(44, 44)))
    hl.addWidget(logo)
    t = QLabel(f"<span style='font-size:14px; font-weight:800; color:white'>{title}</span>" if slim else
               f"<span style='font-size:20px; font-weight:800; color:white'>{title}</span><br><span style='color:#E9D5EE'>{subtitle}</span>")
    hl.addWidget(t)
    hl.addStretch()
    if right_widget is not None:
        hl.addWidget(right_widget)
    # About is in Help > About (same in every program)
    if slim:
        QTimer.singleShot(0, lambda: _header_toggle(header, on_about, title))
    _keep_help(header, title, on_about)
    return header


from PySide6.QtWidgets import QMenu  # noqa: E402
from PySide6.QtCore import QTimer  # noqa: E402


def _header_toggle(header, on_about=None, title="", tries=0):
    """View > Hide header (remembered)"""
    from PySide6.QtCore import QSettings
    from PySide6.QtGui import QAction
    try:
        win = header.window()
    except RuntimeError:
        return
    mb = win.menuBar() if (win is not header and hasattr(win, "menuBar")) else None
    if mb is None:
        if tries < 60:                                   # the header is not in its window yet: try again shortly
            QTimer.singleShot(100, lambda: _header_toggle(header, on_about, title, tries + 1))
        return
    if win.property("_hdr_toggle"):
        return
    win.setProperty("_hdr_toggle", True)
    menu = _top_menus(mb).get("View")
    if menu is None:
        menu = QMenu("View", win)
        win._digonto_view_menu = menu
        help_act = next((a for a in mb.actions() if a.text().replace("&", "") == "Help"), None)
        if help_act is not None:
            mb.insertMenu(help_act, menu)
        else:
            mb.addMenu(menu)
    else:
        menu.addSeparator()
    act = QAction("Hide header", win)
    act.setCheckable(True)
    st = QSettings("Digonto", "ui")
    hidden = str(st.value("header_hidden", "false")).lower() == "true"
    act.setChecked(hidden)
    header.setVisible(not hidden)

    def apply(on):
        header.setVisible(not on)
        st.setValue("header_hidden", "true" if on else "false")
    act.toggled.connect(apply)
    menu.addAction(act)


def scrolled(widget):
    """the content keeps its natural size; when the window is smaller, scroll bars appear instead of cut-off parts"""
    from PySide6.QtWidgets import QFrame, QScrollArea
    sa = QScrollArea()
    sa.setWidgetResizable(True)
    sa.setFrameShape(QFrame.NoFrame)
    sa.setWidget(widget)
    sa.setStyleSheet("QScrollArea{background:transparent;}")
    return sa


def wrap_with_header(window, header, body):
    """central widget = header on top, body below (what Digonto PDF does)"""
    central = QWidget()
    cl = QVBoxLayout(central)
    cl.setContentsMargins(0, 0, 0, 0)
    cl.setSpacing(0)
    cl.addWidget(header)
    cl.addWidget(scrolled(body), 1)
    window.setCentralWidget(central)


def light_palette():
    """fixed light colors, so a dark system theme cannot turn text white on our light panels"""
    p = QPalette()
    ink, soft = QColor("#1B1040"), QColor("#8A7FA6")
    for role, col in ((QPalette.Window, "#F6F2FA"), (QPalette.WindowText, "#1B1040"), (QPalette.Base, "#FFFFFF"),
                      (QPalette.AlternateBase, "#EDE6F4"), (QPalette.Text, "#1B1040"), (QPalette.Button, "#FFFFFF"),
                      (QPalette.ButtonText, "#1B1040"), (QPalette.Highlight, "#C2395C"), (QPalette.HighlightedText, "#FFFFFF"),
                      (QPalette.ToolTipBase, "#FFFFE8"), (QPalette.ToolTipText, "#1B1040"), (QPalette.Link, "#C2395C"),
                      (QPalette.PlaceholderText, "#8A7FA6"), (QPalette.BrightText, "#FFFFFF")):
        p.setColor(role, QColor(col))
    for role in (QPalette.WindowText, QPalette.Text, QPalette.ButtonText):
        p.setColor(QPalette.Disabled, role, soft)
    return p


class _ComboFix(QObject):
    """QSS drop-down lists need a styled delegate to paint their selected row properly"""

    def eventFilter(self, obj, ev):
        if ev.type() == QEvent.Polish and isinstance(obj, QComboBox) and not obj.property("_fx"):
            obj.setProperty("_fx", True)
            obj.setItemDelegate(QStyledItemDelegate(obj))
        return False


THEME_QSS = """
QMainWindow, QDialog { background:#F6F2FA; }
QMenuBar { background:#EDE6F4; color:#1B1040; }
QMenuBar::item:selected { background:#FBDCE5; }
QMenu { background:white; color:#1B1040; border:1px solid #D0C4E1; }
QMenu::item { padding:6px 26px; }
QMenu::item:selected { background:#FBDCE5; color:#1B1040; }
QMenu::separator { height:1px; background:#EAE3F2; margin:4px 8px; }
QStatusBar { background:#EDE6F4; color:#5B5278; }
QToolTip { background:#FFFFF0; color:#1B1040; border:1px solid #D0C4E1; padding:4px; }
QTabWidget::pane { border:1px solid #DDD3E9; background:white; border-radius:8px; top:-1px; }
QTabBar::tab { background:#EBE3F3; color:#3B2A63; padding:8px 16px; margin-right:2px; border-top-left-radius:8px; border-top-right-radius:8px; }
QTabBar::tab:selected { background:white; color:#8A2150; font-weight:600; }
QTabBar::tab:hover:!selected { background:#E3D7EF; }
QPushButton { background:white; color:#1B1040; border:1px solid #D0C4E1; border-radius:6px; padding:6px 14px; }
QPushButton:hover { background:#EDE6F4; }
QPushButton:pressed { background:#FBDCE5; }
QPushButton:disabled { background:#F2EDF7; color:#A99FC0; border-color:#E5DDEF; }
QPushButton:checked { background:qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #FF6F8E, stop:1 #FFB05A); color:#2A1241; border-color:#FF6F8E; }
QPushButton[primary="true"] { background:qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #FF6F8E, stop:1 #FFB05A); color:#2A1241; border:1px solid #FF6F8E; font-weight:600; padding:8px 20px; }
QPushButton[primary="true"]:hover { background:qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #FF86A1, stop:1 #FFC273); }
QPushButton[primary="true"]:disabled { background:#E2B3C2; border-color:#E2B3C2; color:white; }
QLineEdit, QPlainTextEdit, QTextEdit { background:white; color:#1B1040; border:1px solid #D0C4E1; border-radius:6px; padding:5px; selection-background-color:#C2395C; selection-color:white; }
QLineEdit:focus, QPlainTextEdit:focus, QTextEdit:focus { border:1px solid #C2395C; }
QSpinBox, QDoubleSpinBox { background:white; color:#1B1040; padding:3px; }
QComboBox { background:white; color:#1B1040; border:1px solid #D0C4E1; border-radius:6px; padding:5px 8px; }
QComboBox:focus { border:1px solid #C2395C; }
QComboBox QAbstractItemView::item { min-height:24px; color:#1B1040; background:white; }
QComboBox QAbstractItemView::item:selected, QComboBox QAbstractItemView::item:hover { background:#FBDCE5; color:#1B1040; }
QComboBox QAbstractItemView { background:white; color:#1B1040; selection-background-color:#FBDCE5; selection-color:#1B1040; border:1px solid #D0C4E1; }
QGroupBox { background:white; border:1px solid #DDD3E9; border-radius:8px; margin-top:16px; padding:10px; font-weight:600; }
QGroupBox::title { subcontrol-origin:margin; left:12px; padding:0 6px; color:#8A2150; }
QTableWidget, QTableView, QTreeWidget, QTreeView, QListWidget, QListView { background:white; color:#1B1040; alternate-background-color:#FAF7FC; border:1px solid #DDD3E9; border-radius:6px; gridline-color:#EAE3F2; }
QTableWidget::item:selected, QTableView::item:selected, QTreeWidget::item:selected, QTreeView::item:selected, QListWidget::item:selected, QListView::item:selected { background:#FBDCE5; color:#1B1040; }
QHeaderView::section { background:#EDE6F4; color:#3B2A63; border:0; border-right:1px solid #DDD3E9; border-bottom:1px solid #DDD3E9; padding:6px 8px; font-weight:600; }
QProgressBar { border:1px solid #D0C4E1; border-radius:6px; text-align:center; background:white; color:#1B1040; }
QProgressBar::chunk { background:qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #FF6F8E, stop:1 #FFB05A); border-radius:5px; }
QSlider::groove:horizontal { height:6px; background:#DDD3E9; border-radius:3px; }
QSlider::sub-page:horizontal { background:qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #FF6F8E, stop:1 #FFB05A); border-radius:3px; }
QSlider:horizontal { min-height:24px; }
QSlider::handle:horizontal { background:white; border:2px solid #FF6F8E; width:16px; height:16px; margin:-7px 0; border-radius:10px; }
QScrollBar:vertical { background:transparent; width:14px; margin:0; }
QScrollBar::handle:vertical { background:#CDBFDD; min-height:30px; border-radius:4px; margin:3px; }
QScrollBar::handle:vertical:hover { background:#B49CCB; }
QScrollBar:horizontal { background:transparent; height:14px; margin:0; }
QScrollBar::handle:horizontal { background:#CDBFDD; min-width:30px; border-radius:4px; margin:3px; }
QScrollBar::handle:horizontal:hover { background:#B49CCB; }
QScrollBar::add-line, QScrollBar::sub-line { width:0; height:0; }
QScrollBar::add-page, QScrollBar::sub-page { background:transparent; }
QSplitter::handle { background:#DDD3E9; }
QSplitter::handle:horizontal { width:3px; }
QSplitter::handle:vertical { height:3px; }
"""


def _close_qss():
    """a small round x on every tab: soft grey, rose on hover (drawn once into the config folder)"""
    import tempfile
    from PySide6.QtGui import QColor, QPainter, QPen, QPixmap
    d = os.path.join(tempfile.gettempdir(), "digonto-ui")
    try:
        os.makedirs(d, exist_ok=True)
        out = {}
        for name, bg, fg in (("close", None, "#8C7FA0"), ("close_hover", "#F3C2CF", "#C2395C")):
            pm = QPixmap(32, 32)
            pm.fill(Qt.transparent)
            p = QPainter(pm)
            p.setRenderHint(QPainter.Antialiasing)
            if bg:
                p.setPen(Qt.NoPen)
                p.setBrush(QColor(bg))
                p.drawEllipse(1, 1, 30, 30)
            p.setPen(QPen(QColor(fg), 3.2, Qt.SolidLine, Qt.RoundCap))
            p.drawLine(10, 10, 22, 22)
            p.drawLine(22, 10, 10, 22)
            p.end()
            path = os.path.join(d, name + ".png")
            pm.save(path)
            out[name] = path.replace("\\", "/")
        return ("QTabBar::close-button { image:url(%s); subcontrol-position:right; margin:2px; width:16px; height:16px; }"
                "QTabBar::close-button:hover { image:url(%s); }" % (out["close"], out["close_hover"]))
    except Exception:
        return ""


def apply_theme(app):
    """the Digonto look for the whole program: fixed light colors, rounded buttons, green accents"""
    app.setStyle("Fusion")
    app.setPalette(light_palette())
    app.setStyleSheet(THEME_QSS + _close_qss())
    if not hasattr(app, "_combofix"):
        app._combofix = _ComboFix(app)
        app.installEventFilter(app._combofix)


def primary(button):
    """make a button the main (green) action of its page"""
    button.setProperty("primary", True)
    button.style().unpolish(button)
    button.style().polish(button)
    return button


def base_dir():
    return (os.environ.get("DIGONTO_BASE") or os.environ.get("PROTTOY_BASE")) or os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def add_recent(slug, path):
    """tell Digonto Studio about a file you worked on (it shows the list)"""
    rp = os.path.join(base_dir(), "recent.json")
    try:
        with open(rp, encoding="utf-8") as f:
            items = [r for r in json.load(f) if isinstance(r, dict)]
    except (OSError, ValueError):
        items = []
    items = [r for r in items if r.get("path") != path]
    items.insert(0, {"app": slug, "path": path, "time": time.time()})
    try:
        os.makedirs(base_dir(), exist_ok=True)
        with open(rp, "w", encoding="utf-8") as f:
            json.dump(items[:40], f)
    except OSError:
        pass


def file_menu(window, extra=(), before_exit=()):
    """File menu: your own actions (text, shortcut, callback), then Exit and Quit (force)"""
    from PySide6.QtGui import QAction
    fm = window.menuBar().addMenu("File")
    for item in extra:
        if isinstance(item, QAction):
            fm.addAction(item)
            continue
        text, sc, fn = item
        a = QAction(text, window)
        if sc:
            a.setShortcut(sc)
        a.triggered.connect(fn)
        fm.addAction(a)
    if extra:
        fm.addSeparator()
    for a in before_exit:
        fm.addAction(a)
    if before_exit:
        fm.addSeparator()
    ex = QAction("Exit", window)
    ex.setShortcut("Ctrl+Q")
    ex.triggered.connect(window.close)
    fm.addAction(ex)
    q = QAction("Quit (force)", window)
    q.setShortcut("Ctrl+Shift+Q")
    q.triggered.connect(lambda: os._exit(0))
    fm.addAction(q)
    return fm



_HOLD = [0]


def hold_alive(on):
    """call hold_alive(True) before hiding every window on purpose (a screen capture) and hold_alive(False) after:
    meanwhile the 'no window for 3 seconds = end the program' safety net waits"""
    _HOLD[0] = max(0, _HOLD[0] + (1 if on else -1))


def force_exit_soon(ms=300):
    """call from closeEvent: leave normally, and if anything (a thread) keeps the program alive, end it"""
    QApplication.instance().quit()
    QTimer.singleShot(ms, lambda: os._exit(0))


def migrate_legacy():
    """one-time, copy-only: bring settings and data from the old "Prottoy" names over to "Digonto" (nothing is deleted)"""
    import shutil
    try:
        from PySide6.QtCore import QSettings, QStandardPaths
        pairs = [("Prottoy", n) for n in ("Audio", "Images", "SSH", "Vector", "Write", "Sheets", "Studio", "QR",
                                          "Logo", "Browser", "Tools", "Sublimation", "DTFRIP")]
        pairs += [("ProttoyPDF", "ProttoyPDF")]
        for org, app in pairs:
            old = QSettings(org, app)
            keys = old.allKeys()
            if not keys:
                continue
            new = QSettings(org.replace("Prottoy", "Digonto"), app.replace("Prottoy", "Digonto"))
            if new.allKeys():
                continue
            for k in keys:
                new.setValue(k, old.value(k))
            new.sync()
        home = os.path.expanduser("~")
        roots = [home]
        for loc in (QStandardPaths.GenericDataLocation, QStandardPaths.GenericConfigLocation):
            roots.append(QStandardPaths.writableLocation(loc))
        roots.append(os.path.join(home, "Library", "Application Support"))
        for root in roots:
            if not root or not os.path.isdir(root):
                continue
            for entry in os.listdir(root):
                if "prottoy" in entry.lower():
                    src = os.path.join(root, entry)
                    dst = os.path.join(root, entry.replace("Prottoy", "Digonto").replace("prottoy", "digonto").replace("PROTTOY", "DIGONTO"))
                    if os.path.isdir(src) and not os.path.exists(dst):
                        shutil.copytree(src, dst)
    except Exception:
        pass


def setup_app(app, name, slug, icon, theme=False):
    migrate_legacy()
    app.setApplicationName(name)
    app.setApplicationDisplayName(name)
    app.setDesktopFileName(slug)
    app.setStyle("Fusion")
    app.setPalette(light_palette())
    app.setWindowIcon(icon)
    install_dialogs()
    install_about(icon)                       # one About window for every Digonto program
    from PySide6.QtCore import QTimer
    def _bye():                       # closing the last window ends the program for good (no Python left in the Dock)
        import threading
        t = threading.Timer(0.25, lambda: os._exit(0))      # a thread, so it works even if the Qt loop is stuck
        t.daemon = True
        t.start()
    app.lastWindowClosed.connect(_bye)
    app.aboutToQuit.connect(_bye)
    app.setQuitOnLastWindowClosed(True)
    state = {"seen": False, "gone": 0}

    def _watch():                     # safety net (macOS): no visible window for 3 seconds = the program is over, end the process
        if _HOLD[0] > 0:              # the program hid its window on purpose (a screen capture): not over
            state["gone"] = 0
            return
        if any(w.isVisible() for w in app.topLevelWidgets()):
            state["seen"], state["gone"] = True, 0
        elif state["seen"]:
            state["gone"] += 1
            if state["gone"] >= 3:
                os._exit(0)
    wd = QTimer(app)
    wd.setInterval(1000)
    wd.timeout.connect(_watch)
    wd.start()
    if theme:
        apply_theme(app)


def fit_window(window, w=1200, h=860):
    """open at a size that suits the screen (never bigger than 92 % of it)"""
    scr = window.screen().availableGeometry() if window.screen() else None
    if scr:
        w, h = min(w, int(scr.width() * 0.92)), min(h, int(scr.height() * 0.92))
        window.resize(w, h)
        window.move(scr.x() + (scr.width() - w) // 2, scr.y() + (scr.height() - h) // 2)
    else:
        window.resize(w, h)


def mac_app_name(name):
    """macOS: show the program's own name in the menu bar (and the app menu) instead of "Python". Call before QApplication(...).
    Does nothing on Linux / Windows."""
    import sys
    if sys.platform != "darwin":
        return
    try:
        import ctypes
        import ctypes.util
        objc = ctypes.cdll.LoadLibrary(ctypes.util.find_library("objc"))
        objc.objc_getClass.restype = ctypes.c_void_p
        objc.objc_getClass.argtypes = [ctypes.c_char_p]
        objc.sel_registerName.restype = ctypes.c_void_p
        objc.sel_registerName.argtypes = [ctypes.c_char_p]
        msg = objc.objc_msgSend
        msg.restype = ctypes.c_void_p

        def send(obj, sel, *args):
            msg.argtypes = [ctypes.c_void_p, ctypes.c_void_p] + [ctypes.c_void_p] * len(args)
            return msg(obj, objc.sel_registerName(sel.encode()), *args)

        def nsstr(s):
            msg.argtypes = [ctypes.c_void_p, ctypes.c_void_p, ctypes.c_char_p]
            return msg(objc.objc_getClass(b"NSString"), objc.sel_registerName(b"stringWithUTF8String:"), s.encode("utf-8"))

        bundle = send(objc.objc_getClass(b"NSBundle"), "mainBundle")
        info = send(bundle, "infoDictionary")
        if info:
            for key in ("CFBundleName", "CFBundleDisplayName"):
                send(info, "setObject:forKey:", nsstr(name), nsstr(key))
        send(send(objc.objc_getClass(b"NSProcessInfo"), "processInfo"), "setProcessName:", nsstr(name))
    except Exception:
        pass


# ---- one running copy per program: opening another file hands it to the copy that is already open (new tab / window)
_SI_KEEP = []


def _si_name(slug):
    import getpass
    try:
        u = getpass.getuser()
    except Exception:
        u = "user"
    return "digonto-" + slug + "-" + "".join(c if c.isalnum() else "_" for c in u)


def forward_to_running(slug, files):
    """True = the files were sent to a copy of this program that is already open (the caller then just exits)"""
    files = [os.path.abspath(f) for f in files if os.path.isfile(f)]
    if not files:
        return False
    from PySide6.QtNetwork import QLocalSocket
    s = QLocalSocket()
    s.connectToServer(_si_name(slug))
    if not s.waitForConnected(400):
        return False
    s.write(json.dumps(files).encode("utf-8"))
    ok = s.waitForBytesWritten(1500)
    s.waitForReadyRead(1500)              # the other side answers "ok" once it has the window up
    s.disconnectFromServer()
    return bool(ok)


def serve_single(slug, window, opener):
    """this copy becomes the one that other launches hand their files to; opener(path) opens one file"""
    from PySide6.QtNetwork import QLocalServer
    name = _si_name(slug)
    QLocalServer.removeServer(name)
    srv = QLocalServer(window)
    if not srv.listen(name):
        return
    _SI_KEEP.append(srv)

    def got():
        while srv.hasPendingConnections():
            c = srv.nextPendingConnection()
            c.waitForReadyRead(800)
            try:
                paths = json.loads(bytes(c.readAll()).decode("utf-8"))
            except Exception:
                paths = []
            target = None
            for p in paths:
                try:
                    if os.path.isfile(p):
                        r = opener(p)
                        if r is not None:
                            target = r
                except Exception:
                    pass
            try:
                w = target or window
                if w.isMinimized():
                    w.showNormal()
                w.show()
                w.raise_()
                w.activateWindow()
            except Exception:
                pass
            c.write(b"ok")
            c.flush()
            c.waitForBytesWritten(500)
            c.disconnectFromServer()
    srv.newConnection.connect(got)


# ---- Help menu in every program: Quick help, All shortcuts, About (same look as About)
_HELP_QUICK = {
    # program: (what it is, [what you can do], [how to do it])
    "pdf": ("Open, edit and create PDF files. Every PDF opens in its own tab; the first tab, Start, shows your recent files.",
            ["Change or add text right on the page", "Insert, move, rotate, delete and extract pages",
             "Sign with your own signature", "Make a PDF smaller (Shrink)", "Join several files into one PDF",
             "Put both sides of an ID card on one page", "Print"],
            ["Pick a tool on the right (Pages, Sign, Edit text, Shrink, Add files, More); its actions appear above the page.",
             "Edit text: click a line to change it, or choose Add text and click on the page. Double-click any text to edit it again.",
             "Pages: select pages in the list on the left, then insert, move, rotate, delete or extract them.",
             "Sign: draw or load your signature, place it, move and resize it, then press Apply. It is remembered for next time.",
             "Shrink makes a smaller copy in a new tab; the original stays as it is.",
             "File > Close project closes the current PDF; the program asks before closing unsaved changes."]),
    "images": ("Photo editing with layers, like Photoshop or GIMP, made easy.",
               ["Paint, erase, clone and heal", "Select parts of a picture (box, lasso, magic wand, quick selection)",
                "Work with layers, masks, blend modes and text layers", "Adjust colour, light and contrast; use filters",
                "Crop, resize and transform", "Open and save Photoshop files (.psd) with layers, masks and editable text"],
               ["Tools are in the column on the left; hover over a tool to see its key. Tool options appear above the picture.",
                "When there is a selection, everything happens only inside it. Ctrl+D removes the selection.",
                "Layers panel: show or hide, opacity, blend mode, lock, add, duplicate, reorder, merge. Double-click a layer to rename it.",
                "Masks: Layers panel > Mask. Paint black to hide, white to show.",
                "Text: choose the Text tool and click on the picture. Double-click a text layer to change it later.",
                "File > Save project keeps everything (.dimg). Save as .psd for Photoshop and GIMP. File > Export makes PNG, JPG and WebP."]),
    "vector": ("Draw logos, shapes and illustrations, like Illustrator, CorelDRAW or Inkscape, made easy.",
               ["Draw rectangles, ellipses, polygons, stars, lines and free curves", "Edit shapes point by point (nodes)",
                "Combine shapes: weld, trim, intersect", "Fill with colours and gradients; set outlines",
                "Write text and turn it into curves", "Work with layers and groups",
                "Open SVG, AI, EPS and PDF; export SVG, EPS, AI, PDF and PNG"],
               ["Left-click a colour at the bottom for the fill, right-click it for the outline.",
                "Double-click a shape to edit its nodes. In node mode, double-click a line to add a node.",
                "Drag from a ruler to pull out a guide; objects snap to guides, to other objects and to the page.",
                "Shaping (Weld, Trim, Intersect ...) makes new shapes from shapes that overlap.",
                "Hold Space and drag to move the view; the mouse wheel zooms.",
                "For Inkscape and Illustrator use File > Export > SVG: layers, groups and text stay editable."]),
    "sheets": ("A spreadsheet like Excel: formulas, charts, XLSX and CSV.",
               ["Type numbers and text into cells", "Calculate with formulas and functions", "Sort, filter and check data",
                "Format numbers, fonts, colours and borders", "Make charts", "Open and save XLSX, CSV and TSV; export PDF"],
               ["Type to replace a cell, or press F2 to change it. Enter or Tab confirms.",
                "Start a formula with = and click cells to add them. Insert > Function list shows every function with an example.",
                "Drag the small square at the corner of a selection to fill cells or continue a series.",
                "Data menu: sort, filter and data validation. Format menu: number formats, fonts, borders, merge and conditional colours.",
                "Ctrl+W returns to the start screen; the program asks before closing unsaved changes."]),
    "write": ("A word processor like Word: letters, reports and documents.",
              ["Write and format text with styles, fonts and colours", "Lists, tables, pictures and links",
               "Page setup: paper, margins, header, footer and page numbers", "Spell check (English)",
               "Open and save DOCX, ODT, HTML, Markdown and text; save as PDF; print"],
              ["Choose a style (Title, Heading, Quote, Code) in the toolbar, then set font, size and colour.",
               "Lists: Tab and Shift+Tab change the level. Tables, pictures and links are in the Insert menu.",
               "A red wavy line marks a spelling mistake: right-click it for suggestions. F7 goes to the next one.",
               "File > Page setup sets paper, margins, header, footer and page numbers; PDF and print use them.",
               "Ctrl+W returns to the start screen; the program asks before closing unsaved changes."]),
    "audio": ("Record, edit and clean up sound, like Adobe Audition, made easy.",
              ["Record from a microphone", "Cut, copy, paste and delete parts of a sound",
               "Make quiet sound louder; fade in and out", "Remove background noise",
               "Equalizer and many effects, each with Preview", "Split voice and music",
               "Export WAV, MP3, FLAC, OGG, M4A and more"],
              ["Drag on the wave to select. Double-click selects everything; Shift+click makes the selection longer.",
               "Edit > Cut by time: type exact times like 0:12.345 and cut that piece.",
               "Effects work on the selection, or on everything when nothing is selected. Press Preview before Apply.",
               "Quiet sound: Effects > Volume > Make quiet audio louder.",
               "Background noise: select a part with only noise, Effects > Learn noise, then Remove background noise.",
               "Ctrl+S saves a project (.daud, nothing lost). Ctrl+E exports a sound file."]),
    "logo": ("Make a complete logo and brand in four steps.",
             ["Get dozens of logo ideas from a few words", "Change name, symbol, layout, colours and fonts",
              "Export a full brand kit: logo files (SVG, PNG, PDF, EPS, AI), favicon, app icons, social images and a brand guide"],
             ["1 Brief: type the business name, a tagline, what you do, then pick styles and colours.",
              "2 Ideas: press the heart to keep an idea, More for other versions of it, More ideas for a new set.",
              "3 Customize: change anything; Undo and Redo work as usual.",
              "4 Export: choose a folder; everything is made at once.",
              "File > Save project keeps your work as a .dlgo file."]),
    "qr": ("Make QR codes for a link, text, Wi-Fi, contact card, e-mail, phone, SMS, WhatsApp or a map location.",
           ["Style the dots and corner eyes", "One colour or a gradient", "Put a logo in the middle",
            "Add a frame with a text label", "Export PNG (any size), SVG or PDF", "Make many codes at once from a list"],
           ["Choose the type on the left and fill in the data; the code changes while you type.",
            "Set the style on the right: dots, corner eyes, colours, logo, frame and label.",
            "Export with the PNG, SVG or PDF buttons. Many codes from a list makes a whole folder at once.",
            "File > Save project keeps everything as a .dqr file you can open again.",
            "Always test a code with your phone before printing. A dark code on a light background scans best."]),
    "ssh": ("An SSH terminal and SFTP file manager. Your servers are the same on every computer.",
            ["Keep a list of your servers in an encrypted vault", "Open servers as terminal tabs",
             "Copy files with SFTP", "Choose terminal colours and fonts"],
            ["Sign in with the same e-mail, vault password and location on each computer to see the same servers.",
             "Add a server once, then open it as a terminal tab; use the file view to copy files.",
             "A copy of the vault stays on each computer, so the program also works while the VPN is down.",
             "Settings: terminal colours, font and font size."]),
    "dtfrip": ("Print DTF transfers with an Epson L800 / L805 DTF printer.",
               ["Lay out pictures on the film", "Colour and white in one print run", "Quality presets from Draft to Maximum",
                "Nozzle check, head cleaning and test prints"],
               ["First time: add your printer's own colour profile (.icc / .icm) in Settings > Add profile - profiles are not included.",
                "Add pictures (PNG, TIFF, JPG, PDF, SVG) or drop them on the window, then set the width and copies.",
                "Use PNG with a transparent background: white ink is printed only under the picture.",
                "Layout, Printer, Color and White tabs on the right set the sheet, quality, colour and white ink.",
                "Load the DTF film (print side up) in the rear tray, then press Print.",
                "Printer / driver setup help is in the File menu."]),
    "sublimation": ("Print on sublimation transfer paper with any 4-ink Epson printer.",
                    ["Lay out pictures on the page", "Mirror for transfer paper", "Colour profiles and colour amount",
                     "Save a print-ready PNG or PDF"],
                    ["Install the Epson driver for your printer once (File > Printer / driver setup help).",
                     "Add your printer's own colour profile (.icc / .icm) in Settings > Add profile - profiles are not included.",
                     "Add pictures, set the paper size, then press Print. The driver dialog opens.",
                     "In the driver dialog: colour management off, best quality, the sublimation paper type, scale 100 %.",
                     "You can also save a print-ready PNG or PDF and print it from any program."]),
    "player": ("Play video and music. Open files or a folder, or drop them on the window.",
               ["Play lists with shuffle and repeat", "Full screen", "Speed from 0.5x to 2x",
                "Choose audio tracks and subtitles inside the file", "Continue long films where you stopped",
                "Save a picture of the moment you see"],
               ["Space plays or pauses; a click on the picture does the same. Double-click goes full screen; Esc leaves.",
                "The play list is on the right. Double-click to play, drag to change the order. File > Save play list makes an .m3u file.",
                "Shuffle and repeat (off / all / one) are next to the play buttons.",
                "Audio > Audio track and Subtitles show the tracks inside the file."]),
    "studio": ("All your Digonto programs in one place.",
               ["Open any Digonto program", "Open a file in the right program", "See your recent files",
                "Install, update or remove programs"],
               ["Click a tile to open that program in its own window.",
                "Open file picks the right program by the file type. Recent files are on the right.",
                "Exit closes only Studio; open programs keep running.",
                "The Uninstall button on a tile removes one program. Your own files are never touched."]),
    "tools": ("Screenshots, phone screenshots, cropping, template matching and background removal.",
              ["Capture the screen, an area or one window", "Take screenshots from a phone (ADB)",
               "Crop templates and find tap coordinates", "Check if a template is found in a screenshot",
               "Remove a background (automatic, by clicking, or with AI)"],
              ["Choose a tool in the column on the left; its settings are in the panels on the right.",
               "Several pictures can be open as tabs; drop files on the window to open them. The mouse wheel zooms.",
               "Crop: drag a box to save a template, click the tap point to get offset_x / offset_y.",
               "Remove background keeps the original pixels exactly; only the background becomes transparent.",
               "Setup shows what is installed and can install what is missing."]),
}

_HELP_MORE = {
    # an extra section in Quick tips: working together with other programs
    "images": ("Working with Photoshop and GIMP", [
        "Use .psd to share pictures with Photoshop and GIMP: File > Export and choose Photoshop PSD. File > Open opens .psd files.",
        "Layers keep their names, order, opacity, blend mode and visibility. Groups stay groups.",
        "Masks are saved as real layer masks, so you can keep editing them there.",
        "Text layers are saved as real Photoshop text: you can change the words, font, size and colour in Photoshop. "
        "GIMP shows them as normal picture layers.",
        "Layer styles (shadow, outline ...) are merged into the layer picture. Adjustment layers are not saved.",
        "Opening a .psd from Photoshop: layers, masks and text come in editable. A font you do not have is replaced by the closest one.",
        "Keep working in .dimg (File > Save project): it keeps everything. Use .psd to exchange files."]),
    "vector": ("Working with Inkscape and Illustrator", [
        "Use SVG to share drawings with Inkscape and Illustrator: File > Export > SVG, and File > Open for SVG files from them.",
        "Layers keep their names, and hidden or locked layers stay hidden or locked. Groups and object names are kept.",
        "Text stays editable text with its font, size, bold, italic and colour.",
        "Shapes, colours, gradients and outlines stay editable in both directions.",
        "AI, EPS and PDF files can be opened too, but only the shapes come in: no layers, no editable text, no pictures.",
        "Keep working in .dvec (File > Save): it keeps everything. Use SVG to exchange files."]),
}


_HELP_EXTRA = {
    "images": [("Tools", [("V", "Move"), ("Ctrl+T", "Free transform"), ("A", "Quick selection"), ("M", "Select"), ("L", "Lasso"), ("W", "Wand"),
                          ("B", "Brush"), ("E", "Eraser"), ("S", "Clone stamp"), ("J", "Healing brush"), ("R", "Smudge"), ("O", "Dodge"),
                          ("K", "Fill"), ("G", "Gradient"), ("I", "Picker"), ("T", "Text"), ("U", "Shape"), ("C", "Crop"), ("H", "Hand"), ("Z", "Zoom")]),
               ("Painting and selecting", [("[  ]", "Brush size"), ("X", "Swap colours"), ("D", "Black and white"),
                                           ("Shift + select", "Add to selection"), ("Alt + select", "Subtract from selection"),
                                           ("Alt + click", "Clone / healing: choose the part to copy")]),
               ("View", [("Mouse wheel", "Zoom"), ("Space + drag", "Move around")])],
    "vector": [("Tools", [("V", "Select"), ("A", "Node edit"), ("P", "Pen"), ("R", "Rectangle"), ("E", "Ellipse"), ("G", "Polygon"), ("S", "Star"),
                          ("L", "Line"), ("B", "Freehand"), ("T", "Text"), ("I", "Eyedropper"), ("Z", "Zoom"), ("H or Space", "Pan")]),
               ("Mouse", [("Left-click colour", "Fill"), ("Right-click colour", "Outline"), ("Drag from ruler", "Pull out a guide"),
                          ("Wheel", "Zoom"), ("Shift + wheel", "Scroll sideways"), ("Double-click shape", "Edit nodes")])],
    "sheets": [("Move", [("Arrows", "Move"), ("Ctrl + arrows", "To the edge of data"), ("Home / Ctrl+Home / Ctrl+End", "Start of row / sheet / end of data"), ("PgUp / PgDn", "One screen")]),
               ("Select", [("Shift + arrows", "Extend"), ("Ctrl+Space", "Column"), ("Shift+Space", "Row"), ("Ctrl + click", "Add a cell")]),
               ("Edit", [("F2", "Edit cell"), ("Enter / Tab", "Confirm and move"), ("Esc", "Cancel"), ("Alt+Enter", "New line in cell")]),
               ("Formulas", [("=", "Start a formula; click cells to add references"), ("F4", "Toggle $"), ("Tab", "Accept function suggestion"), ("Alt+=", "AutoSum")]),
               ("Copy and fill", [("Ctrl+Shift+V", "Paste values only"), ("Ctrl+D", "Fill down"), ("Ctrl+R", "Fill right")]),
               ("Other", [("Ctrl+G", "Go to"), ("Ctrl+;", "Today's date"), ("Ctrl + wheel", "Zoom")])],
    "write": [("Writing", [("Tab / Shift+Tab", "List level"), ("F7", "Next spelling mistake")])],
    "player": [("Mouse", [("Click", "Play / pause"), ("Double-click", "Full screen"), ("Wheel", "Volume")])],
    "audio": [("Playing and cursor", [("Space", "Play / pause"), ("Left / Right", "Move cursor 10 ms"), ("Alt + arrows", "1 ms"), ("Ctrl + arrows", "1 s"), ("Shift + arrows", "Extend selection")]),
              ("Mouse", [("Drag", "Select"), ("Double-click", "Select everything"), ("Wheel", "Zoom"), ("Shift + wheel", "Scroll"), ("Right-drag", "Move the view")])],
    "pdf": [("Mouse", [("Click on text", "Edit that line"), ("Double-click text", "Edit text again"), ("Wheel", "Scroll pages"), ("Ctrl + wheel", "Zoom")])],
}


def _help_key(name):
    n = (name or "").lower()
    for k in _HELP_QUICK:
        if k in n:
            return k
    return ""


def _mac_keys(text):
    """on a Mac: Ctrl+Shift+S -> ⌘+⇧+S (Qt's Ctrl is the Command key there); the + stays, like on Linux and Windows"""
    import re
    if sys.platform != "darwin":
        return text
    for a, b in (("Ctrl", "\u2318"), ("Cmd", "\u2318"), ("Meta", "\u2303"), ("Alt", "\u2325"), ("Shift", "\u21e7")):
        text = re.sub(r"\b" + a + r"\b", b, text)
    return text


def _nice_key(seq):
    from PySide6.QtGui import QKeySequence
    return _mac_keys(seq.toString(QKeySequence.PortableText))


def collect_shortcuts(win):
    """[(menu name, [(keys, what it does)])]  - read from the real menus, so it is always the truth"""
    from PySide6.QtGui import QAction
    seen, groups, used = set(), [], set()

    def clean(t):
        return t.replace("&", "").replace("…", "").replace("...", "").strip()

    def walk(menu, out, depth=0):
        try:
            acts = list(menu.actions())
        except RuntimeError:
            return
        for a in acts:
            used.add(id(a))
            try:
                sub = a.menu()
                if sub is not None:
                    sub.actions()
            except RuntimeError:
                sub = None
            if sub is not None:
                if depth < 4:
                    walk(sub, out, depth + 1)
                continue
            if a.isSeparator():
                continue
            keys = [_nice_key(s) for s in a.shortcuts() if not s.isEmpty()]
            t = clean(a.text())
            if keys and t and (t, keys[0]) not in seen:
                seen.add((t, keys[0]))
                out.append((" / ".join(keys), t))
    mb = win.menuBar() if hasattr(win, "menuBar") else None
    if mb is not None:
        menus = _top_menus(mb)
        for top in mb.actions():
            m = menus.get(clean(top.text()))
            if m is None:
                continue
            out = []
            walk(m, out)
            if out:
                groups.append((clean(top.text()), out))
    other = []
    for a in win.findChildren(QAction):
        if id(a) in used:
            continue
        keys = [_nice_key(s) for s in a.shortcuts() if not s.isEmpty()]
        t = clean(a.text())
        if keys and t and (t, keys[0]) not in seen:
            seen.add((t, keys[0]))
            other.append((" / ".join(keys), t))
    if other:
        groups.append(("Other", other))
    return groups


def _help_window(parent, title, subtitle, html, buttons):
    """popup with the Digonto header (same look as About); buttons = [(label, callback or None)]"""
    from PySide6.QtWidgets import QDialog, QTextBrowser
    dlg = QDialog(parent)
    dlg.setWindowTitle(title)
    dlg.setStyleSheet("QDialog { background:#F6F2FA; } QLabel { color:#1B1040; }")
    lay = QVBoxLayout(dlg)
    lay.setContentsMargins(0, 0, 0, 0)
    lay.setSpacing(0)
    head = QWidget()
    head.setObjectName("abouthead")
    head.setStyleSheet("#abouthead { background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #1D1548, stop:0.55 #4A1F6E, stop:1 #8A2150); }")
    hl = QHBoxLayout(head)
    hl.setContentsMargins(18, 14, 26, 14)
    hl.setSpacing(14)
    bp = _banner_pixmap(58)
    if bp is not None:
        b = QLabel()
        b.setPixmap(bp)
        hl.addWidget(b)
        bar = QWidget()
        bar.setFixedSize(2, 52)
        bar.setStyleSheet("background:rgba(255,255,255,0.25);")
        hl.addWidget(bar)
    t = QLabel(f"<span style='font-size:18px; font-weight:700; color:white'>{title}</span>"
               f"<br><span style='font-size:13px; color:#E9D5EE'>{subtitle}</span>")
    hl.addWidget(t)
    hl.addStretch()
    lay.addWidget(head)
    tb = QTextBrowser()
    tb.setFrameShape(tb.Shape.NoFrame)
    tb.setOpenExternalLinks(False)
    tb.setStyleSheet("QTextBrowser { background:#F6F2FA; color:#1B1040; font-size:13px; padding:8px 14px; }")
    tb.setHtml(html)
    lay.addWidget(tb, 1)
    row = QHBoxLayout()
    row.setContentsMargins(22, 8, 22, 16)
    row.addStretch()
    for label, cb in buttons:
        btn = QPushButton(label)
        btn.setCursor(Qt.PointingHandCursor)
        primary = cb is None
        if primary:
            btn.setDefault(True)
            btn.setStyleSheet("QPushButton{background:qlineargradient(x1:0,y1:0,x2:1,y2:0,stop:0 #FF6F8E,stop:1 #FFB05A); color:#2A1241; "
                              "border:1px solid #FF6F8E; border-radius:7px; padding:7px 22px; font-size:13px; font-weight:600;}")
            btn.clicked.connect(dlg.accept)
        else:
            btn.setStyleSheet("QPushButton{background:white; color:#1B1040; border:1px solid #D0C4E1; border-radius:7px; padding:7px 18px; font-size:13px;}"
                              "QPushButton:hover{background:#EDE6F4;}")
            btn.clicked.connect(lambda _=False, cb=cb: (dlg.accept(), QTimer.singleShot(0, cb)))
        row.addWidget(btn)
    lay.addLayout(row)
    dlg.setFixedSize(*POPUP_SIZE)
    return dlg


_HELP_CSS = ("<style>h3{color:#8A2150; margin:14px 0 4px 0; font-size:14px;} p{margin:4px 0;} li{margin:3px 0;} "
             "td{padding:3px 10px 3px 0; vertical-align:top;} td.k{font-weight:600; color:#4A1F6E; white-space:nowrap; padding-right:18px;}</style>")


def _esc(s):
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def show_quick_help(win, name):
    """Help > Quick tips: what the program is for, what you can do, how to do it"""
    key = _help_key(name)
    entry = _HELP_QUICK.get(key, ("", [], []))
    intro, can, how = (entry[0], [], entry[1]) if len(entry) == 2 else entry
    body = _HELP_CSS
    if intro:
        body += f"<p style='font-size:14px'>{_esc(intro)}</p>"
    if can:
        body += "<h3>What you can do</h3><ul>" + "".join(f"<li>{_esc(b)}</li>" for b in can) + "</ul>"
    if how:
        body += "<h3>How to do it</h3><ul>" + "".join(f"<li>{_esc(b)}</li>" for b in how) + "</ul>"
    more = _HELP_MORE.get(key)
    if more:
        body += f"<h3>{_esc(more[0])}</h3><ul>" + "".join(f"<li>{_esc(b)}</li>" for b in more[1]) + "</ul>"
    dlg = _help_window(win, "Quick tips", name, body, [("Shortcuts", lambda: show_all_shortcuts(win, name)), ("Close", None)])
    dlg.exec()


def show_all_shortcuts(win, name):
    """Help > Shortcuts: every key of the program, read from its real menus"""
    groups = [(g, its) for g, its in collect_shortcuts(win) if g.lower() != "help"]
    extra = _HELP_EXTRA.get(_help_key(name), [])
    body = _HELP_CSS + "<p>Every keyboard shortcut of this program, as it works on your computer.</p>"
    have = {k.lower() for _g, its in groups for k, _t in its}
    extra = [(g, [(_mac_keys(k), t) for k, t in its if _mac_keys(k).lower() not in have]) for g, its in extra]
    for g, items in groups + [(g, its) for g, its in extra if its]:
        body += f"<h3>{_esc(g)}</h3><table>" + "".join(f"<tr><td class='k'>{_esc(k)}</td><td>{_esc(t)}</td></tr>" for k, t in items) + "</table>"
    if not groups and not extra:
        body += "<p>This program has no keyboard shortcuts.</p>"
    dlg = _help_window(win, "Shortcuts", name, body, [("Close", None)])
    dlg.exec()


def _top_menus(mb):
    """the menus of a menu bar as {name: QMenu}. Found through the window's children, not QAction.menu():
    on some systems (Wayland, newer Python) that gives back a menu object that is already deleted"""
    out = {}
    try:
        acts = list(mb.actions())
    except RuntimeError:
        return out
    win = mb.window()
    for m in win.findChildren(QMenu):
        try:
            act = m.menuAction()
            if act in acts:
                out.setdefault(m.title().replace("&", "").strip(), m)
        except RuntimeError:
            continue
    return out


def _remove_top(mb, name):
    """take every top-level menu called name out of the menu bar (also ones whose object is gone)"""
    for a in list(mb.actions()):
        try:
            if a.text().replace("&", "").strip() == name:
                mb.removeAction(a)
        except RuntimeError:
            continue


def install_help_menu(win, title, on_about):
    """Help > Quick tips, Shortcuts, About - exactly the same in every Digonto program"""
    from PySide6.QtGui import QAction
    mb = win.menuBar() if hasattr(win, "menuBar") else None
    if mb is None:
        return False
    name = QApplication.applicationDisplayName()
    if not _help_key(name):
        name = title
    menus = _top_menus(mb)
    mine = getattr(win, "_digonto_help_menu", None)
    try:
        if mine is not None and mine.menuAction() in mb.actions():
            _fix_roles(mine)
            return True
    except RuntimeError:
        pass
    # the program's own Help items go away; anything that is not help (Sheets: Function list) moves to Insert / Tools
    keep = []
    old = menus.get("Help")
    if old is not None:
        try:
            for a in list(old.actions()):
                tl = a.text().lower().replace("&", "")
                if not a.isSeparator() and not any(w in tl for w in ("tip", "shortcut", "quick help", "about")):
                    keep.append(a)
        except RuntimeError:
            keep = []
    _remove_top(mb, "Help")                              # always a new, clean Help menu
    if keep:
        host = next((menus[n] for n in ("Insert", "Tools", "Data") if n in menus), None)
        if host is not None:
            try:
                host.addSeparator()
                for a in keep:
                    host.addAction(a)
            except RuntimeError:
                pass
    hmenu = QMenu("Help", win)
    win._digonto_help_menu = hmenu                      # keep the Python object alive with the window
    mb.addMenu(hmenu)
    hmenu.setProperty("_digonto_help", True)
    tips = QAction("Quick tips", hmenu)
    tips.triggered.connect(lambda: show_quick_help(win, name))
    keys = QAction("Shortcuts", hmenu)
    keys.triggered.connect(lambda: show_all_shortcuts(win, name))
    about = QAction("About", hmenu)
    about.triggered.connect(lambda: on_about())
    hmenu.addAction(tips)
    hmenu.addAction(keys)
    hmenu.addSeparator()
    hmenu.addAction(about)
    _fix_roles(hmenu)
    if sys.platform == "darwin":                         # macOS: also "About ..." in the program menu, as Mac users expect
        mac_about = QAction("About " + title, win)
        mac_about.setMenuRole(QAction.AboutRole)
        mac_about.triggered.connect(lambda: on_about())
        host = next((m for n, m in _top_menus(mb).items() if m is not hmenu), None)
        if host is not None:
            host.addAction(mac_about)
    return True


def _fix_roles(menu):
    """Qt on macOS moves items called About/Settings/Quit into the program menu; in Help they must stay where they are"""
    from PySide6.QtGui import QAction
    for a in menu.actions():
        a.setMenuRole(QAction.NoRole)


def _keep_help(header, title, on_about):
    """install the Help menu as soon as the header sits in a window with a menu bar, and again each time it is shown"""
    from PySide6.QtCore import QObject, QEvent

    class _Watch(QObject):
        def eventFilter(self, obj, ev):
            if ev.type() in (QEvent.Show, QEvent.WindowActivate):
                install_help_menu(obj, title, on_about)
            return False

    def attempt(n=0):
        try:
            w = header.window()
        except RuntimeError:
            return
        if w is not header and hasattr(w, "menuBar"):
            install_help_menu(w, title, on_about)
            if not w.property("_help_watch"):
                w.setProperty("_help_watch", True)
                f = _Watch(w)
                w.installEventFilter(f)
                w._digonto_help_watch = f
            if n < 3:                                    # the program may add its own menus a little later
                QTimer.singleShot(400, lambda: attempt(n + 1))
        elif n < 60:
            QTimer.singleShot(100, lambda: attempt(n + 1))
    QTimer.singleShot(0, attempt)


# ---- fonts a file uses that are not installed (Images, Vector, Write, Sheets)
def font_installed(family):
    """is this font family on this computer? (spaces, case and dashes do not matter)"""
    if not family:
        return True
    from PySide6.QtGui import QFontDatabase
    key = lambda t: "".join(c for c in t.lower() if c.isalnum())   # noqa: E731
    want = key(family)
    generic = {"sansserif", "serif", "monospace", "sans", "default", "systemui", "cursive", "fantasy"}
    if want in generic:
        return True
    return any(key(f) == want for f in QFontDatabase.families())


def missing_fonts(families):
    return sorted({f for f in families if f and not font_installed(f)}, key=str.lower)


def note_missing_fonts(parent, families):
    """one note after opening a file: every font it uses that is not installed"""
    miss = missing_fonts(families)
    if not miss:
        return
    from PySide6.QtWidgets import QMessageBox as _MB
    names = "\n".join("•  " + f for f in miss[:12]) + ("\n•  …" if len(miss) > 12 else "")
    one = len(miss) == 1
    _styled_question(parent, "Fonts not installed",
                     f"This file uses {'a font' if one else f'{len(miss)} fonts'} that {'is' if one else 'are'} "
                     f"not installed on this computer:\n\n{names}\n\nIt looks right as long as you don't edit "
                     "that text. Install the font first and open the file again, or the text will use the default "
                     "font when you edit it.", _MB.StandardButton.Ok)


def warn_missing_font(parent, family):
    """before editing a text whose font is missing: True = go on (with the default font), False = stop"""
    if font_installed(family):
        return True
    from PySide6.QtWidgets import QMessageBox as _MB
    SB = _MB.StandardButton
    r = _styled_question(parent, "Font not installed",
                         f"\"{family}\" is not installed on this computer.\n\nInstall the font first and open the file "
                         "again, or continue and this text will be replaced by the default font.",
                         SB.Ok | SB.Cancel, SB.Cancel, labels={SB.Ok: "Use default font"})
    return r == SB.Ok

# ================================================================================================================
# The common Digonto window parts: line icons, the left icon bar ("rail") and the start screen.
# Every program uses the same order: New, Open, Save, Export, Print - then its own icons - Settings at the bottom.
# ================================================================================================================
INK, SOFT, LINE, PINK, AMBER = "#2A1241", "#6B5F86", "#E7E1F0", "#FF6F8E", "#FFB05A"
ICON_INK = "#5A2A86"


def line_icon(kind, size=22, color=INK):
    """simple line icons drawn in code (sharp on every screen, no files to ship)"""
    import math
    from PySide6.QtCore import QPointF, QRectF
    from PySide6.QtGui import QFont, QPainter, QPainterPath, QPen
    pm = QPixmap(size * 2, size * 2)
    pm.fill(Qt.transparent)
    p = QPainter(pm)
    p.setRenderHint(QPainter.Antialiasing)
    p.scale(2 * size / 24, 2 * size / 24)
    p.setPen(QPen(QColor(color), 1.8, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
    p.setBrush(Qt.NoBrush)

    def L(x0, y0, x1, y1):
        p.drawLine(QPointF(x0, y0), QPointF(x1, y1))

    def R(x, y, w, h, r=2):
        p.drawRoundedRect(QRectF(x, y, w, h), r, r)

    def poly(*pts, close=True):
        path = QPainterPath()
        path.moveTo(*pts[0])
        for q in pts[1:]:
            path.lineTo(*q)
        if close:
            path.closeSubpath()
        p.drawPath(path)

    def txt(rect, s, pt=8):
        p.setFont(QFont("Sans", pt, QFont.Bold))
        p.drawText(QRectF(*rect), Qt.AlignCenter, s)

    if kind == "open":
        poly((3, 7), (9, 7), (11, 9), (21, 9), (21, 19), (3, 19))
    elif kind == "new":
        poly((6, 3), (14, 3), (19, 8), (19, 21), (6, 21)); L(12.5, 10, 12.5, 17); L(9, 13.5, 16, 13.5)
    elif kind == "file":
        poly((6, 3), (14, 3), (19, 8), (19, 21), (6, 21)); poly((14, 3), (14, 8), (19, 8), close=False)
    elif kind == "folder":
        poly((3, 6), (9, 6), (11, 8), (21, 8), (21, 19), (3, 19)); L(3, 11, 21, 11)
    elif kind == "save":
        R(4, 4, 16, 16); R(8, 4, 8, 5, 1); R(7.5, 13, 9, 7, 1)
    elif kind == "export":
        L(12, 15, 12, 4); L(8, 8, 12, 4); L(16, 8, 12, 4); poly((7, 11), (4, 11), (4, 21), (20, 21), (20, 11), (17, 11), close=False)
    elif kind == "print":
        R(7, 3, 10, 6, 1); R(3, 9, 18, 8); R(7, 14, 10, 7, 1)
    elif kind == "pen":
        poly((15, 4), (20, 9), (9, 20), (4, 20), (4, 15)); L(13, 6, 18, 11)
    elif kind == "pages":
        R(4, 3, 10, 13); R(10, 8, 10, 13)
    elif kind == "merge":
        R(3, 4, 7, 9); R(14, 4, 7, 9); L(6.5, 13, 12, 19); L(17.5, 13, 12, 19); L(12, 19, 12, 22)
    elif kind == "split":
        R(8, 3, 8, 8); L(12, 11, 12, 14); L(12, 14, 5, 19); L(12, 14, 19, 19); R(2, 18, 6, 4, 1); R(16, 18, 6, 4, 1)
    elif kind == "rotate":
        p.drawArc(QRectF(4, 4, 16, 16), 30 * 16, 290 * 16); L(19, 3, 19.5, 8); L(19.5, 8, 14.5, 8)
    elif kind == "organise":
        for x, y in ((3, 3), (13, 3), (3, 13), (13, 13)):
            R(x, y, 8, 8, 1.5)
    elif kind == "remove":
        R(5, 3, 14, 18); L(9, 9, 15, 15); L(15, 9, 9, 15)
    elif kind == "extract":
        R(3, 3, 11, 14); L(13, 16, 21, 16); L(18, 13, 21, 16); L(18, 19, 21, 16)
    elif kind == "numbers":
        R(5, 3, 14, 18); txt((5, 11, 14, 9), "12", 7)
    elif kind == "crop":
        L(6, 2, 6, 18); L(6, 18, 22, 18); L(2, 6, 18, 6); L(18, 6, 18, 22)
    elif kind == "img2pdf":
        R(3, 5, 18, 14); p.drawEllipse(QPointF(8, 10), 1.6, 1.6); L(3, 17, 10, 12); L(10, 12, 21, 18)
    elif kind == "word":
        R(5, 3, 14, 18); txt((5, 7, 14, 12), "W")
    elif kind == "textfile":
        R(5, 3, 14, 18); L(8, 8, 16, 8); L(8, 12, 16, 12); L(8, 16, 13, 16)
    elif kind == "text":
        L(5, 5, 19, 5); L(12, 5, 12, 20); L(9, 20, 15, 20)
    elif kind == "sign":
        path = QPainterPath(); path.moveTo(3, 15)
        for x in range(3, 22):
            path.lineTo(x, 15 - 4 * math.sin(x / 2.0))
        p.drawPath(path); L(3, 21, 21, 21)
    elif kind == "watermark":
        path = QPainterPath(); path.moveTo(12, 3); path.cubicTo(6, 11, 5, 14, 5, 15.5)
        path.cubicTo(5, 23, 19, 23, 19, 15.5); path.cubicTo(19, 14, 18, 11, 12, 3); p.drawPath(path)
    elif kind == "redact":
        R(5, 3, 14, 18); p.setBrush(QColor(color)); R(8, 9, 8, 3, 1); R(8, 14, 6, 3, 1)
    elif kind == "ocr":
        for a in ((3, 7, 3, 3), (3, 3, 7, 3), (17, 3, 21, 3), (21, 3, 21, 7), (3, 17, 3, 21), (3, 21, 7, 21),
                  (17, 21, 21, 21), (21, 21, 21, 17)):
            L(*a)
        txt((3, 6, 18, 12), "Aa")
    elif kind == "clean":
        L(14, 3, 9, 13); poly((5, 13), (13, 13), (15, 21), (3, 21)); L(18, 6, 21, 6); L(19.5, 4.5, 19.5, 7.5)
    elif kind == "blank":
        R(5, 3, 14, 18); p.setPen(QPen(QColor(color), 1.4, Qt.DashLine)); R(8, 7, 8, 10, 1)
    elif kind == "compress":
        L(12, 2, 12, 9); L(9, 6, 12, 9); L(15, 6, 12, 9); L(12, 22, 12, 15); L(9, 18, 12, 15); L(15, 18, 12, 15); L(4, 12, 20, 12)
    elif kind == "lock":
        R(5, 10, 14, 11); p.drawArc(QRectF(8, 4, 8, 12), 0, 180 * 16)
    elif kind == "unlock":
        R(5, 10, 14, 11); p.drawArc(QRectF(8, 4, 8, 12), 40 * 16, 140 * 16)
    elif kind == "info":
        p.drawEllipse(QRectF(3, 3, 18, 18)); L(12, 11, 12, 17); p.drawPoint(QPointF(12, 7.5))
    elif kind == "compare":
        R(3, 4, 8, 16); R(13, 4, 8, 16); L(5, 9, 9, 9); L(15, 9, 19, 9); L(5, 13, 9, 13)
    elif kind == "images":
        R(3, 6, 14, 12); R(7, 3, 14, 12)
    elif kind == "repair":
        L(5, 19, 14, 10); p.drawEllipse(QRectF(13, 3, 8, 8))
    elif kind == "star":
        pts = [(12 + (9 if i % 2 == 0 else 4) * math.sin(math.radians(i * 36)),
                12.5 - (9 if i % 2 == 0 else 4) * math.cos(math.radians(i * 36))) for i in range(10)]
        poly(*pts)
    elif kind == "back":
        L(15, 5, 8, 12); L(8, 12, 15, 19)
    elif kind == "settings":                       # a gear: 8 teeth around a ring, a hole in the middle
        path = QPainterPath()
        teeth, r_out, r_in = 8, 10.0, 7.6
        pts = []
        for i in range(teeth):
            a0 = (i / teeth) * 2 * math.pi
            w = math.pi / teeth
            for ang, rad in ((a0 - w * 0.45, r_in), (a0 - w * 0.28, r_out), (a0 + w * 0.28, r_out), (a0 + w * 0.45, r_in)):
                pts.append((12 + rad * math.cos(ang), 12 + rad * math.sin(ang)))
        path.moveTo(*pts[0])
        for q in pts[1:]:
            path.lineTo(*q)
        path.closeSubpath()
        from PySide6.QtGui import QLinearGradient
        g = QLinearGradient(QPointF(2, 2), QPointF(22, 22))     # the Digonto colours: pink to amber
        g.setColorAt(0, QColor(PINK))
        g.setColorAt(1, QColor(AMBER))
        p.setPen(QPen(g, 2.0, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
        p.drawPath(path)
        p.drawEllipse(QRectF(8.8, 8.8, 6.4, 6.4))
    elif kind == "record":
        p.drawEllipse(QRectF(3, 3, 18, 18)); p.setBrush(QColor("#E0457B")); p.setPen(Qt.NoPen); p.drawEllipse(QRectF(7.5, 7.5, 9, 9))
    elif kind == "play":
        poly((8, 5), (19, 12), (8, 19))
    elif kind == "playlist":
        L(4, 6, 14, 6); L(4, 11, 14, 11); L(4, 16, 10, 16); poly((15, 13), (21, 16.5), (15, 20))
    elif kind == "terminal":
        R(3, 4, 18, 16); L(7, 9, 10, 12); L(10, 12, 7, 15); L(12, 15, 16, 15)
    elif kind == "server":
        R(4, 4, 16, 7); R(4, 13, 16, 7); p.drawPoint(QPointF(7.5, 7.5)); p.drawPoint(QPointF(7.5, 16.5))
    elif kind == "qr":
        R(3, 3, 7, 7, 1); R(14, 3, 7, 7, 1); R(3, 14, 7, 7, 1); L(14, 14, 16, 14); L(19, 14, 21, 14); L(14, 17, 14, 21)
        L(17, 17, 21, 17); L(17, 21, 21, 21)
    elif kind == "wand":
        L(4, 20, 15, 9); L(17, 3, 17, 7); L(15, 5, 19, 5); L(20, 9, 20, 11); L(19, 10, 21, 10)
    elif kind == "search":
        p.drawEllipse(QRectF(4, 4, 11, 11)); L(13.5, 13.5, 20, 20)
    elif kind == "close":
        L(6, 6, 18, 18); L(18, 6, 6, 18)
    p.end()
    pm.setDevicePixelRatio(2)
    return QIcon(pm)


SHELL_QSS = f"""
QFrame#dgRail {{ background: white; border-right: 1px solid {LINE}; }}
QFrame#dgRail QToolButton {{ border: none; border-radius: 10px; padding: 6px; background: transparent; }}
QFrame#dgRail QToolButton:hover {{ background: #F1EAF8; }}
QFrame#dgRail QToolButton:checked {{ background: #FCE4EA; }}
QFrame#dgRail QToolButton:disabled {{ background: transparent; }}
QWidget#dgStart {{ background: #F7F4FB; }}
QWidget#dgStart QLabel {{ background: transparent; }}
QWidget#dgStart[dropping="true"] {{ background: #FCEFF3; border: 2px dashed {PINK}; border-radius: 16px; }}
QLabel#dgSec {{ color: {SOFT}; font-size: 11px; font-weight: 700; letter-spacing: 1px; }}
QPushButton#dgRecent {{ border: none; background: transparent; color: {INK}; font-size: 13px; padding: 3px 8px;
                        font-weight: 500; text-align: center; }}
QPushButton#dgRecent:hover {{ color: #C2395C; text-decoration: underline; }}
QPushButton#dgPrimary {{ border: none; border-radius: 10px; padding: 9px 18px; color: {INK}; font-weight: 600;
    background: qlineargradient(x1:0,y1:0,x2:1,y2:0, stop:0 {PINK}, stop:1 {AMBER}); }}
QPushButton#dgPrimary:hover {{ background: qlineargradient(x1:0,y1:0,x2:1,y2:0, stop:0 #FF5F82, stop:1 #FFA444); }}
QPushButton#dgPrimary:disabled {{ background: #E9E3F0; color: #A79CB8; }}
QPushButton#dgPlain {{ background: white; border: 1px solid #D9D0E6; border-radius: 10px; padding: 9px 18px;
                       color: {INK}; font-weight: 600; }}
QPushButton#dgPlain:hover {{ background: #F7F2FB; }}
"""


class Rail(QWidget):
    """the left icon bar.  items: list of (key, icon kind, tooltip, callback) - None for a divider;
    `bottom` the same for the icons at the bottom (settings).  Keys can be made checkable."""

    def __init__(self, items, bottom=(), width=58):
        from PySide6.QtWidgets import QFrame, QToolButton
        super().__init__()
        self.setObjectName("dgRailHolder")
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        frame = QFrame()
        frame.setObjectName("dgRail")
        frame.setFixedWidth(width)
        frame.setStyleSheet(SHELL_QSS)
        lay.addWidget(frame)
        v = QVBoxLayout(frame)
        v.setContentsMargins(8, 10, 8, 10)
        v.setSpacing(6)
        self.buttons = {}

        def add(item, color=INK):
            if item is None:
                s = QFrame()
                s.setFixedHeight(1)
                s.setStyleSheet(f"background:{LINE};")
                v.addWidget(s)
                return
            key, kind, tip, fn = item
            b = QToolButton()
            b.setIcon(line_icon(kind, 22, color))
            b.setIconSize(QSize(22, 22))
            b.setFixedSize(42, 42)
            b.setToolTip(tip)
            b.setCursor(Qt.PointingHandCursor)
            if fn:
                b.clicked.connect(fn)
            self.buttons[key] = b
            v.addWidget(b, 0, Qt.AlignHCenter)

        for it in items:
            add(it)
        v.addStretch(1)
        for it in bottom:
            add(it, INK)

    def button(self, key):
        return self.buttons[key]

    def set_enabled(self, keys, flag):
        for k in keys:
            if k in self.buttons:
                self.buttons[k].setEnabled(flag)


class StartScreen(QWidget):
    """the plain start screen: Digonto logo, a line of text, the main buttons, 'or drop files here', recent files.
    buttons: list of (label, icon kind, callback, primary?).  recent(): list of paths.  The window does the
    dropping; call set_dropping(True/False) from its drag events to light the screen up."""

    def __init__(self, tagline, buttons, drop_text, recent=None, open_path=None, max_recent=6):
        super().__init__()
        self.setObjectName("dgStart")
        self.setAttribute(Qt.WA_StyledBackground, True)
        self.setStyleSheet(SHELL_QSS)
        self._recent, self._open = recent, open_path
        self.max_recent = max_recent
        v = QVBoxLayout(self)
        v.setContentsMargins(28, 24, 28, 24)
        v.addStretch(2)
        ban = QLabel()
        pm = _banner_pixmap(75)
        if pm is not None:
            ban.setPixmap(pm)
        ban.setAlignment(Qt.AlignCenter)
        v.addWidget(ban)
        t = QLabel(tagline)
        t.setAlignment(Qt.AlignCenter)
        t.setStyleSheet(f"color:{SOFT}; font-size:14px; margin-top:6px;")
        v.addWidget(t)
        row = QHBoxLayout()
        row.addStretch(1)
        self.buttons = []
        for label, kind, fn, prim in buttons:
            b = QPushButton("  " + label)
            b.setObjectName("dgPrimary" if prim else "dgPlain")
            b.setIcon(line_icon(kind, 18))
            b.setIconSize(QSize(18, 18))
            b.setCursor(Qt.PointingHandCursor)
            b.clicked.connect(fn)
            row.addWidget(b)
            self.buttons.append(b)
        row.addStretch(1)
        v.addSpacing(14)
        v.addLayout(row)
        drop = QLabel(drop_text)
        drop.setAlignment(Qt.AlignCenter)
        drop.setStyleSheet(f"color:{SOFT}; font-size:12.5px; margin-top:10px;")
        v.addWidget(drop)
        v.addSpacing(26)
        self.rec_title = QLabel("RECENT")
        self.rec_title.setObjectName("dgSec")
        self.rec_title.setAlignment(Qt.AlignCenter)
        v.addWidget(self.rec_title)
        self.rec_box = QVBoxLayout()
        self.rec_box.setSpacing(0)
        v.addLayout(self.rec_box)
        v.addStretch(3)
        self.refresh()

    def refresh(self):
        while self.rec_box.count():
            w = self.rec_box.takeAt(0).widget()
            if w:
                w.deleteLater()
        items = [p for p in (self._recent() if self._recent else []) if os.path.exists(p)][:self.max_recent]
        self.rec_title.setVisible(bool(items))
        for pth in items:
            b = QPushButton(os.path.basename(pth))
            b.setObjectName("dgRecent")
            b.setToolTip(pth)
            b.setCursor(Qt.PointingHandCursor)
            b.clicked.connect(lambda _=False, q=pth: self._open and self._open(q))
            self.rec_box.addWidget(b, 0, Qt.AlignHCenter)

    def set_dropping(self, flag):
        self.setProperty("dropping", "true" if flag else "false")
        self.style().unpolish(self)
        self.style().polish(self)


def recent_paths(slug, limit=12):
    """the files this program worked on last (from the list Digonto Studio shows), newest first"""
    try:
        with open(os.path.join(base_dir(), "recent.json"), encoding="utf-8") as f:
            items = [r for r in json.load(f) if isinstance(r, dict) and r.get("app") == slug]
    except (OSError, ValueError):
        return []
    return [r["path"] for r in items if os.path.exists(r.get("path", ""))][:limit]


def open_external(target):
    """open a folder, a file or a web address with the system's own program. Inside the built Digonto
    programs on Linux the library paths of the bundle must not reach the file manager (it would load our
    libraries and quietly fail), so it gets the environment the person started the program with."""
    import subprocess
    target = str(target)
    is_url = "://" in target and not target.startswith("file://")
    if sys.platform == "win32":
        os.startfile(target)                                       # noqa: S606
        return
    if sys.platform == "darwin":
        subprocess.Popen(["open", target])
        return
    env = dict(os.environ)
    for var in ("LD_LIBRARY_PATH", "QT_PLUGIN_PATH", "QT_QPA_PLATFORM_PLUGIN_PATH", "GDK_PIXBUF_MODULE_FILE",
                "GIO_MODULE_DIR", "GTK_PATH", "XDG_DATA_DIRS", "SSL_CERT_FILE", "PYTHONPATH", "PYTHONHOME"):
        orig = env.pop(var + "_ORIG", None)                        # PyInstaller keeps the original value here
        if orig is not None:
            env[var] = orig
        elif var in ("LD_LIBRARY_PATH", "QT_PLUGIN_PATH", "QT_QPA_PLATFORM_PLUGIN_PATH", "PYTHONPATH", "PYTHONHOME"):
            env.pop(var, None)
    if not is_url and not os.path.exists(target.replace("file://", "")):
        return
    try:
        subprocess.Popen(["xdg-open", target], env=env, start_new_session=True,
                         stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except OSError:
        from PySide6.QtCore import QUrl
        from PySide6.QtGui import QDesktopServices
        QDesktopServices.openUrl(QUrl(target) if is_url else QUrl.fromLocalFile(target))
