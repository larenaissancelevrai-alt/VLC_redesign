"""VLC Redesign : lecteur multimédia PySide6 + libVLC, d'après la maquette Figma."""

import os
import random
import shutil
import sys
import time
import traceback
import asyncio
import uuid
import math
from pathlib import Path

APP_NAME = "VLC Redesign"
DATA_DIR = Path.home() / ".vlc_redesign"
LOG_PATH = DATA_DIR / "erreur.log"


# ------------------------------------------------------------ erreurs de démarrage
def log_error(text):
    """Ajoute une erreur au journal ~/.vlc_redesign/erreur.log (ne plante jamais)."""
    try:
        DATA_DIR.mkdir(parents=True, exist_ok=True)
        with open(LOG_PATH, "a", encoding="utf-8") as f:
            f.write(f"--- {time.strftime('%Y-%m-%d %H:%M:%S')} ---\n{text}\n")
    except OSError:
        pass


def fatal(message):
    """Affiche une erreur lisible puis quitte, même si la fenêtre a été lancée par double-clic."""
    log_error(message)
    print("\n" + message + f"\n\n(Journal : {LOG_PATH})")
    if sys.platform.startswith("win"):
        try:
            import ctypes
            ctypes.windll.user32.MessageBoxW(0, message, APP_NAME, 0x10)
        except Exception:
            pass
    try:
        if sys.stdin and sys.stdin.isatty():
            input("\nAppuyez sur Entrée pour fermer…")
    except (EOFError, OSError):
        pass
    sys.exit(1)


try:
    from PySide6.QtCore import (
        QEasingCurve, QParallelAnimationGroup, QPoint, QPropertyAnimation, Property, QRect,
        QSize, Qt, QThreadPool, QTimer, QSignalBlocker,
    )
    from PySide6.QtGui import QActionGroup, QColor, QIcon, QPainter, QPainterPath, QPixmap, QPalette
    from PySide6.QtWidgets import (
        QApplication, QAbstractItemView, QButtonGroup, QFileDialog, QFrame, QHBoxLayout, QInputDialog, QLabel,
        QLineEdit, QListView, QListWidget, QListWidgetItem, QMainWindow, QMenu, QMessageBox,
        QProgressBar, QPushButton, QStackedLayout, QStackedWidget, QToolButton, QToolTip, QVBoxLayout, QWidget
    )
    from PySide6.QtCore import Signal
except ImportError as exc:      # PySide6 absent ou cassé
    fatal("PySide6 n'est pas installé (ou ne se charge pas).\n\n"
          "Ouvrez une invite de commandes dans le dossier de l'application et tapez :\n"
          "    python -m pip install -r requirements.txt\n\n"
          f"Détail : {exc}")

import icons
import i18n
import lyrics
import shortcuts
import tags
import theme
import widgets
from asyncwork import AsyncRunner
from backend import (
    AUDIO_TRACK_EXT, MEDIA_EXT, SUBTITLE_EXT, Backend, is_stream, kind_of
)
from config import MAX_VOLUME, Config
from miniplayer import MiniPlayer, OverlayHost
from panels import PlaylistsPanel, QueuePanel, SettingsPanel, UserPanel, SPEEDS
from youtube_panel import YouTubePanel
from downloader_panel import DownloaderPanel
from widgets import (
    ROLE_KIND, ROLE_PATH, ROLE_REAL, ROLE_SUBTITLE, ROLE_THUMB, ClickSlider, LyricsView,
    MediaDelegate, ThumbSignals, ThumbWorker, VideoFrame, VolumeBar
)
from animated_controls import AnimatedPushButton as QPushButton, AnimatedToolButton as QToolButton
from wizard import HelpDialog, WizardDialog

# (clé, libellé, icône) : dans l'ordre de la maquette
NAVIGATION = [
    ("home", "Accueil", "home"),
    ("video", "Vidéos", "video"),
    ("music", "Musique", "music"),
    ("network", "Réseau", "network"),
    ("discover", "YouTube", "globe"),
    ("downloads", "Télécharger", "download"),
    ("playlist", "Playlists", "playlist"),
    ("queue", "File d’attente", "queue"),
    ("recent", "Récents", "recent"),
    ("favorites", "Favoris", "favorite"),
]
SETTINGS_KEY = "settings"
USER_KEY = "user"
PAGE_TITLES = dict((k, name) for k, name, _icon in NAVIGATION)
PAGE_TITLES[SETTINGS_KEY] = "Paramètres"
PAGE_TITLES[USER_KEY] = "Utilisateur"
GRID_PAGES = {"home", "video", "music", "network", "recent", "favorites"}

EMPTY_MESSAGES = {
    "home": "Votre bibliothèque est vide.\nUtilisez « Ajouter » ou glissez des fichiers ici.",
    "video": "Aucune vidéo pour le moment.",
    "music": "Aucune musique pour le moment.",
    "network": "Aucun flux réseau.\nUn flux est un son ou une vidéo diffusé par une adresse (URL), "
               "sans téléchargement. Ajoutez-en via « Ajouter » › « Flux réseau… » (Ctrl+U), "
               "ou écoutez de la musique libre dans « Découvrir ».",
    "recent": "Rien n'a encore été lu.",
}

SORTS = [
    ("Nom (A → Z)", "name", False),
    ("Nom (Z → A)", "name", True),
    ("Ajout le plus récent", "added", True),
    ("Ajout le plus ancien", "added", False),
]

FILE_FILTER = (
    "Fichiers multimédias (" + " ".join(f"*{e}" for e in sorted(MEDIA_EXT))
    + ");;Tous les fichiers (*)"
)
REPEAT_NEXT = {"off": "one", "one": "all", "all": "off"}
REPEAT_TEXT = {"off": "Répétition désactivée", "one": "Répéter ce titre", "all": "Répéter la liste"}


def format_time(ms):
    seconds = max(0, int(ms) // 1000)
    return f"{seconds // 3600:02}:{seconds % 3600 // 60:02}:{seconds % 60:02}"


def scan_folder(folder):
    """Tous les médias d'un dossier (récursif), triés ; les dossiers illisibles sont ignorés."""
    found = []
    for root, _dirs, files in os.walk(folder, onerror=lambda _e: None):
        for name in files:
            if os.path.splitext(name)[1].lower() in MEDIA_EXT:
                found.append(os.path.join(root, name))
    return sorted(found, key=str.lower)


def rounded_pixmap(pixmap, size, radius):
    """Image carrée recadrée aux coins arrondis."""
    out = QPixmap(size, size)
    out.fill(Qt.GlobalColor.transparent)
    painter = QPainter(out)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
    clip = QPainterPath()
    clip.addRoundedRect(0, 0, size, size, radius, radius)
    painter.setClipPath(clip)
    scaled = pixmap.scaled(size, size, Qt.AspectRatioMode.KeepAspectRatioByExpanding,
                           Qt.TransformationMode.SmoothTransformation)
    painter.drawPixmap(-(scaled.width() - size) // 2, -(scaled.height() - size) // 2, scaled)
    painter.end()
    return out


class MediaGrid(QListWidget):
    """Grille qui accepte le dépôt de fichiers depuis l'explorateur."""

    files_dropped = Signal(list)
    delete_requested = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAcceptDrops(True)
        self.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)

    def keyPressEvent(self, event):
        if event.key() == Qt.Key.Key_Delete and self.selectedItems():
            self.delete_requested.emit()
            event.accept()
            return
        super().keyPressEvent(event)

    def dragEnterEvent(self, event):
        if event.mimeData().hasUrls():
            event.acceptProposedAction()
        else:
            super().dragEnterEvent(event)

    def dragMoveEvent(self, event):
        if event.mimeData().hasUrls():
            event.acceptProposedAction()
        else:
            super().dragMoveEvent(event)

    def dropEvent(self, event):
        items = [u.toLocalFile() if u.isLocalFile() else u.toString() for u in event.mimeData().urls()]
        if items:
            self.files_dropped.emit(items)
            event.acceptProposedAction()
        else:
            super().dropEvent(event)


class BackgroundLayer(QWidget):
    """Paint the selected background behind every application surface."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._pixmap = QPixmap()
        self._color = QColor("#0e0e0f")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)

    def set_background(self, pixmap, color):
        self._pixmap = pixmap if pixmap is not None else QPixmap()
        self._color = QColor(color)
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.fillRect(self.rect(), self._color)
        if not self._pixmap.isNull():
            scaled = self._pixmap.scaled(
                self.size(), Qt.AspectRatioMode.KeepAspectRatioByExpanding,
                Qt.TransformationMode.SmoothTransformation,
            )
            x = (scaled.width() - self.width()) // 2
            y = (scaled.height() - self.height()) // 2
            painter.drawPixmap(self.rect(), scaled, QRect(x, y, self.width(), self.height()))
        painter.end()


class DiagonalWaveOverlay(QWidget):
    """Translucent wipe whose rippled edge travels diagonally across the window."""

    waveProgress = Property(float, lambda self: self._wave_progress,
                            lambda self, value: self._set_wave_progress(value))

    def __init__(self, parent=None):
        super().__init__(parent)
        self._wave_progress = 0.0
        self._covering = True
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)

    def _set_wave_progress(self, value):
        self._wave_progress = max(0.0, min(1.0, float(value)))
        self.update()

    def setWaveProgress(self, value):
        """Public setter used by the transition controller."""
        self._set_wave_progress(value)

    def set_covering(self, covering):
        self._covering = bool(covering)
        self.update()

    def paintEvent(self, _event):
        width = self.width()
        height = self.height()
        if width <= 0 or height <= 0:
            return
        threshold = self._wave_progress * (width + height)
        amplitude = 22.0 * math.sin(math.pi * self._wave_progress)
        path = QPainterPath()
        step = max(5, height // 110)
        boundary = lambda y: max(0.0, min(float(width), threshold - y + amplitude * math.sin(y / max(1, height) * math.tau * 1.25)))
        if self._covering:
            path.moveTo(0, 0)
            for y in range(0, height + step, step):
                y = min(y, height)
                path.lineTo(boundary(y), y)
            path.lineTo(0, height)
        else:
            path.moveTo(width, 0)
            for y in range(0, height + step, step):
                y = min(y, height)
                path.lineTo(boundary(y), y)
            path.lineTo(width, height)
        path.closeSubpath()
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        painter.fillPath(path, QColor(5, 7, 10, 205))
        painter.end()


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle(APP_NAME)
        self.resize(1250, 780)
        self.setMinimumSize(960, 600)
        self.setAcceptDrops(True)

        self.cfg = Config()
        self.tagcache = tags.MetaCache(str(self.cfg.profile_root / self.cfg.active_profile / "tags.json"))
        self.backend = Backend()
        self.runner = AsyncRunner(self)
        self.queue = list(self.cfg.get("queue", []))
        self.active_playlist = None
        self.current = None
        self.page = "home"
        self.lyrics = None
        self._visible = []
        self._ended_handled = False
        self._last_active = None
        self._docked = "player"
        self._icon_registry = {}
        self._tip_errors = 0
        self._profile_switch_pending = False
        self._crossfade_target = None
        self._crossfade_started_at = None
        self._crossfade_fade_duration = 0
        self._resume_pending = None
        self._resume_last_saved_at = 0.0
        self._resume_last_saved_position = None
        self._sleep_deadline = None
        self._sleep_end_track = None
        self._sleep_timer_last_label = None

        self.ffmpeg = widgets.find_ffmpeg()
        self.thumbs = {}             # média → QPixmap lu depuis un fichier image
        self._placeholders = {}
        self._thumb_pending = set()
        self._thumb_done = set()
        self.pool = QThreadPool(self)
        self.pool.setMaxThreadCount(2)
        self.thumb_signals = ThumbSignals(self)
        self.thumb_signals.ready.connect(self._on_thumb_ready)

        self._save_timer = QTimer(self)
        self._save_timer.setSingleShot(True)
        self._save_timer.setInterval(500)
        self._save_timer.timeout.connect(self.save_now)

        self._bind_shortcuts()
        self._build_ui()
        if self.cfg.get("sidebar_collapsed", False):
            self.toggle_sidebar()
        self.apply_theme()
        self._set_page("home")
        self.show_library()

        self.backend.set_volume(self.cfg.get("volume"))
        self.backend.set_muted(self.cfg.get("muted"))
        self.backend.set_rate(self.cfg.get("playback_rate"))
        self.backend.set_normalize_audio(self.cfg.get("normalize_audio", False))
        self.apply_equalizer()
        self._sync_volume_ui()
        self._sync_repeat_ui()
        self.set_lyrics_visible(self.cfg.get("show_lyrics"), save=False)

        # Apply the selected language on startup and to labels rebuilt dynamically
        # by page refreshes, playlists, and the player.
        i18n.translate_tree(self, self.cfg.get("language", "fr"))
        self._language_timer = QTimer(self)
        self._language_timer.setInterval(500)
        self._language_timer.timeout.connect(
            lambda: i18n.translate_tree(self, self.cfg.get("language", "fr"))
        )
        self._language_timer.start()

        self.timer = QTimer(self)
        # A finer cadence keeps the crossfade audibly smooth; the previous
        # 250 ms cadence produced coarse, noticeable volume steps.
        self.timer.setInterval(50)
        self.timer.timeout.connect(self._tick)
        self.timer.start()
        self._sleep_timer = QTimer(self)
        self._sleep_timer.setInterval(1000)
        self._sleep_timer.timeout.connect(self._check_sleep_timer)

    # ------------------------------------------------------------------ accès rapides
    @property
    def library(self):
        return self.cfg.data["library"]

    @property
    def recents(self):
        return self.cfg.data["recents"]

    @property
    def playlists(self):
        return self.cfg.data["playlists"]

    @property
    def smart_playlists(self):
        return self.cfg.get("smart_playlists", {})

    def smart_playlist_tracks(self, name):
        criteria = self.smart_playlists.get(name, {})
        if not isinstance(criteria, dict):
            return []
        wanted_artist = str(criteria.get("artist", "")).strip().casefold()
        wanted_genre = str(criteria.get("genre", "")).strip().casefold()
        favorites_only = bool(criteria.get("favorites", False))
        favorites = set(self.cfg.get("favorites", []))
        matches = []
        for path in self.library:
            if favorites_only and path not in favorites:
                continue
            meta = self.meta_of(path)
            artist = str(meta.get("artist", "")).casefold()
            genre = str(meta.get("genre", "")).casefold()
            if wanted_artist and wanted_artist not in artist:
                continue
            if wanted_genre and wanted_genre not in genre:
                continue
            matches.append(path)
        return matches

    def colors(self):
        return theme.colors(self.cfg.get("accent"), self.cfg.get("background"),
                            self.cfg.get("element_color", theme.PALETTE["panel"]))

    def save_soon(self):
        self._save_timer.start()

    def save_now(self):
        self._save_timer.stop()
        if not self.cfg.save():
            self.osd("Impossible d'enregistrer les réglages (dossier protégé ?).")
        self.tagcache.save()

    # ================================================================== interface
    def _build_ui(self):
        # On conserve la barre de titre native de Windows, comme demandé.
        self.stack = QStackedWidget()
        self.stack.setObjectName("appStack")
        self.stack.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        # The background is a dedicated bottom layer. Painting it in the main
        # window let transparent pages reveal it over other child surfaces.
        self.background_layer = BackgroundLayer()
        self.background_host = QWidget()
        layers = QStackedLayout(self.background_host)
        layers.setContentsMargins(0, 0, 0, 0)
        layers.setStackingMode(QStackedLayout.StackingMode.StackAll)
        layers.addWidget(self.background_layer)
        layers.addWidget(self.stack)
        layers.setCurrentWidget(self.stack)

        self.profile_loading_overlay = DiagonalWaveOverlay(self.background_host)
        self.profile_loading_overlay.setObjectName("profileLoadingOverlay")
        overlay_layout = QVBoxLayout(self.profile_loading_overlay)
        overlay_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        loading_card = QFrame()
        loading_card.setObjectName("profileLoadingCard")
        colors = self.colors()
        loading_card.setStyleSheet(
            f"QFrame#profileLoadingCard {{ background: {colors['panel']}; color: {colors['text']}; "
            f"border: 1px solid {colors['border']}; border-radius: 16px; }}"
        )
        card_layout = QVBoxLayout(loading_card)
        card_layout.setContentsMargins(32, 26, 32, 26)
        card_layout.setSpacing(16)
        self.profile_loading_label = QLabel("Chargement du profil…")
        self.profile_loading_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.profile_loading_label.setStyleSheet(
            f"color: {colors['text']}; font-size: 17px; font-weight: 600; border: none;"
        )
        card_layout.addWidget(self.profile_loading_label)
        self.profile_loading_bar = QProgressBar()
        self.profile_loading_bar.setRange(0, 0)
        self.profile_loading_bar.setTextVisible(False)
        self.profile_loading_bar.setFixedWidth(250)
        self.profile_loading_bar.setStyleSheet(
            f"QProgressBar {{ background: {colors['field']}; border: none; border-radius: 3px; height: 6px; }}"
            f"QProgressBar::chunk {{ background: {colors['accent']}; border-radius: 3px; }}"
        )
        card_layout.addWidget(self.profile_loading_bar)
        overlay_layout.addWidget(loading_card)
        layers.addWidget(self.profile_loading_overlay)
        layers.setCurrentWidget(self.stack)
        self.profile_loading_overlay.hide()
        self.profile_loading_animation = QPropertyAnimation(
            self.profile_loading_overlay, b"waveProgress", self
        )
        self.profile_loading_animation.setDuration(260)
        self.profile_loading_animation.setEasingCurve(QEasingCurve.Type.InOutCubic)
        self.profile_loading_animation.finished.connect(self._finish_profile_loading_wave)
        self.setCentralWidget(self.background_host)
        self.stack.addWidget(self._build_library_page())
        self.player_page = self._build_player_page()
        self.stack.addWidget(self.player_page)
        self.mini = MiniPlayer(self.library_page)
        self.mini.set_anchor(self.nowplaying)
        self.mini.play_button.clicked.connect(self.toggle_play)
        self.mini.expand_button.clicked.connect(self.show_player)
        self.mini.close_button.clicked.connect(self._close_mini)
        self._set_icon(self.mini.play_button, "play", "tool")
        self._set_icon(self.mini.expand_button, "fullscreen", "tool")
        self._set_icon(self.mini.close_button, "close", "tool")
        self.library_page.resized.connect(self.mini.place)

    def _set_icon(self, widget, name, mode="tool"):
        """Associe une icône à un widget ; elle est recolorée au changement de thème."""
        self._icon_registry[widget] = (name, mode)
        widget.setIcon(self._make_icon(name, mode))

    def _make_icon(self, name, mode):
        c = self.colors()
        if mode == "nav":
            return icons.icon(name, c["dim"], active=c["accent"], size=20)
        if mode == "accent":
            return icons.icon(name, c["accent"])
        if mode == "onaccent":
            return icons.icon(name, c["on_accent"])
        return icons.icon(name, c["text"])

    def _refresh_icons(self):
        for widget, (name, mode) in self._icon_registry.items():
            widget.setIcon(self._make_icon(name, mode))

    def _tool_button(self, icon_name, tooltip, callback=None, mode="tool", size=22, checkable=False):
        button = QToolButton()
        button.setToolTip(tooltip)
        button.setIconSize(QSize(size, size))
        button.setCursor(Qt.CursorShape.PointingHandCursor)
        button.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        button.setCheckable(checkable)
        self._set_icon(button, icon_name, mode)
        if callback is not None:
            button.clicked.connect(lambda checked=False: callback())
        return button

    def _nav_button(self, label, icon_name, checkable=True):
        button = QPushButton(f"  {label}")
        button.setObjectName("nav")
        button.setCheckable(checkable)
        button.setIconSize(QSize(20, 20))
        button.setCursor(Qt.CursorShape.PointingHandCursor)
        button.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self._set_icon(button, icon_name, "nav")
        return button

    def toggle_sidebar(self):
        self.sidebar_collapsed = not self.sidebar_collapsed
        collapsed = self.sidebar_collapsed
        target_width = 64 if collapsed else 220
        start_width = self.sidebar.width()
        if hasattr(self, "_sidebar_width_animation"):
            self._sidebar_width_animation.stop()
        self.sidebar.setMinimumWidth(start_width)
        self.sidebar.setMaximumWidth(start_width)
        animation = QParallelAnimationGroup(self)
        for property_name in (b"minimumWidth", b"maximumWidth"):
            width_animation = QPropertyAnimation(self.sidebar, property_name, animation)
            width_animation.setDuration(230)
            width_animation.setStartValue(start_width)
            width_animation.setEndValue(target_width)
            width_animation.setEasingCurve(QEasingCurve.Type.InOutCubic)
            animation.addAnimation(width_animation)
        self._sidebar_width_animation = animation
        animation.start()
        self.sidebar_logo.setVisible(not collapsed)
        self.sidebar_toggle.setToolTip(
            "Déplier la barre latérale" if collapsed else "Réduire la barre latérale"
        )
        for key, button in self.nav_buttons.items():
            button.setText("" if collapsed else self.sidebar_labels[key])
            button.setProperty("compact", collapsed)
            button.style().unpolish(button)
            button.style().polish(button)
        self.more_button.setText("" if collapsed else "  Paramètres…")
        self.more_button.setProperty("compact", collapsed)
        self.more_button.style().unpolish(self.more_button)
        self.more_button.style().polish(self.more_button)
        self.cfg.set("sidebar_collapsed", collapsed)
        self.save_soon()

    # --- page bibliothèque ---------------------------------------------------------
    def _build_library_page(self):
        page = OverlayHost()
        self.library_page = page
        root = QHBoxLayout(page)
        root.setContentsMargins(10, 10, 10, 10)
        root.setSpacing(14)

        sidebar = QFrame()
        sidebar.setObjectName("sidebar")
        sidebar.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        sidebar.setFixedWidth(220)
        self.sidebar = sidebar
        self.sidebar_collapsed = False

        side = QVBoxLayout(sidebar)
        side.setContentsMargins(10, 14, 10, 14)
        side.setSpacing(4)
        logo = QLabel(APP_NAME)
        logo.setObjectName("logo")
        self.sidebar_logo = logo
        brand_row = QHBoxLayout()
        brand_row.addWidget(logo, 1)
        self.sidebar_toggle = self._tool_button(
            "menu", "Réduire la barre latérale", self.toggle_sidebar, size=18
        )
        brand_row.addWidget(self.sidebar_toggle)
        side.addLayout(brand_row)
        side.addSpacing(12)

        self.nav_group = QButtonGroup(self)
        self.nav_group.setExclusive(True)
        self.nav_buttons = {}
        self.sidebar_labels = {}
        for key, label, icon_name in NAVIGATION:
            button = self._nav_button(label, icon_name)
            button.setToolTip(label)
            if key == "network":
                button.setToolTip("Lire un flux audio/vidéo à partir d'une adresse réseau (URL)")
            if key == "discover":
                button.setToolTip("Rechercher et écouter des vidéos sur YouTube")
            button.clicked.connect(lambda checked=False, k=key: self._set_page(k))
            self.nav_group.addButton(button)
            self.nav_buttons[key] = button
            self.sidebar_labels[key] = button.text()
            side.addWidget(button)

        self.more_button = self._nav_button("Paramètres…", "more", checkable=False)
        self.more_button.setToolTip("Paramètres")
        self.more_menu = QMenu(self)
        self.more_menu.addAction("Ajouter des fichiers…", self.add_files_dialog)
        self.more_menu.addAction("Ajouter un dossier…", self.add_folder_dialog)
        self.more_menu.addAction("Flux réseau…", self.add_stream_dialog)
        self.more_menu.addSeparator()
        self.more_menu.addAction("Paramètres", lambda: self.go_page(SETTINGS_KEY))
        self.more_button.clicked.connect(
            lambda: self.more_menu.exec(self.more_button.mapToGlobal(QPoint(0, self.more_button.height())))
        )
        side.addWidget(self.more_button)

        side.addStretch()
        user_button = self._nav_button("Utilisateur", "user")
        user_button.setToolTip("Espaces utilisateurs")
        user_button.clicked.connect(lambda: self.go_page(USER_KEY))
        self.nav_group.addButton(user_button)
        self.nav_buttons[USER_KEY] = user_button
        self.sidebar_labels[USER_KEY] = user_button.text()
        side.addWidget(user_button)
        root.addWidget(sidebar)

        content = QVBoxLayout()
        content.setContentsMargins(0, 4, 0, 0)
        content.setSpacing(12)

        header = QHBoxLayout()
        header.setSpacing(10)
        self.page_title = QLabel("Accueil")
        self.page_title.setObjectName("title")
        header.addWidget(self.page_title)
        self.count_label = QLabel("")
        self.count_label.setObjectName("dim")
        header.addWidget(self.count_label)
        header.addStretch()
        self.search = QLineEdit()
        self.search.setObjectName("search")
        self.search.setPlaceholderText("Rechercher")
        self.search.setClearButtonEnabled(True)
        self.search.textChanged.connect(lambda _t: self.refresh_grid())
        header.addWidget(self.search)
        self.sort_button = self._tool_button("sort", "Trier")
        self.sort_button.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
        self.sort_button.setMenu(self._sort_menu())
        header.addWidget(self.sort_button)
        content.addLayout(header)

        self.content_stack = QStackedWidget()
        self.delegate = MediaDelegate(self)
        self.grid = MediaGrid()
        self.grid.files_dropped.connect(self._handle_dropped_items)
        self.grid.delete_requested.connect(self.remove_selected_from_library)
        self.grid.setViewMode(QListView.ViewMode.IconMode)
        self.grid.setResizeMode(QListView.ResizeMode.Adjust)
        self.grid.setMovement(QListView.Movement.Static)
        self.grid.setUniformItemSizes(True)
        self.grid.setSpacing(2)
        self.grid.setGridSize(QSize(MediaDelegate.CELL_W, MediaDelegate.CELL_H))
        self.grid.setItemDelegate(self.delegate)
        self.grid.setMouseTracking(True)
        self.grid.setFrameShape(QFrame.Shape.NoFrame)
        self.grid.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.grid.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.grid.customContextMenuRequested.connect(self._grid_menu)
        self.grid.itemActivated.connect(self._on_item_activated)
        self.content_stack.addWidget(self.grid)

        self.empty_label = QLabel("")
        self.empty_label.setObjectName("empty")
        self.empty_label.setWordWrap(True)
        self.empty_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.content_stack.addWidget(self.empty_label)

        self.playlists_panel = PlaylistsPanel(self)
        self.settings_panel = SettingsPanel(self)
        self.user_panel = UserPanel(self)
        self.discover = YouTubePanel(self)
        self.downloads = DownloaderPanel(self)
        self.queue_panel = QueuePanel(self)
        for panel in (self.playlists_panel, self.settings_panel, self.user_panel,
                      self.discover, self.downloads, self.queue_panel):
            self.content_stack.addWidget(panel)
        content.addWidget(self.content_stack, 1)

        # barre « en cours de lecture »
        self.nowplaying = QFrame()
        self.nowplaying.setObjectName("nowplaying")
        np_layout = QHBoxLayout(self.nowplaying)
        np_layout.setContentsMargins(14, 8, 10, 8)
        np_layout.setSpacing(10)
        self.np_name = QLabel("Aucun média en cours")
        self.np_name.setMinimumWidth(130)
        np_layout.addWidget(self.np_name, 1)
        np_layout.addWidget(self._tool_button("prev", "Précédent", lambda: self.next_media(-1)))
        self.np_play = self._tool_button("play", "Lecture / Pause", self.toggle_play)
        np_layout.addWidget(self.np_play)
        np_layout.addWidget(self._tool_button("next", "Suivant", lambda: self.next_media(1)))
        self.np_time = QLabel("00:00 / 00:00")
        self.np_time.setObjectName("time")
        np_layout.addWidget(self.np_time)
        self.np_seek = ClickSlider()
        self.np_seek.setRange(0, 1000)
        self.np_seek.setMinimumWidth(100)
        self.np_seek.seeked.connect(lambda value: self.backend.seek_fraction(value / 1000))
        np_layout.addWidget(self.np_seek, 3)
        self.np_volume = VolumeBar(MAX_VOLUME)
        self.np_volume.changed.connect(self.set_volume)
        np_layout.addWidget(self.np_volume)
        np_layout.addWidget(self._tool_button("fullscreen", "Ouvrir le lecteur", self.show_player))
        self.nowplaying.hide()
        content.addWidget(self.nowplaying)

        root.addLayout(content, 1)
        return page

    def _sort_menu(self):
        menu = QMenu(self)
        group = QActionGroup(menu)
        group.setExclusive(True)
        for label, key, reverse in SORTS:
            action = menu.addAction(label)
            action.setCheckable(True)
            action.setChecked((key, reverse) == (self.cfg.get("sort_key"), self.cfg.get("sort_reverse")))
            group.addAction(action)
            action.triggered.connect(lambda checked=False, k=key, r=reverse: self._set_sort(k, r))
        return menu

    # --- page lecteur --------------------------------------------------------------
    def _build_player_page(self):
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self.media_stack = QStackedWidget()
        # page vidéo : un conteneur, pour pouvoir déplacer la vidéo vers le mini-lecteur
        self.video_page = QWidget()
        self.video_layout = QVBoxLayout(self.video_page)
        self.video_layout.setContentsMargins(0, 0, 0, 0)
        self.video = VideoFrame()
        self.video.clicked.connect(self.toggle_play)
        self.video.double_clicked.connect(self._video_double_click)
        self.video.context_requested.connect(self._video_menu)
        self.video_layout.addWidget(self.video)
        self.media_stack.addWidget(self.video_page)
        self.media_stack.addWidget(self._build_audio_page())
        layout.addWidget(self.media_stack, 1)

        self.controls = QFrame()
        self.controls.setObjectName("controls")
        bar = QHBoxLayout(self.controls)
        bar.setContentsMargins(16, 10, 16, 10)
        bar.setSpacing(6)
        bar.addWidget(self._tool_button("prev", "Précédent (P)", lambda: self.next_media(-1)))
        self.play_button = self._tool_button("play", "Lecture / Pause (Espace)", self.toggle_play, mode="onaccent")
        self.play_button.setObjectName("play")
        bar.addWidget(self.play_button)
        bar.addWidget(self._tool_button("next", "Suivant (N)", lambda: self.next_media(1)))
        bar.addSpacing(8)
        self.time_label = QLabel("00:00:00")
        self.time_label.setObjectName("time")
        bar.addWidget(self.time_label)
        self.seek = ClickSlider()
        self.seek.setRange(0, 1000)
        self.seek.seeked.connect(lambda value: self.backend.seek_fraction(value / 1000))
        bar.addWidget(self.seek, 1)
        self.total_label = QLabel("00:00:00")
        self.total_label.setObjectName("time")
        bar.addWidget(self.total_label)
        bar.addSpacing(8)

        self.mute_button = self._tool_button("volume", "Muet (M)", self.toggle_mute)
        bar.addWidget(self.mute_button)
        self.volume = VolumeBar(MAX_VOLUME)
        self.volume.changed.connect(self.set_volume)
        bar.addWidget(self.volume)
        bar.addSpacing(8)

        self.repeat_button = self._tool_button("repeat", "Répétition", self.cycle_repeat, checkable=True)
        bar.addWidget(self.repeat_button)
        self.lyrics_button = self._tool_button("lyrics", "Paroles (L)", self.toggle_lyrics, checkable=True)
        bar.addWidget(self.lyrics_button)
        self.playlist_toggle_button = self._tool_button(
            "playlist", "Afficher / masquer la playlist", self.toggle_playlist_sidebar, checkable=True
        )
        self.playlist_toggle_button.setVisible(False)
        bar.addWidget(self.playlist_toggle_button)

        self.audio_menu = QMenu(self)
        self.audio_menu.aboutToShow.connect(lambda: self._fill_track_menu(self.audio_menu, "audio"))
        self.audio_button = self._tool_button("audio", "Piste audio (B)")
        self.audio_button.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
        self.audio_button.setMenu(self.audio_menu)
        bar.addWidget(self.audio_button)
        self.subs_menu = QMenu(self)
        self.subs_menu.aboutToShow.connect(lambda: self._fill_track_menu(self.subs_menu, "subs"))
        self.subs_button = self._tool_button("subtitles", "Sous-titres (V)")
        self.subs_button.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
        self.subs_button.setMenu(self.subs_menu)
        bar.addWidget(self.subs_button)

        self.fullscreen_button = self._tool_button("fullscreen", "Plein écran (F)", self.toggle_fullscreen)
        bar.addWidget(self.fullscreen_button)
        bar.addWidget(self._tool_button("chevron_down", "Retour à la bibliothèque (Retour arrière)", self.show_library))
        layout.addWidget(self.controls)
        return page

    def _build_audio_page(self):
        page = QWidget()
        page.setObjectName("audio_page")
        page.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.audio_page = page
        self.audio_layout = QHBoxLayout(page)
        self.audio_layout.setContentsMargins(24, 24, 24, 24)
        self.audio_layout.setSpacing(24)
        self.audio_layout.addStretch(1)

        left = QVBoxLayout()
        left.setSpacing(10)
        left.addStretch(1)
        self.cover_label = QLabel()
        self.cover_label.setFixedSize(340, 340)
        left.addWidget(self.cover_label, 0, Qt.AlignmentFlag.AlignHCenter)
        left.addSpacing(10)
        self.audio_title = QLabel("")
        self.audio_title.setObjectName("track_title")
        self.audio_title.setWordWrap(True)
        self.audio_title.setFixedWidth(340)
        self.audio_title.setAlignment(Qt.AlignmentFlag.AlignHCenter)
        left.addWidget(self.audio_title, 0, Qt.AlignmentFlag.AlignHCenter)
        self.audio_artist = QLabel("")
        self.audio_artist.setObjectName("audioArtist")
        self.audio_artist.setWordWrap(True)
        self.audio_artist.setFixedWidth(340)
        self.audio_artist.setAlignment(Qt.AlignmentFlag.AlignHCenter)
        left.addWidget(self.audio_artist, 0, Qt.AlignmentFlag.AlignHCenter)
        left.addStretch(1)
        self.audio_layout.addLayout(left)

        self.lyrics_panel = QWidget()
        lp = QVBoxLayout(self.lyrics_panel)
        lp.setContentsMargins(0, 0, 0, 0)
        lp.setSpacing(10)
        self.lyrics_view = LyricsView()
        self.lyrics_view.setObjectName("lyricsView")
        self.lyrics_view.seek_requested.connect(self.backend.seek_ms)
        lp.addWidget(self.lyrics_view, 1)
        row = QHBoxLayout()
        online = QPushButton("Chercher en ligne")
        online.clicked.connect(lambda: self.fetch_lyrics_online(auto=False))
        load = QPushButton("Importer un .lrc / .txt…")
        load.clicked.connect(self.import_lyrics)
        self.lyrics_source = QLabel("")
        self.lyrics_source.setObjectName("note")
        row.addWidget(online)
        row.addWidget(load)
        row.addWidget(self.lyrics_source, 1)
        lp.addLayout(row)
        self.audio_layout.addWidget(self.lyrics_panel, 1)
        # Stretch symétrique : centre la pochette même quand la playlist est cachée,
        # tout en gardant la colonne de playlist collée au bord droit.
        self.audio_layout.addStretch(1)
        self.playlist_sidebar = QWidget()
        self.playlist_sidebar.setObjectName("playlistSidebar")
        self.playlist_sidebar.setFixedWidth(320)
        playlist_layout = QVBoxLayout(self.playlist_sidebar)
        playlist_layout.setContentsMargins(10, 8, 10, 8)
        playlist_header = QHBoxLayout()
        playlist_title = QLabel("Playlist en cours")
        playlist_title.setObjectName("sectionTitle")
        playlist_header.addWidget(playlist_title, 1)
        self.hide_playlist_button = QPushButton("Masquer")
        self.hide_playlist_button.setObjectName("playlistHide")
        self.hide_playlist_button.clicked.connect(self.toggle_playlist_sidebar)
        playlist_header.addWidget(self.hide_playlist_button)
        playlist_layout.addLayout(playlist_header)
        self.playlist_tracks = QListWidget()
        self.playlist_tracks.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.playlist_tracks.setObjectName("playlistTracks")
        self.playlist_tracks.itemClicked.connect(self._play_playlist_sidebar_item)
        playlist_layout.addWidget(self.playlist_tracks, 1)
        self.playlist_sidebar.setVisible(False)
        self.audio_layout.addWidget(self.playlist_sidebar)
        self.playlist_sidebar_visible = True
        return page

    # ====================================================================== thème
    def apply_theme(self):
        c = self.colors()
        mode = self.cfg.get("background_mode", "color")
        image_key = "background_blurred_image" if mode == "blur" else "background_image"
        image_path = self.cfg.get(image_key, "") if mode in ("image", "blur") else ""
        if image_path and not Path(image_path).is_file():
            image_path = ""
        self._background_pixmap = QPixmap(image_path) if image_path else QPixmap()
        self.setStyleSheet(theme.stylesheet(
            self.cfg.get("accent"), self.cfg.get("background"),
            element_color=self.cfg.get("element_color", theme.PALETTE["panel"]),
        ))
        self.background_layer.set_background(self._background_pixmap, c["bg"])
        central = self.centralWidget()
        if central is not None:
            central.setStyleSheet("background: transparent;")
        if self.stack is not None:
            palette = self.stack.palette()
            palette.setColor(QPalette.ColorRole.Window, QColor(c["bg"]))
            self.stack.setPalette(palette)
            self.stack.setAutoFillBackground(mode == "color")
            self.stack.setStyleSheet(
                f"QStackedWidget#appStack {{ background-color: {c['bg']}; }}"
                if mode == "color" else "QStackedWidget#appStack { background: transparent; }"
            )
            page_style = (
                f"background-color: {c['bg']}; color: {c['text']};"
                if mode == "color" else "background: transparent;"
            )
            for page in (getattr(self, "library_page", None), getattr(self, "player_page", None)):
                if page is not None:
                    page.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
                    page.setStyleSheet(page_style)

        # Paint the panel directly on the sidebar frame. A transparent stacked
        # child could cover the fill and leave only the outline visible.
        sidebar = getattr(self, "sidebar", None)
        if sidebar is not None:
            edge = theme._mix(c["panel"], c["surface_text"], 0.42)
            sidebar.setStyleSheet(
                "QFrame#sidebar {"
                f"background-color: {c['panel']}; border: 1px solid {edge}; "
                "border-radius: 12px;"
                "}"
            )
            sidebar.update()
        logo = getattr(self, "sidebar_logo", None)
        if logo is not None:
            logo.setStyleSheet(
                f"QLabel#logo {{ background-color: {c['panel']}; color: {c['surface_text']}; "
                "font-size: 15px; font-weight: 600; padding: 6px 10px; }"
            )

        # Keep panel styling in the main stylesheet so child labels and icon
        # buttons inherit the same surface instead of painting a second fill.
        # Style nav buttons directly because their idle, hover, and checked
        # fills must stay distinct from the general action buttons.
        nav_buttons = list(getattr(self, "nav_buttons", {}).values())
        more_button = getattr(self, "more_button", None)
        if more_button is not None:
            nav_buttons.append(more_button)
        for button in nav_buttons:
            button.setStyleSheet(
                "QPushButton#nav {"
                f"background-color: transparent; color: {c['surface_dim']}; "
                "border: none; border-radius: 8px; text-align: left; padding: 10px 12px;"
                "}"
                "QPushButton#nav:hover {"
                f"background-color: {c['hover']}; color: {c['surface_text']};"
                "}"
                "QPushButton#nav:checked {"
                f"background-color: {c['panel']}; color: {c['surface_text']};"
                "}"
                "QPushButton#nav:checked:hover {"
                f"background-color: {c['hover']}; color: {c['surface_text']};"
                "}"
                "QPushButton#nav[compact=\"true\"] {text-align: center; padding: 10px 0px;}"
            )
            button.update()
        # QToolButtons also need an explicit transparent idle fill on Windows;
        # otherwise the native control can leave a dark square behind its icon.
        for widget in list(self._icon_registry):
            if not isinstance(widget, QToolButton):
                continue
            if widget.objectName() == "play":
                widget.setStyleSheet(
                    f"background-color: {c['accent']}; border: none; border-radius: 8px; padding: 7px 16px;"
                    f"QToolButton:hover {{ background-color: {c['accent_hi']}; }}"
                )
            elif widget is getattr(self, "sidebar_toggle", None):
                widget.setStyleSheet(
                    f"background-color: {c['panel']}; border: none; border-radius: 8px; padding: 7px;"
                    f"QToolButton:hover {{ background-color: {c['hover']}; }}"
                )
            else:
                widget.setStyleSheet(
                    "background-color: transparent; border: none; border-radius: 8px; padding: 7px;"
                    f"QToolButton:hover {{ background-color: {c['hover']}; }}"
                )
            widget.update()
        self.update()
        for obj in (self.delegate, self.volume, self.np_volume, self.lyrics_view):
            obj.colors = c
        self.volume.update()
        self.np_volume.update()
        self._placeholders.clear()
        self._refresh_icons()
        self.lyrics_view.restyle()
        if self.current:
            self._update_audio_page(self.current)
        if self.page in GRID_PAGES:
            self.refresh_grid()

    def set_accent(self, color):
        self.cfg.set("accent", color)
        self.apply_theme()
        self.save_soon()

    def set_language(self, language):
        """Persist and apply the UI language immediately."""
        language = language if language in ("fr", "en") else "fr"
        self.cfg.set("language", language)
        i18n.translate_tree(self, language)
        if hasattr(self, "discover"):
            self.discover.update_language()
        self.save_soon()

    def set_element_color(self, color):
        self.cfg.set("element_color", color)
        self.apply_theme()
        self.save_soon()

    def remove_selected_from_library(self):
        selected = {item.data(ROLE_PATH) for item in self.grid.selectedItems()}
        if not selected:
            return
        self.cfg.data["library"] = [path for path in self.library if path not in selected]
        self.cfg.data["recents"] = [path for path in self.recents if path not in selected]
        for name, paths in self.playlists.items():
            self.playlists[name] = [path for path in paths if path not in selected]
        self.queue[:] = [path for path in self.queue if path not in selected]
        self.cfg.set("queue", list(self.queue))
        self.refresh_grid()
        self.queue_panel.refresh()
        self.playlists_panel.refresh()
        self.save_soon()
        self.osd(f"{len(selected)} média(s) retiré(s) de la bibliothèque")

    def set_background(self, color):
        self.cfg.set("background", color)
        self.cfg.set("background_mode", "color")
        self.apply_theme()
        self.save_soon()

    def set_background_mode(self, mode):
        self.cfg.set("background_mode", mode if mode in ("color", "image", "blur") else "color")
        self.apply_theme()
        self.save_soon()

    def set_active_playlist(self, name):
        self.active_playlist = name if name in self.playlists else None
        self.refresh_playlist_sidebar()

    def refresh_playlist_sidebar(self):
        if not hasattr(self, "playlist_sidebar"):
            return
        playlist = self.playlists.get(self.active_playlist, []) if self.active_playlist else []
        self.playlist_sidebar.setVisible(bool(playlist) and self.playlist_sidebar_visible)
        if hasattr(self, "playlist_toggle_button"):
            self.playlist_toggle_button.setVisible(bool(playlist))
            self.playlist_toggle_button.setChecked(self.playlist_sidebar_visible)
        blocker = QSignalBlocker(self.playlist_tracks)
        self.playlist_tracks.clear()
        current_row = -1
        for row, path in enumerate(playlist):
            item = QListWidgetItem(self.name_of(path))
            item.setData(Qt.ItemDataRole.UserRole, path)
            item.setToolTip(path)
            item.setSizeHint(QSize(item.sizeHint().width(), 38))
            self.playlist_tracks.addItem(item)
            if path == self.current:
                current_row = row
        if current_row >= 0:
            self.playlist_tracks.setCurrentRow(current_row)
        del blocker

    def toggle_playlist_sidebar(self):
        self.playlist_sidebar_visible = not self.playlist_sidebar_visible
        self.refresh_playlist_sidebar()
        if hasattr(self, "playlist_toggle_button"):
            self.playlist_toggle_button.setChecked(self.playlist_sidebar_visible)

    def _play_playlist_sidebar_item(self, item):
        name = self.active_playlist
        if not name or name not in self.playlists:
            return
        self.play_path(item.data(Qt.ItemDataRole.UserRole),
                       queue=list(self.playlists[name]), playlist_name=name)

    def switch_profile(self, profile_id):
        if self._profile_switch_pending or not profile_id or profile_id == self.cfg.active_profile:
            return
        self._profile_switch_pending = True
        self.save_now()
        self._show_profile_loading()
        # Let Qt paint the overlay before profile data is reloaded.
        QTimer.singleShot(230, lambda: self._complete_profile_switch(profile_id))

    def _show_profile_loading(self):
        colors = self.colors()
        # The small card follows the profile's current theme.
        card = self.profile_loading_overlay.findChild(QFrame, "profileLoadingCard")
        if card:
            card.setStyleSheet(
                f"QFrame#profileLoadingCard {{ background: {colors['panel']}; color: {colors['text']}; "
                f"border: 1px solid {colors['border']}; border-radius: 16px; }}"
            )
        self.profile_loading_label.setText(
            "Loading profile…" if self.cfg.get("language", "fr") == "en" else "Chargement du profil…"
        )
        self.stack.setEnabled(False)
        self.profile_loading_overlay.set_covering(True)
        self.profile_loading_animation.stop()
        self.profile_loading_overlay.setWaveProgress(0.0)
        self.profile_loading_overlay.show()
        self.profile_loading_overlay.raise_()
        self.profile_loading_animation.setStartValue(0.0)
        self.profile_loading_animation.setEndValue(1.0)
        self.profile_loading_animation.start()

    def _complete_profile_switch(self, profile_id):
        try:
            if not self.cfg.switch_profile(profile_id):
                self.settings_panel.refresh()
                QMessageBox.warning(self, "Espace utilisateur", "Impossible d’enregistrer ou d’ouvrir cet espace.")
            else:
                self._reload_profile_data()
                self.profile_loading_label.setText(
                    "Loading profile…" if self.cfg.get("language", "fr") == "en"
                    else "Chargement du profil…"
                )
                i18n.translate_tree(self, self.cfg.get("language", "fr"))
        except Exception as exc:
            log_error(traceback.format_exc())
            QMessageBox.warning(self, "Espace utilisateur", f"Impossible d’ouvrir cet espace : {exc}")
        finally:
            self._profile_switch_pending = False
            self.profile_loading_animation.stop()
            # The dark wave now retreats along the same diagonal, revealing
            # the newly loaded profile from top-left to bottom-right.
            self.profile_loading_overlay.set_covering(False)
            self.profile_loading_overlay.setWaveProgress(0.0)
            self.profile_loading_animation.setStartValue(0.0)
            self.profile_loading_animation.setEndValue(1.0)
            self.profile_loading_animation.start()

    def _finish_profile_loading_wave(self):
        if self.profile_loading_overlay.waveProgress >= 0.999 and not self._profile_switch_pending:
            self.profile_loading_overlay.hide()
            self.stack.setEnabled(True)

    def reset_application(self):
        self._save_timer.stop()
        self.stop()
        if not self.cfg.reset_application():
            QMessageBox.warning(
                self, "Réinitialisation impossible",
                "Les données de l’application n’ont pas pu être réinitialisées. "
                "Vérifie que le dossier de configuration n’est pas utilisé par un autre programme.",
            )
            return
        self._reload_profile_data()

    def create_profile(self, name):
        self.save_now()
        if not self.cfg.create_profile(name):
            QMessageBox.warning(self, "Espace utilisateur", "Ce nom est déjà utilisé ou l’espace n’a pas pu être créé.")
            self.settings_panel.refresh()
            return
        self._reload_profile_data()

    def delete_profile(self, profile_id):
        profile = next((p for p in self.cfg.profiles if p["id"] == profile_id), None)
        if not profile or profile_id == "principal":
            return
        if profile_id == self.cfg.active_profile:
            self.save_now()
            if not self.cfg.switch_profile("principal"):
                QMessageBox.warning(self, "Espace utilisateur", "Impossible de revenir à l’espace Principal.")
                return
            self._reload_profile_data()
        if not self.cfg.delete_profile(profile_id):
            QMessageBox.warning(self, "Espace utilisateur", "Impossible de supprimer cet espace.")
        self.user_panel.refresh()

    def _reload_profile_data(self):
        self.cancel_sleep_timer()
        return_to_user_page = self.page == USER_KEY
        self.stop()
        self.current = None
        self.active_playlist = None
        self.lyrics = None
        self._lyrics_message("")
        self.queue = list(self.cfg.get("queue", []))
        self.tagcache = tags.MetaCache(str(self.cfg.profile_root / self.cfg.active_profile / "tags.json"))
        self.thumbs.clear()
        self._placeholders.clear()
        self._thumb_pending.clear()
        self._thumb_done.clear()
        self.search.clear()
        self.np_name.setText("Aucun média en cours")
        self.setWindowTitle(APP_NAME)
        self.nowplaying.hide()
        self.playlists_panel.current_playlist = None
        self.playlists_panel.refresh()
        self.queue_panel.refresh()
        self.show_library()
        self._set_page(USER_KEY if return_to_user_page else "home")
        self.backend.set_volume(self.cfg.get("volume"))
        self.backend.set_normalize_audio(self.cfg.get("normalize_audio", False))
        self.apply_equalizer()
        self.backend.set_muted(self.cfg.get("muted"))
        self.backend.set_rate(self.cfg.get("playback_rate"))
        self._sync_volume_ui()
        self._sync_repeat_ui()
        self.set_lyrics_visible(self.cfg.get("show_lyrics"), save=False)
        collapsed = bool(self.cfg.get("sidebar_collapsed", False))
        if collapsed != self.sidebar_collapsed:
            self.toggle_sidebar()
        self.apply_theme()
        self.settings_panel.refresh()
        self.user_panel.refresh()

    # =================================================================== navigation
    def show_library(self):
        if self.isFullScreen():
            self.toggle_fullscreen()
        self.stack.setCurrentIndex(0)
        self.shortcuts.set_player_page(False)
        self._update_mini()

    def show_player(self):
        if self.current is None:
            return
        self.stack.setCurrentIndex(1)
        self.shortcuts.set_player_page(True)
        self._update_mini()

    def go_page(self, key):
        self.show_library()
        self._set_page(key)

    def _set_page(self, key):
        self.page = key
        self.page_title.setText(PAGE_TITLES[key])
        if key in self.nav_buttons:
            self.nav_buttons[key].setChecked(True)
        else:
            for button in self.nav_buttons.values():
                button.setChecked(False)
        is_grid = key in GRID_PAGES
        self.search.setVisible(is_grid)
        self.sort_button.setVisible(is_grid)
        self.sort_button.setEnabled(key != "recent")
        self.count_label.setVisible(is_grid)
        if is_grid:
            self.refresh_grid()
        elif key == "playlist":
            self.playlists_panel.refresh()
            self.content_stack.setCurrentWidget(self.playlists_panel)
        elif key == "queue":
            self.queue_panel.refresh()
            self.content_stack.setCurrentWidget(self.queue_panel)
        elif key == "downloads":
            self.content_stack.setCurrentWidget(self.downloads)
        elif key == USER_KEY:
            self.user_panel.refresh()
            self.content_stack.setCurrentWidget(self.user_panel)
        elif key == "discover":
            self.content_stack.setCurrentWidget(self.discover)
            self.discover.opened()
        else:
            self.content_stack.setCurrentWidget(self.settings_panel)
            self.settings_panel.refresh()

    def focus_search(self):
        self.show_library()
        if self.page not in GRID_PAGES:
            self._set_page("home")
        self.search.setFocus()
        self.search.selectAll()

    # ================================================================== bibliothèque
    def _add_menu(self):
        menu = QMenu(self)
        menu.addAction("Fichiers…", self.add_files_dialog)
        menu.addAction("Dossier…", self.add_folder_dialog)
        menu.addAction("Flux réseau…", self.add_stream_dialog)
        return menu

    def add_files_dialog(self):
        paths, _f = QFileDialog.getOpenFileNames(self, "Ajouter des fichiers", str(Path.home()), FILE_FILTER)
        self.add_paths(paths)

    def add_folder_dialog(self):
        folder = QFileDialog.getExistingDirectory(self, "Ajouter un dossier", str(Path.home()))
        if folder:
            self.add_paths([folder])

    def add_stream_dialog(self):
        url, ok = QInputDialog.getText(
            self, "Flux réseau",
            "Adresse d'un son ou d'une vidéo diffusé sur le réseau (http://, https://, rtsp://…) :")
        if not ok:
            return
        if not isinstance(url, str):
            QMessageBox.warning(self, "Adresse invalide", "Entre une adresse réseau valide.")
            return
        url = url.strip()
        if not url:
            return
        scheme = url.partition("://")[0].lower() if "://" in url else ""
        if scheme not in {"http", "https", "rtsp", "rtmp", "udp", "rtp", "mms", "ftp"}:
            QMessageBox.warning(self, "Adresse invalide",
                                "Utilise une adresse http://, https://, rtsp://, rtmp:// ou udp://.")
            return
        self._add_to_library(url)
        self.go_page("network")
        self.save_soon()

    def _add_to_library(self, mrl):
        if mrl not in self.library:
            self.library.append(mrl)
            return True
        return False

    def add_paths(self, paths):
        """Ajoute fichiers, dossiers (récursif) et URL à la bibliothèque. Renvoie ce qui est nouveau."""
        added = []
        for raw in paths:
            if is_stream(raw) and not raw.lower().startswith("file:"):
                found = [raw]
            elif os.path.isdir(raw):
                found = scan_folder(raw)
            elif os.path.isfile(raw):
                found = [raw] if os.path.splitext(raw)[1].lower() in MEDIA_EXT else []
            else:
                found = []
            for item in found:
                if self._add_to_library(item):
                    added.append(item)
        if added:
            self.save_soon()
        if self.page in GRID_PAGES:
            self.refresh_grid()
        return added

    def clear_recents(self):
        self.recents.clear()
        self.save_soon()
        if self.page == "recent":
            self.refresh_grid()

    def _set_sort(self, key, reverse):
        self.cfg.set("sort_key", key)
        self.cfg.set("sort_reverse", reverse)
        self.save_soon()
        self.refresh_grid()

    # --- noms et infos -------------------------------------------------------------
    def media_kind(self, mrl):
        """'audio', 'video' ou 'stream' (un flux sans infos est traité comme une vidéo à l'écran)."""
        saved_meta = self.cfg.data["meta"].get(mrl)
        saved_kind = saved_meta.get("kind") if isinstance(saved_meta, dict) else None
        if saved_kind in ("audio", "video"):
            return saved_kind
        kind = kind_of(mrl)
        if kind == "stream" and mrl in self.cfg.data["meta"]:
            return "audio"          # flux audio avec des informations personnalisées
        return "video" if kind == "stream" else kind

    def meta_of(self, mrl):
        found = self.cfg.data["meta"].get(mrl)
        if isinstance(found, dict):
            return found
        if not is_stream(mrl):
            return self.tagcache.get(mrl) or {}
        return {}

    def name_of(self, mrl):
        title = self.meta_of(mrl).get("title")
        if title:
            return title
        if is_stream(mrl):
            return mrl
        return Path(mrl).stem

    def subtitle_of(self, mrl):
        meta = self.meta_of(mrl)
        return meta.get("artist") or meta.get("album") or ""

    def thumb_of(self, mrl, real_only=False):
        return self.thumbs.get(mrl)

    def placeholder(self, kind):
        if kind not in self._placeholders:
            self._placeholders[kind] = widgets.make_placeholder(kind, self.colors())
        return self._placeholders[kind]

    # --- grille ------------------------------------------------------------------------
    def _visible_entries(self):
        page = self.page
        lib = self.library
        if page == "home":
            entries = list(lib)
        elif page == "video":
            entries = [m for m in lib if self.media_kind(m) == "video"]
        elif page == "music":
            entries = [m for m in lib if self.media_kind(m) == "audio"]
        elif page == "network":
            entries = [m for m in lib if kind_of(m) == "stream"]
        elif page == "recent":
            known = set(lib)
            entries = [m for m in self.recents if m in known]
        elif page == "favorites":
            entries = [m for m in self.cfg.get("favorites", []) if m in lib]
        else:
            entries = []
        needle = self.search.text().strip().lower()
        if needle:
            def haystack(m):
                meta = self.meta_of(m)
                return " ".join((self.name_of(m), meta.get("artist", ""), meta.get("album", ""),
                                 Path(m).name if not is_stream(m) else m)).lower()
            entries = [m for m in entries if needle in haystack(m)]
        if page != "recent":
            if self.cfg.get("sort_key") == "name":
                entries.sort(key=lambda m: self.name_of(m).lower(), reverse=self.cfg.get("sort_reverse"))
            elif self.cfg.get("sort_reverse"):
                entries.reverse()
        return entries

    def make_item(self, mrl, kind, cover_url=""):
        """Carte (nom, artiste, vignette) utilisable dans la bibliothèque et dans Découvrir."""
        if not cover_url:
            cover_url = self.cfg.data["meta"].get(mrl, {}).get("cover", "")
        item = QListWidgetItem(self.name_of(mrl))
        item.setData(ROLE_PATH, mrl)
        item.setData(ROLE_KIND, kind)
        item.setData(ROLE_THUMB, self._thumbnail_for(mrl, kind, cover_url))
        item.setData(ROLE_REAL, mrl in self.thumbs and kind in ("audio", "stream"))
        item.setData(ROLE_SUBTITLE, self.subtitle_of(mrl))
        item.setToolTip(mrl)
        return item

    def refresh_grid(self):
        entries = self._visible_entries()
        self._visible = entries
        self.grid.clear()
        for mrl in entries:
            self.grid.addItem(self.make_item(mrl, kind_of(mrl)))
        count = len(entries)
        self.count_label.setText(f"{count} élément{'s' if count > 1 else ''}" if count else "")
        if entries:
            self.content_stack.setCurrentWidget(self.grid)
        else:
            self.empty_label.setText("Aucun résultat pour cette recherche." if self.search.text().strip()
                                     else EMPTY_MESSAGES.get(self.page, ""))
            self.content_stack.setCurrentWidget(self.empty_label)

    # --- vignettes / pochettes -----------------------------------------------------------
    def _thumbnail_for(self, mrl, kind, cover_url=""):
        if mrl in self.thumbs:
            return self.thumbs[mrl]
        cover_path = self.meta_of(mrl).get("cover_path")
        if cover_path and os.path.isfile(cover_path):
            pix = QPixmap(cover_path)
            if not pix.isNull():
                self.thumbs[mrl] = pix
                return pix
        cached = widgets.find_cached_thumb(mrl)
        if cached:
            pix = QPixmap(cached)
            if not pix.isNull():
                self.thumbs[mrl] = pix
                return pix
        if mrl not in self._thumb_pending and mrl not in self._thumb_done:
            if kind == "audio":
                entry = self.tagcache.get(mrl)
                need = entry is None or not entry.get("nocover")
            elif kind == "video":
                need = True
            else:
                need = bool(cover_url)
            if need:
                self._thumb_pending.add(mrl)
                self.pool.start(ThumbWorker(mrl, kind, self.ffmpeg, cover_url, self.thumb_signals))
        return self.placeholder(kind)

    def _on_thumb_ready(self, src, file, info):
        self._thumb_pending.discard(src)
        self._thumb_done.add(src)
        if info is not None:
            self.tagcache.put(src, info, nocover=not file)
            self.save_soon()
        pix = QPixmap(file) if file else None
        if pix is not None and not pix.isNull():
            self.thumbs[src] = pix
        else:
            pix = None
        for view in (self.grid,):
            for row in range(view.count()):
                item = view.item(row)
                if item.data(ROLE_PATH) != src:
                    continue
                if pix is not None:
                    item.setData(ROLE_THUMB, pix)
                    item.setData(ROLE_REAL, item.data(ROLE_KIND) in ("audio", "stream"))
                item.setText(self.name_of(src))
                item.setData(ROLE_SUBTITLE, self.subtitle_of(src))
            view.viewport().update()
        if src == self.current:
            self._update_audio_page(src)
            self.np_name.setText(self._now_text(src))

    def reset_thumbnails(self):
        self.thumbs.clear()
        self._thumb_done.clear()
        self._thumb_pending.clear()
        self.tagcache.data.clear()
        self.tagcache.dirty = True
        self.save_soon()
        if self.page in GRID_PAGES:
            self.refresh_grid()

    # --- interactions grille --------------------------------------------------------------
    def _on_item_activated(self, item):
        self.play_path(item.data(ROLE_PATH), queue=self._visible)

    def _grid_menu(self, position):
        item = self.grid.itemAt(position)
        if item is None:
            return
        if not item.isSelected():
            self.grid.clearSelection()
            item.setSelected(True)
        mrl = item.data(ROLE_PATH)
        menu = QMenu(self)
        play = menu.addAction("Lire")
        playlist = menu.addAction("Ajouter à une playlist…")
        queue = menu.addAction("Ajouter à la file d’attente")
        favorites = self.cfg.get("favorites", [])
        favorite = menu.addAction("Retirer des favoris" if mrl in favorites else "Ajouter aux favoris")
        edit = menu.addAction("Modifier les informations…")
        remove = menu.addAction("Retirer de la bibliothèque")
        chosen = menu.exec(self.grid.viewport().mapToGlobal(position))
        if chosen is play:
            self.play_path(mrl, queue=self._visible)
        elif chosen is playlist:
            self.add_to_playlist(mrl)
        elif chosen is queue:
            self.add_to_queue(mrl)
        elif chosen is favorite:
            self.toggle_favorite(mrl)
        elif chosen is edit:
            self.edit_media_metadata(mrl)
        elif chosen is remove:
            self.remove_selected_from_library()

    def toggle_favorite(self, mrl):
        favorites = list(self.cfg.get("favorites", []))
        if mrl in favorites:
            favorites.remove(mrl)
            message = "Retiré des favoris"
        else:
            favorites.insert(0, mrl)
            message = "Ajouté aux favoris"
        self.cfg.set("favorites", favorites)
        self.save_soon()
        self.osd(f"{message} : {self.name_of(mrl)}")
        if self.page in GRID_PAGES:
            self.refresh_grid()

    def edit_media_metadata(self, mrl):
        """Edit the app's displayed metadata; source media files stay untouched."""
        current = self.meta_of(mrl)
        values = {}
        for key, label in (("title", "Titre"), ("artist", "Artiste"),
                           ("album", "Album"), ("genre", "Genre")):
            value, accepted = QInputDialog.getText(self, "Modifier les informations", label,
                                                    text=str(current.get(key, "")))
            if not accepted:
                return
            values[key] = value.strip()
        image_path, _ = QFileDialog.getOpenFileName(
            self, "Choisir une pochette (facultatif)", str(Path.home()),
            "Images (*.png *.jpg *.jpeg *.webp *.bmp)"
        )
        if image_path:
            try:
                cover_dir = self.cfg.profile_root / self.cfg.active_profile / "covers"
                cover_dir.mkdir(parents=True, exist_ok=True)
                suffix = Path(image_path).suffix.lower()
                destination = cover_dir / f"{uuid.uuid4().hex}{suffix}"
                shutil.copy2(image_path, destination)
                values["cover_path"] = str(destination)
                pix = QPixmap(str(destination))
                if not pix.isNull():
                    self.thumbs[mrl] = pix
            except OSError as exc:
                QMessageBox.warning(self, "Pochette indisponible", str(exc))
                return
        meta = dict(self.cfg.data.get("meta", {}).get(mrl, {}))
        meta.update(values)
        self.cfg.data.setdefault("meta", {})[mrl] = meta
        self.save_soon()
        self.refresh_grid()
        if self.current == mrl:
            self.np_name.setText(self._now_text(mrl))
            self._update_audio_page(mrl)
        self.osd("Informations mises à jour")

    # --- playlists ------------------------------------------------------------------------
    def add_to_queue(self, mrl):
        self.queue.append(mrl)
        self.cfg.set("queue", list(self.queue))
        self.save_soon()
        self.queue_panel.refresh()
        self.osd(f"Ajouté à la file d’attente : {self.name_of(mrl)}")

    def rename_profile(self, profile_id, name):
        if not self.cfg.rename_profile(profile_id, name):
            return False
        self.user_panel.refresh()
        return True

    def set_profile_image(self, profile_id, path):
        if not self.cfg.set_profile_image(profile_id, path):
            return False
        self.user_panel.refresh()
        return True

    def rename_playlist(self, old_name, new_name):
        new_name = str(new_name).strip()
        if (old_name not in self.playlists or not new_name
                or (new_name != old_name and (new_name in self.playlists
                                                or new_name in self.smart_playlists))):
            return False
        if old_name != new_name:
            self.playlists[new_name] = self.playlists.pop(old_name)
            images = self.cfg.get("playlist_images", {})
            if not isinstance(images, dict):
                images = {}
            if old_name in images:
                images[new_name] = images.pop(old_name)
                self.cfg.set("playlist_images", images)
            if self.active_playlist == old_name:
                self.active_playlist = new_name
            if self.playlists_panel.current_playlist == old_name:
                self.playlists_panel.current_playlist = new_name
                self.playlists_panel.detail_title.setText(new_name)
        self.save_soon()
        self.playlists_panel.refresh()
        self.refresh_playlist_sidebar()
        return True

    def set_playlist_image(self, playlist_name, source_path):
        source = Path(source_path)
        if playlist_name not in self.playlists or not source.is_file():
            return False
        image_dir = self.cfg.profile_root / self.cfg.active_profile / "playlists"
        target = image_dir / (uuid.uuid4().hex + source.suffix.lower())
        try:
            image_dir.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, target)
        except OSError:
            return False
        images = self.cfg.get("playlist_images", {})
        if not isinstance(images, dict):
            images = {}
        images[playlist_name] = str(target)
        self.cfg.set("playlist_images", images)
        self.save_soon()
        self.playlists_panel.refresh()
        self.refresh_playlist_sidebar()
        return True

    def add_to_playlist(self, mrl):
        new_label = "＋ Nouvelle playlist…"
        names = sorted(self.playlists, key=str.lower) + [new_label]
        name, ok = QInputDialog.getItem(self, "Ajouter à une playlist", "Playlist :", names, 0, False)
        if not ok or not name:
            return
        if name == new_label:
            name, ok = QInputDialog.getText(self, "Nouvelle playlist", "Nom de la playlist :")
            name = name.strip()
            if not ok or not name:
                return
            self.playlists.setdefault(name, [])
        if mrl not in self.playlists[name]:
            self.playlists[name].append(mrl)
        self.save_soon()
        self.osd(f"Ajouté à « {name} »")

    def play_playlist(self, name, shuffle=False):
        items = list(self.playlists.get(name, []))
        if not items:
            QMessageBox.information(self, "Playlist vide",
                                    "Ajoutez des médias à cette playlist (clic droit sur un média).")
            return
        if shuffle:
            random.shuffle(items)
        self.play_path(items[0], queue=items, playlist_name=name)

    # ======================================================================= lecture
    def play_path(self, mrl, queue=None, playlist_name=None):
        if not self.backend.available:
            QMessageBox.warning(self, "VLC introuvable", self.backend.error_message())
            return
        self._persist_current_position(force=True)
        self._resume_pending = None
        self.backend.cancel_crossfade()
        self._crossfade_target = None
        self._crossfade_started_at = None
        self._crossfade_fade_duration = 0
        if queue is not None:
            self.queue = list(queue)
        self.active_playlist = playlist_name if playlist_name in self.playlists else None
        if mrl not in self.queue:
            self.queue = [mrl]
        self.cfg.set("queue", list(self.queue))
        self.current = mrl
        self._ended_handled = False
        self._resume_last_saved_position = None
        resume_positions = self.cfg.get("resume_positions", {})
        resume = resume_positions.get(mrl, 0) if isinstance(resume_positions, dict) else 0
        try:
            resume = int(resume or 0)
        except (TypeError, ValueError):
            resume = 0
        if self.cfg.get("resume_playback", True) and resume >= 3000:
            self._resume_pending = (mrl, resume)
        self.seek.setValue(0)
        kind = self.media_kind(mrl)

        self.setWindowTitle(f"{self.name_of(mrl)} — {APP_NAME}")
        self.np_name.setText(self._now_text(mrl))
        self.media_stack.setCurrentWidget(self.audio_page if kind == "audio" else self.video_page)
        self.lyrics_button.setVisible(kind == "audio")
        self.audio_button.setVisible(kind != "audio")
        self.subs_button.setVisible(kind != "audio")
        self._update_audio_page(mrl)
        self.refresh_playlist_sidebar()
        self.nowplaying.show()

        if mrl in self.recents:
            self.recents.remove(mrl)
        self.recents.insert(0, mrl)

        self.show_player()          # crée la fenêtre native avant de donner son id à VLC
        try:
            self.backend.play(mrl, int(self.video.winId()))
        except Exception as exc:
            log_error(traceback.format_exc())
            self.backend.stop()
            self.current = None
            self.active_playlist = None
            self._sync_play_icons(False)
            self.nowplaying.hide()
            self.setWindowTitle(APP_NAME)
            QMessageBox.warning(self, "Lecture impossible",
                                f"Impossible d’ouvrir ce média ou ce flux réseau.\n\n{exc}")
            self.refresh_playlist_sidebar()
            return
        self._sync_play_icons(True)
        if kind == "audio":
            self._load_lyrics(mrl)
        self.save_soon()

    def _now_text(self, mrl):
        artist = self.meta_of(mrl).get("artist")
        return f"{self.name_of(mrl)} — {artist}" if artist else self.name_of(mrl)

    def _update_audio_page(self, mrl):
        meta = self.meta_of(mrl)
        self.audio_title.setText(self.name_of(mrl))
        self.audio_artist.setText(" · ".join(x for x in (meta.get("artist"), meta.get("album")) if x))
        pix = self.thumbs.get(mrl)
        if pix is None:
            pix = widgets.make_placeholder("audio", self.colors(), QSize(340, 340))
        self.cover_label.setPixmap(rounded_pixmap(pix, 340, 16))

    def toggle_play(self):
        if self.current is None:
            self.add_files_dialog()
            return
        if self.backend.active():
            self.backend.pause()
            self._sync_play_icons(False)
        else:
            self._ended_handled = False
            self.backend.resume()
            self._sync_play_icons(True)
        self._update_mini()

    def stop(self):
        if self.current:
            positions = self.cfg.get("resume_positions", {})
            if isinstance(positions, dict) and self.current in positions:
                positions.pop(self.current, None)
                self.cfg.set("resume_positions", positions)
                self.save_soon()
        self._resume_pending = None
        self.backend.stop()
        self._crossfade_target = None
        self._crossfade_started_at = None
        self._crossfade_fade_duration = 0
        self.seek.setValue(0)
        self.np_seek.setValue(0)
        self.time_label.setText("00:00:00")
        self._sync_play_icons(False)
        self._update_mini()

    def next_media(self, direction):
        if not self.queue:
            return
        index = self.queue.index(self.current) if self.current in self.queue else -1
        self.play_path(self.queue[(index + direction) % len(self.queue)],
                       playlist_name=self.active_playlist)

    def seek_relative(self, delta_ms):
        self.backend.seek_ms(self.backend.time() + delta_ms)
        self.osd(f"{format_time(self.backend.time())} / {format_time(self.backend.length())}")

    def _sync_play_icons(self, playing):
        self._last_active = playing
        name = "pause" if playing else "play"
        self._set_icon(self.play_button, name, "onaccent")
        self._set_icon(self.np_play, name, "tool")
        self._set_icon(self.mini.play_button, name, "tool")

    # --- volume, vitesse, répétition ---------------------------------------------------------
    def set_volume(self, value):
        value = max(0, min(MAX_VOLUME, int(value)))
        self.backend.set_volume(value)
        if value > 0 and self.backend.muted:
            self.backend.set_muted(False)
        self.cfg.set("volume", value)
        self.cfg.set("muted", self.backend.muted)
        self._sync_volume_ui()
        self.save_soon()

    def apply_equalizer(self):
        return self.backend.set_equalizer(
            self.cfg.get("equalizer_enabled", False),
            self.cfg.get("equalizer_bands", [0.0] * 10),
            self.cfg.get("equalizer_preamp", 0.0),
        )

    def start_sleep_timer(self, mode):
        if mode == "end":
            if not self.current:
                self.osd("Lance un morceau avant de choisir la fin du morceau.")
                return False
            self._sleep_deadline = None
            self._sleep_end_track = self.current
        else:
            try:
                minutes = max(1, int(mode))
            except (TypeError, ValueError):
                return False
            self._sleep_end_track = None
            self._sleep_deadline = time.monotonic() + minutes * 60
        self._sleep_timer_last_label = None
        self._sleep_timer.start()
        self.settings_panel.update_sleep_status()
        self.osd("Minuteur de veille activé.")
        return True

    def cancel_sleep_timer(self):
        if hasattr(self, "_sleep_timer"):
            self._sleep_timer.stop()
        self._sleep_deadline = None
        self._sleep_end_track = None
        self._sleep_timer_last_label = None
        if hasattr(self, "settings_panel"):
            self.settings_panel.update_sleep_status()

    def _check_sleep_timer(self):
        if self._sleep_deadline is not None:
            remaining = self._sleep_deadline - time.monotonic()
            if remaining <= 0:
                self.cancel_sleep_timer()
                self.stop()
                self.osd("Minuteur terminé : lecture arrêtée.")
                return
            seconds = max(0, int(remaining))
            prefix = "Stops in" if self.cfg.get("language") == "en" else "Arrêt dans"
            label = f"{prefix} {seconds // 60:02d}:{seconds % 60:02d}"
            if label != self._sleep_timer_last_label:
                self._sleep_timer_last_label = label
                self.settings_panel.update_sleep_status(label)
        elif self._sleep_end_track is not None:
            if self.current != self._sleep_end_track or self.backend.ended():
                self.cancel_sleep_timer()
                self.stop()
                self.osd("Fin du morceau : lecture arrêtée.")

    def _persist_current_position(self, force=False):
        if not self.current or not self.backend.available:
            return
        length = self.backend.length()
        position = self.backend.time()
        if length <= 0:
            return
        positions = self.cfg.get("resume_positions", {})
        if not isinstance(positions, dict):
            positions = {}
        now = time.monotonic()
        if position < 3000 or position >= length - 10000:
            changed = self.current in positions
            positions.pop(self.current, None)
        elif force or now - self._resume_last_saved_at >= 5:
            changed = positions.get(self.current) != position
            positions[self.current] = position
            self._resume_last_saved_at = now
            self._resume_last_saved_position = position
        else:
            changed = False
        if changed:
            self.cfg.set("resume_positions", positions)
            self.save_soon()

    def change_volume(self, delta):
        self.set_volume(self.backend.volume + delta)
        self.osd(f"Volume : {self.backend.volume} %")

    def toggle_mute(self):
        self.backend.set_muted(not self.backend.muted)
        self.cfg.set("muted", self.backend.muted)
        self._sync_volume_ui()
        self.save_soon()
        self.osd("Son coupé" if self.backend.muted else f"Volume : {self.backend.volume} %")

    def _sync_volume_ui(self):
        muted = self.backend.muted or self.backend.volume == 0
        for bar in (self.volume, self.np_volume):
            bar.setValue(self.backend.volume)
            bar.setMuted(muted)
        self._set_icon(self.mute_button, "mute" if muted else "volume", "tool")

    def set_rate(self, rate):
        self.backend.set_rate(rate)
        self.cfg.set("playback_rate", self.backend.rate)
        self.save_soon()
        self.osd(f"Vitesse : {self.backend.rate:g}×")

    def change_speed(self, direction):
        rate = self.backend.rate
        if direction > 0:
            nxt = next((s for s in SPEEDS if s > rate + 1e-6), SPEEDS[-1])
        else:
            nxt = next((s for s in reversed(SPEEDS) if s < rate - 1e-6), SPEEDS[0])
        self.set_rate(nxt)

    def set_repeat_mode(self, mode):
        self.cfg.set("repeat_mode", mode)
        self._sync_repeat_ui()
        self.save_soon()
        self.osd(REPEAT_TEXT[mode])

    def cycle_repeat(self):
        self.set_repeat_mode(REPEAT_NEXT[self.cfg.get("repeat_mode")])

    def _sync_repeat_ui(self):
        mode = self.cfg.get("repeat_mode")
        self._set_icon(self.repeat_button, "repeat_one" if mode == "one" else "repeat", "tool")
        self.repeat_button.setChecked(mode != "off")
        self.repeat_button.setToolTip(REPEAT_TEXT[mode] + " (cliquer pour changer)")

    # --- pistes audio / sous-titres ----------------------------------------------------------
    def _fill_track_menu(self, menu, which):
        menu.clear()
        if which == "audio":
            tracks, current = self.backend.audio_tracks()
            setter = self.backend.set_audio_track
        else:
            tracks, current = self.backend.subtitle_tracks()
            setter = self.backend.set_subtitle_track
        if not tracks:
            empty = menu.addAction("Aucune piste disponible")
            empty.setEnabled(False)
        else:
            group = QActionGroup(menu)
            group.setExclusive(True)
            for track_id, name in tracks:
                action = menu.addAction(name)
                action.setCheckable(True)
                action.setChecked(track_id == current)
                group.addAction(action)
                action.triggered.connect(lambda checked=False, tid=track_id, fn=setter: fn(tid))
        menu.addSeparator()
        if which == "audio":
            menu.addAction("Importer une piste audio…", self.import_audio_track)
        else:
            menu.addAction("Importer des sous-titres…", self.import_subtitles)

    def cycle_audio(self):
        name = self.backend.cycle_audio_track()
        self.osd(f"Audio : {name}" if name else "Aucune autre piste audio")

    def cycle_subtitles(self):
        name = self.backend.cycle_subtitle_track()
        self.osd(f"Sous-titres : {name}" if name else "Aucun sous-titre disponible")

    def import_audio_track(self):
        self._import_external("audio")

    def import_subtitles(self):
        self._import_external("subtitle")

    def _import_external(self, kind):
        if not self.current or self.media_kind(self.current) != "video":
            QMessageBox.information(self, "Importer une piste",
                                    "Lancez d'abord une vidéo, puis ajoutez-lui une piste audio "
                                    "ou des sous-titres.")
            return
        if kind == "audio":
            title, exts = "Choisir une piste audio", AUDIO_TRACK_EXT
            label = "Fichiers audio"
        else:
            title, exts = "Choisir des sous-titres", SUBTITLE_EXT
            label = "Sous-titres"
        start = str(Path(self.current).parent) if not is_stream(self.current) else str(Path.home())
        pattern = f"{label} (" + " ".join(f"*{e}" for e in sorted(exts)) + ");;Tous les fichiers (*)"
        path, _f = QFileDialog.getOpenFileName(self, title, start, pattern)
        if path:
            self._add_external(kind, path)

    def _add_external(self, kind, path):
        ok, message = self.backend.add_external_track(kind, path)
        if ok:
            self.osd(("Piste audio ajoutée : " if kind == "audio" else "Sous-titres ajoutés : ") + Path(path).name)
        else:
            QMessageBox.warning(self, "Import impossible", message)

    # --- paroles -------------------------------------------------------------------------------
    def set_lyrics_visible(self, visible, save=True):
        self.cfg.set("show_lyrics", visible)
        self.lyrics_button.setChecked(visible)
        self.lyrics_panel.setVisible(visible)
        # La playlist reste le dernier élément du layout, donc ancrée à droite.
        # Masquer les paroles ne doit jamais déplacer ni masquer cette colonne.
        self.audio_layout.setStretch(0, 1)
        self.audio_layout.setStretch(self.audio_layout.indexOf(self.lyrics_panel), 1 if visible else 0)
        if visible and self.current and self.media_kind(self.current) == "audio" and not self.lyrics:
            self._load_lyrics(self.current)
        if save:
            self.save_soon()

    def toggle_lyrics(self):
        if self.current and self.media_kind(self.current) == "audio":
            self.set_lyrics_visible(not self.cfg.get("show_lyrics"))

    def _show_lyrics(self, found):
        self.lyrics = found
        self.lyrics_view.set_lyrics(found)
        self.lyrics_source.setText(f"Source : {found.source}" if found.source else "")
        if found.synced:
            self.lyrics_view.set_position(self.backend.time())

    def _lyrics_message(self, text):
        self.lyrics = None
        self.lyrics_source.setText("")
        self.lyrics_view.set_message(text)

    def _load_lyrics(self, mrl):
        self._lyrics_message("")
        if not self.cfg.get("show_lyrics"):
            return
        self._lyrics_message("Chargement des paroles…")
        local = not is_stream(mrl)

        def work():
            if not local:
                return None
            embedded = tags.read_info(mrl).get("lyrics") if os.path.splitext(mrl)[1].lower() in (".mp3", ".flac", ".m4a", ".mp4") else None
            return lyrics.load_local(mrl, embedded)

        def done(found):
            if mrl != self.current:
                return
            if found:
                self._show_lyrics(found)
            elif self.cfg.get("lyrics_online"):
                self.fetch_lyrics_online(auto=True)
            else:
                self._lyrics_message("Aucune parole sur cet ordinateur.\nCliquez sur « Chercher en ligne » "
                                     "ou importez un fichier .lrc.")

        self.runner.run(work, done, lambda e: self._lyrics_message(f"Paroles indisponibles : {e}"), key="lyrics")

    def fetch_lyrics_online(self, auto=False):
        mrl = self.current
        if not mrl or self.media_kind(mrl) != "audio":
            return
        info = self.meta_of(mrl)
        artist, title = lyrics.guess_artist_title(mrl, info)
        album = info.get("album", "")
        duration = self.backend.length() // 1000
        self._lyrics_message("Recherche des paroles en ligne…")

        def done(found):
            if mrl != self.current:
                return
            if found:
                try:
                    lyrics.save_cache(mrl, found)
                except OSError:
                    pass
                self._show_lyrics(found)
            else:
                self._lyrics_message("Aucune parole trouvée pour ce titre.\nVous pouvez importer un fichier .lrc.")

        self.runner.run(lambda: lyrics.fetch_lrclib(artist, title, album, duration), done,
                        lambda e: self._lyrics_message(str(e)), key="lyrics")

    def import_lyrics(self, path=None):
        if not self.current or self.media_kind(self.current) != "audio":
            return
        if not path:
            path, _f = QFileDialog.getOpenFileName(self, "Importer des paroles", str(Path.home()),
                                                   "Paroles (*.lrc *.txt);;Tous les fichiers (*)")
        if not path:
            return
        try:
            found = lyrics.load_file(path)
        except OSError as exc:
            QMessageBox.warning(self, "Paroles", f"Lecture impossible : {exc}")
            return
        if not found:
            QMessageBox.information(self, "Paroles", "Ce fichier ne contient aucune parole exploitable.")
            return
        try:
            lyrics.save_cache(self.current, found)     # retrouvées à la prochaine lecture
        except OSError:
            pass
        self._show_lyrics(found)

    # --- affichage ----------------------------------------------------------------------------
    def toggle_fullscreen(self):
        if self.isFullScreen():
            self.showNormal()
        else:
            self.showFullScreen()
        self._set_icon(self.fullscreen_button,
                       "fullscreen_exit" if self.isFullScreen() else "fullscreen", "tool")

    def leave_fullscreen(self):
        if self.isFullScreen():
            self.toggle_fullscreen()

    def toggle_controls(self):
        self.controls.setVisible(not self.controls.isVisible())

    def osd(self, text):
        """Petit message temporaire (visible même par-dessus la vidéo)."""
        pos = self.mapToGlobal(QPoint(self.width() // 2 - 80, 70))
        QToolTip.showText(pos, text, self, QRect(), 1600)

    # --- mini-lecteur vidéo ---------------------------------------------------------------------
    def _dock_video(self, where):
        if where == self._docked:
            return
        self._docked = where
        if where == "mini":
            self.video_layout.removeWidget(self.video)
            self.mini.adopt(self.video)
        else:
            self.mini.release_video()
            self.video_layout.addWidget(self.video)
            self.video_layout.activate()
            self.video.show()
        self.video.ensurePolished()
        def reattach():
            if self._docked == where:
                self.backend.attach(int(self.video.winId()))
        QTimer.singleShot(0, reattach)
        QTimer.singleShot(160, reattach)

    def _update_mini(self):
        """Vidéo en bas à droite quand on quitte le lecteur ; fermée si la vidéo est en pause."""
        want = (self.stack.currentIndex() == 0 and self.current is not None
                and self.media_kind(self.current) == "video"
                and self.backend.active() and self.backend.has_video())
        if want:
            self._dock_video("mini")
            self.mini.set_title(self.name_of(self.current))
            self.mini.show()
            self.mini.place()
        else:
            self.mini.hide()
            self._dock_video("player")

    def _close_mini(self):
        self.stop()

    def _video_double_click(self):
        if self._docked == "mini":
            self.show_player()
        else:
            self.toggle_fullscreen()

    def _video_menu(self, global_pos):
        menu = QMenu(self)
        menu.addAction("Pause" if self.backend.active() else "Lecture", self.toggle_play)
        menu.addAction("Plein écran", self.toggle_fullscreen)
        menu.addSeparator()
        audio, subs = menu.addMenu("Piste audio"), menu.addMenu("Sous-titres")
        self._fill_track_menu(audio, "audio")
        self._fill_track_menu(subs, "subs")
        menu.addSeparator()
        menu.addAction("Retour à la bibliothèque", self.show_library)
        menu.exec(global_pos)

    # ===================================================================== minuterie
    def _tick(self):
        if self.current is None or not self.backend.available:
            return
        self.backend.tick()
        if self._resume_pending and self._resume_pending[0] == self.current and self.backend.active():
            resume_position = self._resume_pending[1]
            media_length = self.backend.length()
            if media_length > 0:
                self.backend.seek_ms(min(resume_position, max(0, media_length - 1000)))
                self._resume_pending = None
        length, position = self.backend.length(), self.backend.time()
        self._tick_crossfade(length, position)
        length, position = self.backend.length(), self.backend.time()
        self._persist_current_position()
        fraction = min(1000, int(position / length * 1000)) if length > 0 else None
        if fraction is not None:
            if not self.seek.dragging:
                self.seek.setValue(fraction)
            if not self.np_seek.dragging:
                self.np_seek.setValue(fraction)
        self.np_time.setText(f"{format_time(position)} / {format_time(length)}")
        self.time_label.setText(format_time(position))
        self.total_label.setText(format_time(length))

        active = self.backend.active()
        if self._last_active is not None and active != self._last_active and not self.backend.ended():
            self._sync_play_icons(active)      # changement venant de VLC lui-même
        self._update_mini()

        if self.lyrics and self.lyrics.synced and self.stack.currentIndex() == 1 and self.lyrics_panel.isVisible():
            self.lyrics_view.set_position(position)

        if self.backend.ended() and not self._ended_handled:
            self._ended_handled = True
            # If the outgoing decoder reaches EOF just before the last timer
            # tick of the fade, keep the already-playing incoming decoder.
            # Falling through to _on_media_ended() would reopen it at 00:00.
            target = self._crossfade_target
            incoming_ready, _ = self.backend.crossfade_status() if target else (False, 0)
            if target and incoming_ready:
                self.backend.set_crossfade_progress(1.0)
                if self.backend.finish_crossfade():
                    self._complete_crossfade(target)
            else:
                self._on_media_ended()

    def _tick_crossfade(self, length, position):
        seconds = int(self.cfg.get("crossfade_seconds", 0) or 0)
        if seconds <= 0:
            if self._crossfade_target is not None:
                self.backend.cancel_crossfade()
                self._crossfade_target = None
                self._crossfade_started_at = None
                self._crossfade_fade_duration = 0
            return
        if not self.backend.active() or not self.current:
            return
        if self.cfg.get("repeat_mode") == "one":
            if self._crossfade_target is not None:
                self.backend.cancel_crossfade()
                self._crossfade_target = None
                self._crossfade_started_at = None
                self._crossfade_fade_duration = 0
            return
        index = self.queue.index(self.current) if self.current in self.queue else -1
        target = None
        if index >= 0 and index + 1 < len(self.queue) and self.cfg.get("autoplay_next", True):
            target = self.queue[index + 1]
        elif index == len(self.queue) - 1 and self.cfg.get("repeat_mode") == "all" and self.queue:
            target = self.queue[0]
        if (not target or target == self.current or self.media_kind(self.current) != "audio"
                or self.media_kind(target) != "audio"):
            if self._crossfade_target is not None:
                self.backend.cancel_crossfade()
                self._crossfade_target = None
                self._crossfade_started_at = None
                self._crossfade_fade_duration = 0
            return
        duration = min(seconds * 1000, max(0, length - 1000))
        if duration <= 0:
            return
        remaining = length - position
        if self._crossfade_target is None and 0 < remaining <= duration:
            if self.backend.begin_crossfade(target):
                self._crossfade_target = target
        if self._crossfade_target is not None and self._crossfade_target != target:
            self.backend.cancel_crossfade()
            self._crossfade_target = None
            self._crossfade_started_at = None
            self._crossfade_fade_duration = 0
        if self._crossfade_target != target:
            return
        incoming_ready, _incoming_time = self.backend.crossfade_status()
        if not incoming_ready:
            # Keep the outgoing track at full level until VLC has really started
            # decoding the incoming one. If it stalls at the very end, fall back
            # to the regular next-track handler instead of leaving silence.
            if remaining <= 250:
                self.backend.cancel_crossfade()
                self._crossfade_target = None
                self._crossfade_started_at = None
                self._crossfade_fade_duration = 0
            return
        if self._crossfade_started_at is None:
            # Start the wall-clock ramp only once VLC confirms that the
            # incoming decoder is producing playback.
            self._crossfade_started_at = time.monotonic()
            # Use the wall clock for a steady ramp; VLC's reported playback
            # position can advance in uneven steps and make the fade lurch.
            available_overlap = max(50, remaining - 50)
            self._crossfade_fade_duration = max(50, min(duration, available_overlap))
        elapsed = max(0, (time.monotonic() - self._crossfade_started_at) * 1000)
        fade_duration = max(1, self._crossfade_fade_duration)
        incoming_progress = elapsed / fade_duration
        progress = min(1.0, max(0.0, incoming_progress))
        self.backend.set_crossfade_progress(progress)
        if progress >= 1.0 and self.backend.finish_crossfade():
            self._complete_crossfade(target)

    def _complete_crossfade(self, target):
        """Finish UI/state bookkeeping after the incoming VLC player is promoted."""
        self.current = target
        self._crossfade_target = None
        self._crossfade_started_at = None
        self._crossfade_fade_duration = 0
        self._ended_handled = False
        if target in self.recents:
            self.recents.remove(target)
        self.recents.insert(0, target)
        self.np_name.setText(self._now_text(target))
        self.setWindowTitle(f"{self.name_of(target)} — {APP_NAME}")
        self._update_audio_page(target)
        self.refresh_playlist_sidebar()
        self._load_lyrics(target)
        self.seek.setValue(0)
        self.np_seek.setValue(0)
        self._sync_play_icons(True)
        self.save_soon()

    def _on_media_ended(self):
        mode = self.cfg.get("repeat_mode")
        index = self.queue.index(self.current) if self.current in self.queue else -1
        if mode == "one" and self.current:
            self.play_path(self.current, queue=self.queue, playlist_name=self.active_playlist)
        elif self.cfg.get("autoplay_next") and 0 <= index < len(self.queue) - 1:
            self.play_path(self.queue[index + 1], playlist_name=self.active_playlist)
        elif mode == "all" and self.queue:
            self.play_path(self.queue[0], playlist_name=self.active_playlist)
        else:
            self.seek.setValue(1000)
            self._sync_play_icons(False)
            self._update_mini()

    # =================================================================== raccourcis
    def _bind_shortcuts(self):
        handlers = {
            "play_pause": self.toggle_play,
            "stop": self.stop,
            "prev": lambda: self.next_media(-1),
            "next": lambda: self.next_media(1),
            "seek_back": lambda: self.seek_relative(-10_000),
            "seek_fwd": lambda: self.seek_relative(10_000),
            "seek_back_long": lambda: self.seek_relative(-60_000),
            "seek_fwd_long": lambda: self.seek_relative(60_000),
            "speed_down": lambda: self.change_speed(-1),
            "speed_up": lambda: self.change_speed(1),
            "speed_reset": lambda: self.set_rate(1.0),
            "vol_up": lambda: self.change_volume(5),
            "vol_down": lambda: self.change_volume(-5),
            "mute": self.toggle_mute,
            "audio_cycle": self.cycle_audio,
            "sub_cycle": self.cycle_subtitles,
            "import_audio": self.import_audio_track,
            "import_subs": self.import_subtitles,
            "fullscreen": self.toggle_fullscreen,
            "leave_fs": self.leave_fullscreen,
            "hide_ui": self.toggle_controls,
            "lyrics": self.toggle_lyrics,
            "to_library": self.show_library,
            "open_files": self.add_files_dialog,
            "open_folder": self.add_folder_dialog,
            "open_stream": self.add_stream_dialog,
            "search": self.focus_search,
            "page_home": lambda: self.go_page("home"),
            "page_video": lambda: self.go_page("video"),
            "page_music": lambda: self.go_page("music"),
            "page_playlist": lambda: self.go_page("playlist"),
            "page_discover": lambda: self.go_page("discover"),
            "settings": lambda: self.go_page(SETTINGS_KEY),
            "help": self.show_help,
            "quit": self.close,
        }
        self.shortcuts = shortcuts.ShortcutManager(self, handlers, self.cfg.get("shortcuts"))

    # ============================================================== aide et tutoriel
    def show_help(self):
        HelpDialog(self).exec()

    def show_wizard(self):
        WizardDialog(self).exec()
        self.cfg.set("setup_done", True)
        self.save_soon()
        self.apply_theme()

    # ============================================================ glisser-déposer
    def _handle_dropped_items(self, items):
        sub_exts = SUBTITLE_EXT - {".txt"}
        remaining = []
        for item in items:
            ext = os.path.splitext(item)[1].lower()
            if (self.current and not is_stream(item) and self.stack.currentIndex() == 1
                    and self.media_kind(self.current) == "video" and ext in sub_exts):
                self._add_external("subtitle", item)
            elif ext == ".lrc" and self.current and self.media_kind(self.current) == "audio":
                self.import_lyrics(item)
            else:
                remaining.append(item)
        added = self.add_paths(remaining)
        if added:
            self.osd(f"{len(added)} média(s) ajouté(s)")

    def dragEnterEvent(self, event):
        if event.mimeData().hasUrls():
            event.acceptProposedAction()

    def dropEvent(self, event):
        items = [u.toLocalFile() if u.isLocalFile() else u.toString() for u in event.mimeData().urls()]
        if items:
            self._handle_dropped_items(items)
            event.acceptProposedAction()

    # ================================================================== mises à jour
    def check_updates(self, manual=False):
        """Cherche une nouvelle version sur GitHub (en arrière-plan)."""
        import updater
        import version

        def failed(exc):
            if manual:
                QMessageBox.warning(self, APP_NAME, f"Impossible de vérifier les mises à jour :\n{exc}")

        def done(info):
            if not info:
                if manual:
                    QMessageBox.information(
                        self, APP_NAME, f"Vous avez déjà la dernière version ({version.__version__}).")
                return
            if not manual and self.cfg.get("skipped_version") == info["version"]:
                return
            self._offer_update(info)

        self.runner.run(lambda: updater.check(version.__version__, version.GITHUB_REPO),
                        done, failed, key="update_check")

    def _offer_update(self, info):
        import updater
        from PySide6.QtCore import QUrl
        from PySide6.QtGui import QDesktopServices

        text = f"La version {info['version']} est disponible."
        if info["notes"]:
            text += "\n\nNouveautés :\n" + info["notes"][:600]
        can_install = updater.is_frozen() and info["url"] and sys.platform.startswith("win")
        text += "\n\nInstaller maintenant ?" if can_install else "\n\nOuvrir la page de téléchargement ?"
        box = QMessageBox(QMessageBox.Icon.Question, "Mise à jour disponible", text,
                          QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No, self)
        skip = box.addButton("Ignorer cette version", QMessageBox.ButtonRole.RejectRole)
        box.exec()
        if box.clickedButton() is skip:
            self.cfg.set("skipped_version", info["version"])
            self.cfg.save()
            return
        if box.standardButton(box.clickedButton()) != QMessageBox.StandardButton.Yes:
            return
        if not can_install:
            QDesktopServices.openUrl(QUrl(info["page"]))
            return

        self.osd("Téléchargement de la mise à jour…")

        def installed(path):
            updater.launch_installer(path)
            self.close()
            QApplication.quit()

        self.runner.run(lambda: updater.download(info["url"], info["name"]), installed,
                        lambda exc: QMessageBox.warning(self, APP_NAME, f"Échec du téléchargement :\n{exc}"),
                        key="update_download")

    # ================================================================== fermeture
    def closeEvent(self, event):
        self.timer.stop()
        self._persist_current_position(force=True)
        self.runner.wait(1000)
        self.pool.waitForDone(1500)
        self.save_now()
        self.backend.close()
        event.accept()


def install_crash_hook():
    state = {"shown": False}

    def hook(exc_type, exc, tb):
        text = "".join(traceback.format_exception(exc_type, exc, tb))
        log_error(text)
        sys.stderr.write(text)
        if state["shown"]:
            return                      # un seul message, même si l'erreur se répète (minuterie…)
        state["shown"] = True
        try:
            QMessageBox.critical(
                None, APP_NAME,
                f"Une erreur inattendue s'est produite :\n\n{exc}\n\n"
                f"Détails enregistrés dans :\n{LOG_PATH}\n\n"
                "L'application reste ouverte ; si elle se comporte bizarrement, relancez-la.")
        except Exception:
            pass

    sys.excepthook = hook


def main():
    if sys.platform.startswith("linux"):
        # libVLC ne sait s'intégrer qu'à une fenêtre X11 : on évite Wayland natif.
        os.environ.setdefault("QT_QPA_PLATFORM", "xcb")

    app = QApplication(sys.argv)
    app.setApplicationName(APP_NAME)
    install_crash_hook()

    window = MainWindow()
    window.show()

    if not window.cfg.get("setup_done"):
        QTimer.singleShot(300, window.show_wizard)
    elif not window.backend.available:
        QTimer.singleShot(300, lambda: QMessageBox.warning(window, "VLC introuvable", window.backend.error_message()))

    if window.cfg.get("auto_update", True):
        QTimer.singleShot(4000, window.check_updates)

    # python main.py fichier1 dossier2 … : ajoute et lance le premier média
    if len(sys.argv) > 1:
        added = window.add_paths(sys.argv[1:])
        first = added[0] if added else None
        if first and window.backend.available:
            window.play_path(first, queue=added)

    sys.exit(app.exec())


if __name__ == "__main__":
    try:
        main()
    except SystemExit:
        raise
    except Exception:
        fatal("L'application n'a pas pu démarrer.\n\n" + traceback.format_exc())


