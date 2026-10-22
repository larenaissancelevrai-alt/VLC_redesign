"""Icônes vectorielles (SVG intégré) recolorées à la volée.

Les PNG du dossier assets/ sont des exports de maquette, pas des icônes
utilisables : on dessine donc un petit jeu d'icônes cohérent en SVG.
"""

from PySide6.QtCore import QByteArray, Qt
from PySide6.QtGui import QIcon, QPainter, QPixmap
from PySide6.QtSvg import QSvgRenderer

_SVG = (
    '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" '
    'stroke="@C@" stroke-width="1.8" stroke-linecap="round" '
    'stroke-linejoin="round">@BODY@</svg>'
)

_ICONS = {
    # navigation
    "home": '<path d="M4 11l8-7 8 7v8a1 1 0 0 1-1 1h-4v-6H9v6H5a1 1 0 0 1-1-1z"/>',
    "video": '<rect x="3" y="5" width="18" height="14" rx="2.5"/>'
             '<path d="M10 9.5v5l4.5-2.5z" fill="@C@"/>',
    "music": '<path d="M9 18V6l10-2v12"/><circle cx="6.5" cy="18" r="2.5"/>'
             '<circle cx="16.5" cy="16" r="2.5"/>',
    "network": '<circle cx="12" cy="12" r="1.6" fill="@C@"/>'
               '<path d="M8.5 8.5a5 5 0 0 0 0 7M15.5 8.5a5 5 0 0 1 0 7'
               'M5.5 5.5a9 9 0 0 0 0 13M18.5 5.5a9 9 0 0 1 0 13"/>',
    "playlist": '<path d="M4 6h12M4 11h12M4 16h6"/>'
                '<path d="M14 14v6l5-3z" fill="@C@"/>',
    "recent": '<path d="M4 12a8 8 0 1 0 2.4-5.7"/><path d="M4 4v4h4"/>'
              '<path d="M12 8v4l3 2"/>',
    "favorite": '<path d="m12 3 2.7 5.5 6.1.9-4.4 4.3 1 6.1-5.4-2.9-5.4 2.9 1-6.1-4.4-4.3 6.1-.9z"/>',
    "user": '<circle cx="12" cy="8" r="3.2"/><path d="M5 20a7 7 0 0 1 14 0"/>',
    "more": '<circle cx="5" cy="12" r="1" fill="@C@"/>'
            '<circle cx="12" cy="12" r="1" fill="@C@"/>'
            '<circle cx="19" cy="12" r="1" fill="@C@"/>',
    "settings": '<circle cx="12" cy="12" r="3.5"/>'
                '<path d="M12 2.8v2.1M12 19.1v2.1M21.2 12h-2.1M4.9 12H2.8'
                'M18.5 5.5 17 7M7 17l-1.5 1.5M18.5 18.5 17 17M7 7 5.5 5.5"/>',
    "add": '<path d="M12 5v14M5 12h14"/>',
    "download": '<path d="M12 3v12m-5-5 5 5 5-5"/><path d="M4 17v3h16v-3"/>',
    "file": '<path d="M6 3h8l5 5v13H6z"/><path d="M14 3v5h5"/>',
    "globe": '<circle cx="12" cy="12" r="9"/><path d="M3 12h18M12 3a15 15 0 0 1 0 18M12 3a15 15 0 0 0 0 18"/>',
    "folder": '<path d="M3 7a2 2 0 0 1 2-2h4l2 2h8a2 2 0 0 1 2 2v8a2 2 0 0 1-2 2H5'
              'a2 2 0 0 1-2-2z"/>',
    # en-tête
    "search": '<circle cx="11" cy="11" r="6.5"/><path d="M20 20l-4.2-4.2"/>',
    "sort": '<path d="M8 5v14M8 19l-3-3M8 19l3-3M16 19V5M16 5l-3 3M16 5l3 3"/>',
    # lecteur
    "play": '<path d="M7 4.5v15l13-7.5z" fill="@C@"/>',
    "pause": '<rect x="6" y="5" width="4" height="14" rx="1" fill="@C@"/>'
             '<rect x="14" y="5" width="4" height="14" rx="1" fill="@C@"/>',
    "prev": '<path d="M6 5v14"/><path d="M19 5v14L9 12z" fill="@C@"/>',
    "next": '<path d="M18 5v14"/><path d="M5 5v14l10-7z" fill="@C@"/>',
    "stop": '<rect x="6" y="6" width="12" height="12" rx="2" fill="@C@"/>',
    "volume": '<path d="M4 9.5h3.5L12 6v12l-4.5-3.5H4z" fill="@C@"/>'
              '<path d="M15.5 9a4 4 0 0 1 0 6M18 6.5a7.5 7.5 0 0 1 0 11"/>',
    "mute": '<path d="M4 9.5h3.5L12 6v12l-4.5-3.5H4z" fill="@C@"/>'
            '<path d="M16 9.5l5 5M21 9.5l-5 5"/>',
    "audio": '<path d="M3 10v4M7 7v10M11 4v16M15 8v8M19 11v2"/>',
    "subtitles": '<rect x="3" y="5" width="18" height="14" rx="3"/>'
                 '<path d="M7 11h4M13 11h4M7 15h2M11 15h6"/>',
    "fullscreen": '<path d="M4 9V4h5M20 9V4h-5M4 15v5h5M20 15v5h-5"/>',
    "fullscreen_exit": '<path d="M9 4v5H4M15 4v5h5M9 20v-5H4M15 20v-5h5"/>',
    "repeat": '<path d="M17 2l4 4-4 4"/><path d="M3 11V9a3 3 0 0 1 3-3h15M7 22l-4-4 4-4"/><path d="M21 13v2a3 3 0 0 1-3 3H3"/>',
    "repeat_one": '<path d="M17 2l4 4-4 4"/><path d="M3 11V9a3 3 0 0 1 3-3h15M7 22l-4-4 4-4"/><path d="M21 13v2a3 3 0 0 1-3 3H3"/><path d="M12 10v5m-1-4 1-1 1 1"/>',
    "lyrics": '<path d="M4 5h16M4 10h16M4 15h10M4 20h8"/><path d="M17 15l4 2.5-4 2.5z" fill="@C@"/>',
    "chevron_down": '<path d="m5 9 7 7 7-7"/>',
    "close": '<path d="m6 6 12 12M18 6 6 18"/>',
    "menu": '<path d="M4 6h16M4 12h16M4 18h16"/>',
    "queue": '<path d="M4 5h11M4 10h11M4 15h7M17 14v6m-3-3h6"/>',
}


def pixmap(name, color, size=24):
    """Rend l'icône `name` dans la couleur `color` (écrans haute densité inclus)."""
    ratio = 2
    body = _ICONS.get(name, '<circle cx="12" cy="12" r="9"/><path d="M3 12h18M12 3a15 15 0 0 1 0 18M12 3a15 15 0 0 0 0 18"/>')
    svg = _SVG.replace("@BODY@", body).replace("@C@", color)
    renderer = QSvgRenderer(QByteArray(svg.encode("utf-8")))
    pm = QPixmap(size * ratio, size * ratio)
    pm.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pm)
    renderer.render(painter)
    painter.end()
    pm.setDevicePixelRatio(ratio)
    return pm


def icon(name, color, active=None, size=24):
    """QIcon avec une couleur normale et une couleur « coché » (état On)."""
    ic = QIcon()
    ic.addPixmap(pixmap(name, color, size), QIcon.Mode.Normal, QIcon.State.Off)
    ic.addPixmap(pixmap(name, active or color, size), QIcon.Mode.Normal, QIcon.State.On)
    return ic
