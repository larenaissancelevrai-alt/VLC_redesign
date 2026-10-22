"""Widgets sur mesure : zone vidéo, sliders, barre de volume VLC, paroles, cartes, pochettes."""

import hashlib
import os
import shutil
import subprocess
import sys
import urllib.request
from pathlib import Path

from PySide6.QtCore import (
    QEasingCurve, QObject, QPoint, QPointF, QPropertyAnimation, QRect, QRectF,
    QRunnable, QSize, Qt, QTimer, Signal
)
from PySide6.QtGui import (
    QBrush, QColor, QLinearGradient, QPainter, QPainterPath, QPen, QPixmap
)
from PySide6.QtWidgets import (
    QFrame, QLabel, QScrollArea, QSlider, QStyle, QStyledItemDelegate,
    QVBoxLayout, QWidget
)

import icons
import tags

ROLE_PATH = Qt.ItemDataRole.UserRole
ROLE_KIND = Qt.ItemDataRole.UserRole + 1
ROLE_THUMB = Qt.ItemDataRole.UserRole + 2
ROLE_SUBTITLE = Qt.ItemDataRole.UserRole + 3     # 2e ligne (artiste, nombre de titres…)
ROLE_REAL = Qt.ItemDataRole.UserRole + 4         # True si la vignette est une vraie pochette

CACHE_DIR = Path.home() / ".vlc_redesign" / "thumbs"
USER_AGENT = "VLCRedesign/1.0 (lecteur multimedia personnel)"


# --------------------------------------------------------------------- slider
class ClickSlider(QSlider):
    """Slider horizontal où un clic saute directement à la position cliquée.

    `seeked(valeur)` n'est émis que pour une action de l'utilisateur (clic ou
    glisser), jamais quand le programme appelle setValue().
    """

    seeked = Signal(int)

    def __init__(self, parent=None):
        super().__init__(Qt.Orientation.Horizontal, parent)
        self._dragging = False
        self.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.setCursor(Qt.CursorShape.PointingHandCursor)

    @property
    def dragging(self):
        return self._dragging

    def _apply(self, event):
        value = QStyle.sliderValueFromPosition(
            self.minimum(), self.maximum(),
            int(event.position().x()), max(1, self.width())
        )
        self.setValue(value)
        self.seeked.emit(value)

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self._dragging = True
            self._apply(event)
            event.accept()
        else:
            super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if self._dragging:
            self._apply(event)
            event.accept()
        else:
            super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        if self._dragging and event.button() == Qt.MouseButton.LeftButton:
            self._dragging = False
            event.accept()
        else:
            super().mouseReleaseEvent(event)


# ------------------------------------------------------------ barre de volume VLC
class VolumeBar(QWidget):
    """Barre de volume « à la VLC » : une rampe qui grandit, du vert au rouge.

    Va de 0 à 125 % (comme VLC) ; le trait marque 100 %. Molette = ±5 %.
    `changed(valeur)` n'est émis que pour une action de l'utilisateur.
    """

    changed = Signal(int)

    def __init__(self, maximum=125, parent=None):
        super().__init__(parent)
        self._max = maximum
        self._value = 0
        self._muted = False
        self._dragging = False
        self.colors = {}
        self.setFixedSize(132, 28)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFocusPolicy(Qt.FocusPolicy.NoFocus)

    # --- état -------------------------------------------------------------
    def value(self):
        return self._value

    def setValue(self, value):
        value = max(0, min(self._max, int(value)))
        if value != self._value:
            self._value = value
            self.update()
        self.setToolTip(f"Volume : {self._value} %")

    def setMuted(self, muted):
        if muted != self._muted:
            self._muted = muted
            self.update()

    # --- géométrie ---------------------------------------------------------
    def _ramp(self):
        left, right = 4.0, self.width() - 40.0
        top, bottom = 5.0, self.height() - 5.0
        return left, right, top, bottom

    def _value_at(self, x):
        left, right, _top, _bottom = self._ramp()
        ratio = (x - left) / max(1.0, right - left)
        return int(round(max(0.0, min(1.0, ratio)) * self._max))

    # --- souris -----------------------------------------------------------
    def _apply(self, event):
        value = self._value_at(event.position().x())
        if value != self._value:
            self.setValue(value)
            self.changed.emit(value)
        else:
            self.setToolTip(f"Volume : {value} %")

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self._dragging = True
            self._apply(event)
            event.accept()

    def mouseMoveEvent(self, event):
        if self._dragging:
            self._apply(event)
            event.accept()

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self._dragging = False
            event.accept()

    def wheelEvent(self, event):
        step = 5 if event.angleDelta().y() > 0 else -5
        value = max(0, min(self._max, self._value + step))
        if value != self._value:
            self.setValue(value)
            self.changed.emit(value)
        event.accept()

    # --- dessin -----------------------------------------------------------
    def paintEvent(self, event):
        c = self.colors or {}
        left, right, top, bottom = self._ramp()
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)

        ramp = QPainterPath()
        ramp.moveTo(left, bottom)
        ramp.lineTo(right, bottom)
        ramp.lineTo(right, top)
        ramp.closeSubpath()
        painter.fillPath(ramp, QBrush(QColor(c.get("field", "#0a0a0a"))))

        shown = 0 if self._muted else self._value
        fill_right = left + (right - left) * shown / self._max
        painter.save()
        painter.setClipRect(QRectF(0, 0, max(0.0, fill_right), self.height()))
        if self._muted:
            painter.fillPath(ramp, QBrush(QColor(c.get("dim", "#8d8d94"))))
        else:
            gradient = QLinearGradient(left, 0, right, 0)
            gradient.setColorAt(0.00, QColor("#4fae2c"))     # vert
            gradient.setColorAt(0.45, QColor("#b5cc22"))     # vert-jaune
            gradient.setColorAt(0.70, QColor("#f2b01c"))     # jaune-orange
            gradient.setColorAt(0.80, QColor("#f58a1a"))     # 100 %
            gradient.setColorAt(1.00, QColor("#e5412f"))     # 125 % : rouge
            painter.fillPath(ramp, QBrush(gradient))
        painter.restore()

        x100 = left + (right - left) * 100 / self._max       # repère des 100 %
        painter.setPen(QPen(QColor(c.get("dim", "#8d8d94")), 1))
        painter.drawLine(QPointF(x100, bottom + 2), QPointF(x100, bottom - 4))
        painter.setPen(QPen(QColor(c.get("border", "#262629")), 1))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawPath(ramp)

        painter.setPen(QColor(c.get("dim", "#8d8d94")))
        font = painter.font()
        font.setPixelSize(11)
        painter.setFont(font)
        label = "Muet" if self._muted else f"{self._value}%"
        painter.drawText(QRectF(right + 4, 0, self.width() - right - 6, self.height()),
                         Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter, label)
        painter.end()


# ---------------------------------------------------------------- zone vidéo
class VideoFrame(QWidget):
    """Fenêtre native dans laquelle libVLC dessine la vidéo."""

    clicked = Signal()
    double_clicked = Signal()
    context_requested = Signal(QPoint)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("video")
        self.setAttribute(Qt.WidgetAttribute.WA_NativeWindow, True)
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setMouseTracking(True)
        self.setFocusPolicy(Qt.FocusPolicy.NoFocus)

        # Un simple clic ne doit pas se déclencher avant un éventuel double-clic.
        self._click_timer = QTimer(self)
        self._click_timer.setSingleShot(True)
        self._click_timer.setInterval(220)
        self._click_timer.timeout.connect(self.clicked.emit)

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self._click_timer.start()
        elif event.button() == Qt.MouseButton.RightButton:
            self.context_requested.emit(event.globalPosition().toPoint())
        super().mouseReleaseEvent(event)

    def mouseDoubleClickEvent(self, event):
        self._click_timer.stop()
        self.double_clicked.emit()


# ------------------------------------------------------------------- paroles
class LyricLine(QLabel):
    clicked = Signal(int)

    def __init__(self, index, text, parent=None):
        super().__init__(text, parent)
        self.index = index
        self.setWordWrap(True)
        self.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        self.setCursor(Qt.CursorShape.PointingHandCursor)

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit(self.index)
        super().mouseReleaseEvent(event)


class LyricsView(QScrollArea):
    """Paroles défilantes : la ligne en cours est mise en avant et centrée.

    Un clic sur une ligne (paroles synchronisées) demande de se placer à ce moment.
    """

    seek_requested = Signal(int)     # millisecondes

    def __init__(self, parent=None):
        super().__init__(parent)
        self.colors = {}
        self._lyrics = None
        self._labels = []
        self._current = -2
        self.setWidgetResizable(True)
        self.setFrameShape(QFrame.Shape.NoFrame)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

        self._body = QWidget()
        self._layout = QVBoxLayout(self._body)
        self._layout.setContentsMargins(8, 0, 24, 0)
        self._layout.setSpacing(14)
        self.setWidget(self._body)

        self._anim = QPropertyAnimation(self.verticalScrollBar(), b"value", self)
        self._anim.setDuration(380)
        self._anim.setEasingCurve(QEasingCurve.Type.OutCubic)

    # --- contenu -----------------------------------------------------------
    def _clear(self):
        self._anim.stop()
        while self._layout.count():
            item = self._layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()
        self._labels = []
        self._current = -2

    def set_message(self, text):
        """Affiche un simple message (aucune parole, chargement…)."""
        self._clear()
        self._lyrics = None
        label = QLabel(text)
        label.setWordWrap(True)
        label.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        label.setStyleSheet(f"color: {self.colors.get('dim', '#8d8d94')}; font-size: 16px;")
        self._layout.addStretch(1)
        self._layout.addWidget(label)
        self._layout.addStretch(1)

    def set_lyrics(self, lyrics):
        self._clear()
        self._lyrics = lyrics
        if not lyrics:
            self.set_message("Aucune parole pour ce titre.")
            return
        pad = max(80, self.viewport().height() // 2 - 20)
        self._layout.addSpacing(pad)
        for index, (_ms, text) in enumerate(lyrics.lines):
            label = LyricLine(index, text.strip() or "♪")
            label.clicked.connect(self._on_clicked)
            self._style(label, "plain" if not lyrics.synced else "future")
            self._layout.addWidget(label)
            self._labels.append(label)
        self._layout.addSpacing(pad)
        self.verticalScrollBar().setValue(0)

    def _style(self, label, state):
        c = self.colors
        dim, text = c.get("dim", "#8d8d94"), c.get("text", "#e4e4e7")
        accent = c.get("accent", "#e8851a")
        if state == "current":
            css = f"color: {text}; font-size: 28px; font-weight: 700;"
        elif state == "past":
            css = f"color: {dim}; font-size: 22px; font-weight: 600;"
        elif state == "plain":
            css = f"color: {text}; font-size: 18px; font-weight: 500;"
        else:
            css = f"color: {dim}; font-size: 22px; font-weight: 600;"
        label.setStyleSheet(css + f" selection-background-color: {accent};")

    def restyle(self):
        """À rappeler quand les couleurs du thème changent."""
        if self._lyrics and self._labels:
            current = self._current
            self._current = -2
            self.set_position_index(current)

    def _on_clicked(self, index):
        if self._lyrics and self._lyrics.synced and 0 <= index < len(self._lyrics.lines):
            self.seek_requested.emit(self._lyrics.lines[index][0])

    # --- position ---------------------------------------------------------
    def set_position(self, ms):
        if self._lyrics and self._lyrics.synced:
            self.set_position_index(self._lyrics.index_at(ms))

    def set_position_index(self, index):
        if index == self._current or not self._labels:
            return
        self._current = index
        for i, label in enumerate(self._labels):
            self._style(label, "current" if i == index else ("past" if i < index else "future"))
        if 0 <= index < len(self._labels):
            QTimer.singleShot(0, lambda: self._center_on(index))

    def _center_on(self, index):
        if not (0 <= index < len(self._labels)) or index != self._current:
            return
        label = self._labels[index]
        bar = self.verticalScrollBar()
        target = label.y() + label.height() // 2 - self.viewport().height() // 2
        target = max(bar.minimum(), min(bar.maximum(), target))
        self._anim.stop()
        self._anim.setStartValue(bar.value())
        self._anim.setEndValue(target)
        self._anim.start()


# ------------------------------------------------------------------- pochettes
def make_placeholder(kind, colors, size=QSize(456, 256)):
    """Vignette de remplacement teintée avec la couleur d'accent du thème."""
    pm = QPixmap(size)
    grad = QLinearGradient(0, 0, size.width(), size.height())
    accent = QColor(colors.get("accent", "#e8851a"))
    grad.setColorAt(0.0, QColor(colors.get("accent_dark", "#49301b")))
    grad.setColorAt(1.0, accent.darker(260))
    painter = QPainter(pm)
    painter.fillRect(pm.rect(), QBrush(grad))
    name = {"audio": "music", "stream": "network"}.get(kind, "video")
    glyph = icons.pixmap(name, colors.get("accent", colors["dim"]), 56)
    painter.drawPixmap(
        (size.width() - 56) // 2, (size.height() - 56) // 2, glyph
    )
    painter.end()
    return pm


def draw_cover(painter, pixmap, rect, contain=False):
    """Dessine `pixmap` dans `rect` : rempli et recadré, ou entier (contain)."""
    if pixmap is None or pixmap.isNull():
        return
    mode = (Qt.AspectRatioMode.KeepAspectRatio if contain
            else Qt.AspectRatioMode.KeepAspectRatioByExpanding)
    scaled = pixmap.scaled(rect.size(), mode, Qt.TransformationMode.SmoothTransformation)
    if contain:
        x = rect.left() + (rect.width() - scaled.width()) // 2
        y = rect.top() + (rect.height() - scaled.height()) // 2
        painter.drawPixmap(x, y, scaled)
    else:
        crop = QRect((scaled.width() - rect.width()) // 2,
                     (scaled.height() - rect.height()) // 2, rect.width(), rect.height())
        painter.drawPixmap(rect.topLeft(), scaled, crop)


def make_mosaic(pixmaps, colors, size=QSize(456, 256)):
    """Mosaïque 2×2 des pochettes (ou la première seule s'il y en a moins de 4)."""
    pm = QPixmap(size)
    pm.fill(QColor(colors["panel_hi"]))
    painter = QPainter(pm)
    real = [p for p in pixmaps if p is not None and not p.isNull()]
    if len(real) >= 4:
        w, h = size.width() // 2, size.height() // 2
        for i, pix in enumerate(real[:4]):
            draw_cover(painter, pix, QRect((i % 2) * w, (i // 2) * h, w, h))
    elif real:
        draw_cover(painter, real[0], QRect(0, 0, size.width(), size.height()))
    else:
        glyph = icons.pixmap("playlist", colors["dim"], 56)
        painter.drawPixmap((size.width() - 56) // 2, (size.height() - 56) // 2, glyph)
    painter.end()
    return pm


class ThumbSignals(QObject):
    # chemin du média, chemin de l'image ('' si aucune), infos (titre/artiste/album) ou None
    ready = Signal(str, str, object)


def find_ffmpeg():
    return shutil.which("ffmpeg")


def thumb_stem(src):
    try:
        stamp = os.path.getmtime(src)
    except OSError:
        stamp = 0
    key = hashlib.sha1(f"{src}|{stamp}".encode("utf-8")).hexdigest()[:20]
    return str(CACHE_DIR / key)


def find_cached_thumb(src):
    stem = thumb_stem(src)
    for ext in ("jpg", "png", "webp", "gif", "bmp"):
        if os.path.exists(f"{stem}.{ext}"):
            return f"{stem}.{ext}"
    return None


class ThumbWorker(QRunnable):
    """Trouve une image pour un média, sans bloquer l'interface.

    Musique : pochette intégrée aux tags → image du dossier (cover.jpg…) → FFmpeg.
    Vidéo   : affiche du dossier (<nom>.jpg, poster.jpg…) → image extraite par FFmpeg.
    Flux    : image distante fournie par le catalogue.
    """

    def __init__(self, src, kind, ffmpeg, cover_url, signals):
        super().__init__()
        self.src, self.kind, self.ffmpeg = src, kind, ffmpeg
        self.cover_url, self.signals = cover_url, signals

    # --- sources ------------------------------------------------------------
    def _save(self, data):
        ext = tags.sniff_image(data)
        if not ext:
            return ""
        dst = f"{thumb_stem(self.src)}.{ext}"
        with open(dst, "wb") as f:
            f.write(data)
        return dst

    def _from_file(self, path):
        with open(path, "rb") as f:
            return self._save(f.read(20 * 1024 * 1024))

    def _download(self, url):
        request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
        with urllib.request.urlopen(request, timeout=10) as response:
            return self._save(response.read(8 * 1024 * 1024))

    def _ffmpeg(self, seek_first):
        if not self.ffmpeg:
            return ""
        dst = f"{thumb_stem(self.src)}.jpg"
        extra = {"creationflags": 0x08000000} if sys.platform.startswith("win") else {}
        for seek in (["-ss", "5"], ["-ss", "0"]) if seek_first else ([],):
            cmd = [self.ffmpeg, "-y", "-loglevel", "error", *seek, "-i", self.src,
                   "-an", "-frames:v", "1", "-vf", "scale=480:-2", dst]
            subprocess.run(cmd, capture_output=True, timeout=25, check=False,
                           stdin=subprocess.DEVNULL, **extra)
            if os.path.exists(dst) and os.path.getsize(dst) > 0:
                return dst
        return ""

    # --- exécution ------------------------------------------------------------
    def run(self):
        found, info = "", None
        try:
            CACHE_DIR.mkdir(parents=True, exist_ok=True)
            if self.kind == "audio":
                meta = tags.read_info(self.src)
                info = {k: meta[k] for k in ("title", "artist", "album") if meta.get(k)}
                if meta.get("cover"):
                    found = self._save(meta["cover"])
                if not found:
                    folder = tags.find_folder_cover(self.src)
                    found = self._from_file(folder) if folder else ""
                if not found:
                    found = self._ffmpeg(False)
            elif self.kind == "video":
                folder = tags.find_folder_cover(self.src)
                found = self._from_file(folder) if folder else ""
                if not found:
                    found = self._ffmpeg(True)
            elif self.kind == "stream" and self.cover_url:
                found = self._download(self.cover_url)
        except Exception:
            pass
        try:
            self.signals.ready.emit(self.src, found, info)
        except RuntimeError:  # fenêtre déjà fermée
            pass


# ------------------------------------------------------------ carte de la grille
class MediaDelegate(QStyledItemDelegate):
    """Dessine une carte : vignette arrondie, titre, et une 2e ligne (artiste…)."""

    CELL_W, CELL_H = 240, 196

    def __init__(self, parent=None):
        super().__init__(parent)
        self.colors = {}

    def sizeHint(self, option, index):
        return QSize(self.CELL_W, self.CELL_H)

    def paint(self, painter, option, index):
        c = self.colors
        painter.save()
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)

        card = option.rect.adjusted(6, 6, -6, -6)
        hovered = bool(option.state & QStyle.StateFlag.State_MouseOver)
        selected = bool(option.state & QStyle.StateFlag.State_Selected)

        if hovered or selected:
            bg = QPainterPath()
            bg.addRoundedRect(QRectF(card), 12, 12)
            painter.fillPath(bg, QBrush(QColor(c.get("hover", "#232326"))))

        width = card.width() - 12
        thumb = QRect(card.left() + 6, card.top() + 6, width, round(width * 9 / 16))
        clip = QPainterPath()
        clip.addRoundedRect(QRectF(thumb), 8, 8)

        painter.save()
        painter.setClipPath(clip)
        painter.fillRect(thumb, QBrush(QColor("#000000")))
        pix = index.data(ROLE_THUMB)
        if isinstance(pix, QPixmap) and not pix.isNull():
            kind = index.data(ROLE_KIND)
            real = bool(index.data(ROLE_REAL))
            if real and kind in ("audio", "stream"):
                # pochette d'album carrée : entière, centrée, sur fond sombre
                painter.fillRect(thumb, QBrush(QColor(c.get("panel_hi", "#202022"))))
                draw_cover(painter, pix, thumb, contain=True)
            else:
                draw_cover(painter, pix, thumb)
        painter.restore()

        if selected:
            painter.setPen(QPen(QColor(c.get("accent", "#e8851a")), 2))
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawPath(clip)

        text_w = thumb.width()
        title_rect = QRect(thumb.left(), thumb.bottom() + 8, text_w, 20)
        painter.setPen(QColor(c.get("text", "#e4e4e7")))
        metrics = painter.fontMetrics()
        name = index.data(Qt.ItemDataRole.DisplayRole) or ""
        painter.drawText(
            title_rect, Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
            metrics.elidedText(name, Qt.TextElideMode.ElideRight, text_w))

        subtitle = index.data(ROLE_SUBTITLE)
        if subtitle:
            font = painter.font()
            font.setPixelSize(12)
            painter.setFont(font)
            painter.setPen(QColor(c.get("dim", "#8d8d94")))
            sub_rect = QRect(thumb.left(), title_rect.bottom() + 1, text_w, 18)
            painter.drawText(
                sub_rect, Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
                painter.fontMetrics().elidedText(subtitle, Qt.TextElideMode.ElideRight, text_w))
        painter.restore()
