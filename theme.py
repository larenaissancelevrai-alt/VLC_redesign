"""Couleurs et feuille de style (QSS) de l'application.

Les valeurs sont tirées de la maquette : fond quasi noir, panneaux gris très
foncé, texte gris clair et une couleur d'accent (orange par défaut).
"""

from string import Template
from PySide6.QtGui import QColor

ACCENT = "#e8851a"

PALETTE = {
    "bg": "#0e0e0f",
    "panel": "#171718",
    "panel_hi": "#202022",
    "field": "#0a0a0a",
    "border": "#262629",
    "text": "#e4e4e7",
    "dim": "#8d8d94",
    "hover": "#232326",
}

FONT = '"Inter", "Segoe UI", "SF Pro Text", "Helvetica Neue", Arial, sans-serif'


def _mix(a, b, t):
    """Mélange deux couleurs hexadécimales (t=0 → a, t=1 → b)."""
    ca, cb = QColor(a), QColor(b)
    return QColor(
        round(ca.red() * (1 - t) + cb.red() * t),
        round(ca.green() * (1 - t) + cb.green() * t),
        round(ca.blue() * (1 - t) + cb.blue() * t),
    ).name()


def _relative_luminance(color):
    qcolor = QColor(color)
    channels = [qcolor.redF(), qcolor.greenF(), qcolor.blueF()]
    linear = [value / 12.92 if value <= 0.04045 else ((value + 0.055) / 1.055) ** 2.4 for value in channels]
    return 0.2126 * linear[0] + 0.7152 * linear[1] + 0.0722 * linear[2]


def _contrast_ratio(first, second):
    luminances = sorted((_relative_luminance(first), _relative_luminance(second)), reverse=True)
    return (luminances[0] + 0.05) / (luminances[1] + 0.05)


def _contrast_text(background):
    """Choose whichever of near-black or white has stronger contrast."""
    luminance = _relative_luminance(background)
    white_ratio = 1.05 / (luminance + 0.05)
    dark_ratio = (luminance + 0.05) / 0.05
    return "#ffffff" if white_ratio >= dark_ratio else "#17171a"


def colors(accent=ACCENT, background=None, element_color=None):
    """Return a palette with independent page background and UI surfaces."""
    c = dict(PALETTE)
    bg = QColor(background) if background else QColor(c["bg"])
    if bg.isValid():
        c["bg"] = bg.name()
        c["text"] = _contrast_text(c["bg"])
        c["dim"] = _mix(c["text"], c["bg"], 0.38)

    surface = QColor(element_color) if element_color else QColor(c["panel"])
    c["surface_text"] = _contrast_text(c["panel"])
    c["surface_dim"] = _mix(c["surface_text"], c["panel"], 0.38)
    if surface.isValid():
        # Keep interface panels perceptibly separate from the page background,
        # even when the user picks two nearly identical dark colors.
        target = "#ffffff" if _relative_luminance(c["bg"]) < 0.18 else "#000000"
        for _ in range(24):
            if _contrast_ratio(surface.name(), c["bg"]) >= 1.35:
                break
            surface = QColor(_mix(surface.name(), target, 0.04))
        c["panel"] = surface.name()
        c["surface_text"] = _contrast_text(c["panel"])
        c["surface_dim"] = _mix(c["surface_text"], c["panel"], 0.38)
        if surface.lightness() < 128:
            c.update({
                "panel_hi": _mix(c["panel"], "#ffffff", 0.11),
                "field": _mix(c["panel"], "#000000", 0.22),
                "border": _mix(c["panel"], "#ffffff", 0.15),
                "hover": _mix(c["panel"], "#ffffff", 0.13),
            })
        else:
            c.update({
                "panel_hi": _mix(c["panel"], "#000000", 0.09),
                "field": _mix(c["panel"], "#000000", 0.10),
                "border": _mix(c["panel"], "#000000", 0.16),
                "hover": _mix(c["panel"], "#000000", 0.10),
            })
    c["accent"] = accent
    c["accent_hi"] = _mix(accent, "#ffffff", 0.18)
    c["accent_dark"] = _mix(accent, c["bg"], 0.70)
    c["on_accent"] = _contrast_text(accent)
    c["on_accent_hi"] = _contrast_text(c["accent_hi"])
    c["field_text"] = _contrast_text(c["field"])
    c["selected_text"] = _contrast_text(c["accent_dark"])
    return c

_QSS = Template("""
QMainWindow, QDialog, QMessageBox, QInputDialog, QFileDialog { background: $bg; }

QWidget {
    background: transparent;
    color: $text;
    font-family: $font;
    font-size: 13px;
}

#video { background: $bg; }
#audio_page { background: transparent; }

/* ---------- Barre latérale ---------- */
#sidebar { background: transparent; color: $surface_text; }
#sidebarSurface { background: $panel; border-radius: 12px; }
#sidebarContent { background: transparent; color: $surface_text; }
#sidebar QWidget { color: $surface_text; }
#logo { color: $surface_text; font-size: 15px; font-weight: 600; padding: 6px 10px; }
#section { color: $surface_dim; font-size: 11px; font-weight: 600; padding: 6px 10px; }
#playlistSidebar { background: $panel; color: $surface_text; border: 1px solid $border; border-radius: 12px; }
#playlistSidebar QWidget { color: $surface_text; }
#playlistSidebar QLabel#sectionTitle { font-size: 16px; }
#playlistTracks { background: $panel; color: $surface_text; font-size: 14px; }
#playlistTracks::item { padding: 8px 7px; min-height: 22px; border-radius: 6px; }
#playlistHide { padding: 5px 9px; font-size: 12px; }

QPushButton#nav {
    text-align: left;
    border: none;
    border-radius: 8px;
    padding: 10px 12px;
    color: $surface_dim;
    background: transparent;
}
QPushButton#nav:hover { background: $hover; color: $surface_text; }
QPushButton#nav:checked { background: $panel; color: $surface_text; }
QPushButton#nav[compact="true"] { text-align: center; padding: 10px 0px; }

/* ---------- Contenu ---------- */
#title { font-size: 22px; font-weight: 600; }
#dim { color: $dim; }
#empty { color: $dim; font-size: 14px; }

QLineEdit#search {
    background: $panel;
    border: 1px solid $border;
    border-radius: 10px;
    padding: 8px 12px;
    color: $surface_text;
    selection-background-color: $accent;
    min-width: 220px;
}
QLineEdit#search:focus { border: 1px solid $accent; }

QListWidget { background: transparent; border: none; outline: none; }
QListWidget::item:selected { background: $accent_dark; color: $selected_text; border-radius: 6px; }

/* ---------- Boutons ---------- */
QToolButton {
    background: transparent;
    border: none;
    border-radius: 8px;
    padding: 7px;
}
QToolButton:hover { background: $hover; }
QToolButton::menu-indicator { image: none; width: 0px; }
QToolButton#profileCard {
    background: transparent;
    border: 2px solid transparent;
    border-radius: 14px;
    padding: 8px;
    color: $text;
    font-size: 14px;
    font-weight: 600;
    text-align: center;
}
QToolButton#profileCard:hover { background: $panel; border-color: $border; }
QToolButton#profileCard:checked { background: $panel; border-color: $accent; }
QPushButton#danger { color: #ff7474; border-color: #713a3a; }
QPushButton#danger:hover { background: #572b2b; color: #ffffff; border-color: #a64b4b; }

QToolButton#play {
    background: $accent;
    border-radius: 8px;
    padding: 7px 16px;
}
QToolButton#play:hover { background: $accent_hi; }

/* ---------- Barres de contrôle ---------- */
#controls { background: $panel; color: $accent; border-top: 1px solid $border; }
#controls QWidget { color: $accent; }
#nowplaying {
    background: $panel;
    color: $accent;
    border: 1px solid $border;
    border-radius: 12px;
}
#settingsCard { background: $panel; color: $accent; border: 1px solid $border; border-radius: 14px; }
#settingsCard QWidget { color: $accent; }
#sectionTitle { font-size: 17px; font-weight: 600; color: $text; }
#time { color: $dim; font-size: 12px; }
#track_title { font-size: 20px; font-weight: 600; }

/* ---------- Sliders ---------- */
QSlider::groove:horizontal { height: 8px; background: $field; border-radius: 4px; }
QSlider::sub-page:horizontal { background: $accent_dark; border-radius: 4px; }
QSlider::add-page:horizontal { background: $field; border-radius: 4px; }
QSlider::handle:horizontal {
    background: $accent;
    width: 6px;
    height: 16px;
    margin: -4px 0px;
    border-radius: 3px;
}

/* ---------- Barres de défilement ---------- */
QScrollBar:vertical { background: transparent; width: 10px; margin: 0px; }
QScrollBar::handle:vertical { background: $border; border-radius: 5px; min-height: 30px; }
QScrollBar::handle:vertical:hover { background: $dim; }
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0px; }
QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical { background: transparent; }

/* ---------- Menus et infobulles ---------- */
QMenu {
    background: $panel_hi;
    color: $surface_text;
    border: 1px solid $border;
    border-radius: 10px;
    padding: 6px;
}
QMenu::item { padding: 8px 28px 8px 14px; border-radius: 6px; }
QMenu::item:selected { background: $hover; }
QMenu::item:disabled { color: $dim; }
QMenu::separator { height: 1px; background: $border; margin: 6px 8px; }

QToolTip {
    background: $panel_hi;
    color: $surface_text;
    border: 1px solid $border;
    padding: 4px 8px;
}

QPushButton {
    background-color: $accent;
    color: $on_accent;
    border: 1px solid $accent;
    border-radius: 8px;
    padding: 8px 16px;
}
QPushButton:hover { background-color: $accent_hi; color: $on_accent_hi; border-color: $accent_hi; }
QPushButton:disabled { background-color: $panel_hi; color: $surface_dim; border-color: $border; }

/* Les boutons de navigation restent transparents au repos. */
QPushButton#nav {
    background-color: $panel;
    color: $surface_dim;
    border: none;
}
QPushButton#nav:hover {
    background-color: $hover;
    color: $surface_text;
    border: none;
}
QPushButton#nav:checked {
    background-color: $panel;
    color: $surface_text;
    border: none;
}
QPushButton#nav:checked:hover {
    background-color: $hover;
    color: $surface_text;
    border: none;
}

QLineEdit, QComboBox, QSpinBox, QDoubleSpinBox, QTextEdit, QPlainTextEdit {
    background-color: $field;
    color: $field_text;
    border: 1px solid $border;
    selection-background-color: $accent;
}
QComboBox QAbstractItemView { background: $panel_hi; color: $surface_text; selection-background-color: $accent_dark; }
""")


def stylesheet(accent=ACCENT, background=None, background_image=None, element_color=None):
    values = colors(accent, background, element_color)
    values["font"] = FONT
    result = _QSS.substitute(values)
    return result
