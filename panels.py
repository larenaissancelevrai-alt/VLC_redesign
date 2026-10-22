"""Panneaux de bibliothÃ¨que : playlists, rÃ©glages et dÃ©couverte YouTube."""
import shutil
from pathlib import Path

from PySide6.QtCore import Qt, QSignalBlocker, QSize, QRectF
from PySide6.QtGui import QColor, QIcon, QImage, QPainter, QPixmap
from PySide6.QtWidgets import (
    QAbstractItemView, QButtonGroup, QCheckBox, QColorDialog, QComboBox, QDialog, QDialogButtonBox,
    QFileDialog, QFormLayout, QFrame, QGraphicsBlurEffect, QGraphicsPixmapItem, QGraphicsScene,
    QGridLayout, QHBoxLayout, QLabel, QLineEdit, QListView, QListWidget,
    QListWidgetItem, QMessageBox, QPushButton, QScrollArea, QSlider, QStackedWidget,
    QToolButton, QVBoxLayout,
    QWidget,
)
import theme
from animated_controls import AnimatedPushButton as QPushButton, AnimatedToolButton as QToolButton

SPEEDS = [0.25, 0.5, 0.75, 1.0, 1.25, 1.5, 1.75, 2.0, 3.0, 4.0]
EQ_BANDS = ["60 Hz", "170 Hz", "310 Hz", "600 Hz", "1 kHz", "3 kHz", "6 kHz", "12 kHz", "14 kHz", "16 kHz"]
EQ_PRESETS = {
    "flat": [0, 0, 0, 0, 0, 0, 0, 0, 0, 0],
    "bass": [7, 6, 5, 2, 0, -1, -2, -2, -2, -2],
    "treble": [-2, -2, -1, 0, 1, 3, 5, 6, 6, 6],
    "vocal": [-3, -2, 0, 3, 5, 4, 2, 0, -1, -2],
    "classical": [4, 3, 2, 1, -1, -1, 0, 2, 3, 4],
}


class EqualizerDialog(QDialog):
    def __init__(self, bands, preamp, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Égaliseur personnalisé")
        layout = QVBoxLayout(self)
        grid = QGridLayout()
        self.sliders = []
        values = list(bands)[:10]
        values += [0] * (10 - len(values))
        for column, (label, value) in enumerate(zip(EQ_BANDS, values)):
            band_label = QLabel(label)
            band_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            slider = QSlider(Qt.Orientation.Vertical)
            slider.setRange(-12, 12)
            slider.setValue(round(float(value)))
            slider.setTickPosition(QSlider.TickPosition.TicksBothSides)
            slider.setTickInterval(6)
            readout = QLabel(f"{slider.value()} dB")
            readout.setAlignment(Qt.AlignmentFlag.AlignCenter)
            slider.valueChanged.connect(lambda v, out=readout: out.setText(f"{v} dB"))
            grid.addWidget(band_label, 0, column)
            grid.addWidget(slider, 1, column, alignment=Qt.AlignmentFlag.AlignHCenter)
            grid.addWidget(readout, 2, column)
            self.sliders.append(slider)
        layout.addLayout(grid)
        preamp_row = QHBoxLayout()
        preamp_row.addWidget(QLabel("Préamplification"))
        self.preamp = QSlider(Qt.Orientation.Horizontal)
        self.preamp.setRange(-12, 12)
        self.preamp.setValue(round(float(preamp)))
        preamp_row.addWidget(self.preamp, 1)
        self.preamp_label = QLabel(f"{self.preamp.value()} dB")
        self.preamp.valueChanged.connect(lambda v: self.preamp_label.setText(f"{v} dB"))
        preamp_row.addWidget(self.preamp_label)
        layout.addLayout(preamp_row)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)
        self.resize(680, 380)

    def values(self):
        return [slider.value() for slider in self.sliders], self.preamp.value()


class PlaylistsPanel(QWidget):
    def __init__(self, window):
        super().__init__()
        self.window = window
        self.current_playlist = None
        self.selected_playlist = None
        root = QVBoxLayout(self)
        self.pages = QStackedWidget()
        root.addWidget(self.pages, 1)

        overview = QWidget()
        overview_layout = QVBoxLayout(overview)
        title = QLabel("Playlists")
        title.setObjectName("title")
        overview_layout.addWidget(title)
        self.cards_host = QWidget()
        self.cards_grid = QGridLayout(self.cards_host)
        self.cards_grid.setContentsMargins(4, 8, 4, 8)
        self.cards_grid.setHorizontalSpacing(14)
        self.cards_grid.setVerticalSpacing(14)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setWidget(self.cards_host)
        overview_layout.addWidget(scroll, 1)
        overview_actions = QHBoxLayout()
        self.create_button = QPushButton("Nouvelle playlist")
        self.create_button.clicked.connect(self._create)
        overview_actions.addWidget(self.create_button)
        self.create_smart_button = QPushButton("Playlist intelligente…")
        self.create_smart_button.clicked.connect(self._create_smart_playlist)
        overview_actions.addWidget(self.create_smart_button)
        self.import_playlist_button = QPushButton("Importer M3U / PLS…")
        self.import_playlist_button.clicked.connect(self._import_playlist)
        overview_actions.addWidget(self.import_playlist_button)
        self.edit_playlist_button = QPushButton("Renommer / image…")
        self.edit_playlist_button.clicked.connect(self._edit_selected_playlist)
        overview_actions.addWidget(self.edit_playlist_button)
        self.delete_playlist_button = QPushButton("Supprimer la playlist")
        self.delete_playlist_button.clicked.connect(self._delete_selected_playlist)
        overview_actions.addWidget(self.delete_playlist_button)
        overview_layout.addLayout(overview_actions)
        self.pages.addWidget(overview)

        detail = QWidget()
        detail_layout = QVBoxLayout(detail)
        top = QHBoxLayout()
        self.back_button = QPushButton("← Playlists")
        self.back_button.clicked.connect(lambda: self.pages.setCurrentIndex(0))
        top.addWidget(self.back_button)
        self.detail_title = QLabel("")
        self.detail_title.setObjectName("title")
        top.addWidget(self.detail_title, 1)
        self.edit_current_button = QPushButton("Renommer / image…")
        self.edit_current_button.clicked.connect(lambda: self._edit_playlist(self.current_playlist))
        top.addWidget(self.edit_current_button)
        self.delete_current_button = QPushButton("Supprimer")
        self.delete_current_button.clicked.connect(self._delete_current_playlist)
        top.addWidget(self.delete_current_button)
        detail_layout.addLayout(top)
        self.tracks = QListWidget()
        self.tracks.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self.tracks.itemDoubleClicked.connect(self._play_track)
        detail_layout.addWidget(self.tracks, 1)
        actions = QHBoxLayout()
        self.add_tracks_button = QPushButton("Ajouter des musiques…")
        self.add_tracks_button.clicked.connect(self._add_tracks)
        self.remove_tracks_button = QPushButton("Retirer de la playlist")
        self.remove_tracks_button.clicked.connect(self._remove_tracks)
        actions.addWidget(self.add_tracks_button)
        actions.addWidget(self.remove_tracks_button)
        self.export_playlist_button = QPushButton("Exporter M3U / PLS…")
        self.export_playlist_button.clicked.connect(self._export_playlist)
        actions.addWidget(self.export_playlist_button)
        detail_layout.addLayout(actions)
        self.pages.addWidget(detail)

    def refresh(self):
        while self.cards_grid.count():
            item = self.cards_grid.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()

        images = self.window.cfg.get("playlist_images", {})
        if not isinstance(images, dict):
            images = {}
        index = 0
        for name, tracks in self.window.playlists.items():
            card = QToolButton()
            card.setObjectName("profileCard")
            card.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextUnderIcon)
            count = len(tracks) if isinstance(tracks, list) else 0
            suffix = "En cours" if name == self.window.active_playlist else f"{count} média(s)"
            card.setText(f"{name}\n{suffix}")
            card.setIcon(QIcon(UserPanel._avatar(name, "playlist:" + name, images.get(name, ""))))
            card.setIconSize(QSize(104, 104))
            card.setFixedSize(156, 166)
            card.setCheckable(True)
            card.setChecked(name == self.window.active_playlist)
            card.setToolTip(f"Ouvrir la playlist {name}")
            card.clicked.connect(lambda _checked=False, playlist=name: self._show_playlist(playlist))
            self.cards_grid.addWidget(card, index // 4, index % 4)
            index += 1

        for name in self.window.smart_playlists:
            card = QToolButton()
            card.setObjectName("profileCard")
            card.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextUnderIcon)
            count = len(self.window.smart_playlist_tracks(name))
            suffix = (f"{count} result(s) • auto" if self.window.cfg.get("language") == "en"
                      else f"{count} résultat(s) • auto")
            card.setText(f"{name}\n{suffix}")
            card.setIcon(QIcon(UserPanel._avatar(name, "smart:" + name)))
            card.setIconSize(QSize(104, 104))
            card.setFixedSize(156, 166)
            card.setCheckable(True)
            card.setChecked(name == self.selected_playlist)
            card.setToolTip(f"Playlist intelligente : {name}")
            card.clicked.connect(lambda _checked=False, playlist=name: self._show_smart_playlist(playlist))
            self.cards_grid.addWidget(card, index // 4, index % 4)
            index += 1

        create = QToolButton()
        create.setObjectName("profileCard")
        create.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextUnderIcon)
        create.setText("Nouvelle playlist")
        create.setIcon(QIcon(UserPanel._create_avatar()))
        create.setIconSize(QSize(104, 104))
        create.setFixedSize(156, 166)
        create.setToolTip("Créer une playlist")
        create.clicked.connect(self._create)
        self.cards_grid.addWidget(create, index // 4, index % 4)

        all_names = set(self.window.playlists) | set(self.window.smart_playlists)
        self.selected_playlist = self.selected_playlist if self.selected_playlist in all_names else None
        self.delete_playlist_button.setEnabled(self.selected_playlist is not None)
        self.edit_playlist_button.setEnabled(self.selected_playlist in self.window.playlists)
        if self.current_playlist in all_names and self.pages.currentIndex() == 1:
            self._refresh_tracks()
        else:
            self.pages.setCurrentIndex(0)

    def _create(self):
        self._edit_playlist(None)

    def _create_smart_playlist(self):
        dialog = QDialog(self)
        dialog.setWindowTitle("Nouvelle playlist intelligente")
        layout = QVBoxLayout(dialog)
        form = QFormLayout()
        name = QLineEdit()
        name.setPlaceholderText("Ex. Favoris rock")
        artist = QLineEdit()
        artist.setPlaceholderText("Filtre facultatif")
        genre = QLineEdit()
        genre.setPlaceholderText("Filtre facultatif")
        favorites = QCheckBox("Limiter aux favoris")
        form.addRow("Nom", name)
        form.addRow("Artiste contient", artist)
        form.addRow("Genre contient", genre)
        form.addRow("Favoris", favorites)
        layout.addLayout(form)
        layout.addWidget(QLabel("La liste se met à jour automatiquement depuis ta bibliothèque."))
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(dialog.accept)
        buttons.rejected.connect(dialog.reject)
        layout.addWidget(buttons)
        dialog.resize(440, 210)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        playlist_name = name.text().strip()
        if not playlist_name:
            QMessageBox.warning(self, "Nom invalide", "Saisis un nom pour la playlist.")
            return
        if playlist_name in self.window.playlists or playlist_name in self.window.smart_playlists:
            QMessageBox.warning(self, "Playlist existante", "Une playlist porte déjà ce nom.")
            return
        smart = self.window.cfg.get("smart_playlists", {})
        smart[playlist_name] = {
            "artist": artist.text().strip(),
            "genre": genre.text().strip(),
            "favorites": favorites.isChecked(),
        }
        self.window.cfg.set("smart_playlists", smart)
        self.window.save_soon()
        self.refresh()
        self._show_smart_playlist(playlist_name)

    def _import_playlist(self):
        path, _selected_filter = QFileDialog.getOpenFileName(
            self, "Importer une playlist", str(Path.home()),
            "Playlists (*.m3u *.m3u8 *.pls);;Tous les fichiers (*.*)",
        )
        if not path:
            return
        source = Path(path)
        try:
            try:
                text = source.read_text(encoding="utf-8-sig")
            except UnicodeError:
                text = source.read_text(encoding="cp1252")
            entries = []
            if source.suffix.lower() == ".pls":
                indexed_entries = {}
                for line in text.splitlines():
                    key, separator, value = line.partition("=")
                    key = key.strip().lower()
                    index_text = key[4:] if key.startswith("file") else ""
                    if separator and index_text.isdigit():
                        indexed_entries[int(index_text)] = value.strip()
                entries = [value for _index, value in sorted(indexed_entries.items())]
            else:
                entries = [line.strip() for line in text.splitlines()
                           if line.strip() and not line.lstrip().startswith("#")]
            normalized = []
            for entry in entries:
                if "://" not in entry and not entry.lower().startswith("file:"):
                    candidate = Path(entry)
                    if not candidate.is_absolute():
                        candidate = source.parent / candidate
                    entry = str(candidate.resolve())
                if entry and entry not in normalized:
                    normalized.append(entry)
            if not normalized:
                QMessageBox.information(self, "Playlist vide", "Aucun média n’a été trouvé dans ce fichier.")
                return
        except (OSError, ValueError) as exc:
            QMessageBox.warning(self, "Import impossible", f"Le fichier n’a pas pu être lu : {exc}")
            return
        base = source.stem.strip() or "Playlist importée"
        name = base
        suffix = 2
        while name in self.window.playlists or name in self.window.smart_playlists:
            name = f"{base} ({suffix})"
            suffix += 1
        self.window.playlists[name] = normalized
        for entry in normalized:
            if entry not in self.window.library:
                self.window.library.append(entry)
        self.window.save_soon()
        self.refresh()
        self._show_playlist(name)

    def _export_playlist(self):
        if self.current_playlist in self.window.smart_playlists:
            paths = self.window.smart_playlist_tracks(self.current_playlist)
        else:
            paths = list(self.window.playlists.get(self.current_playlist, []))
        if not paths:
            QMessageBox.information(self, "Playlist vide", "Cette playlist ne contient aucun média à exporter.")
            return
        suggested = self.current_playlist
        target, selected_filter = QFileDialog.getSaveFileName(
            self, "Exporter la playlist", str(Path.home() / suggested),
            "Playlist M3U (*.m3u);;Playlist PLS (*.pls)",
        )
        if not target:
            return
        destination = Path(target)
        pls = "PLS" in selected_filter
        extension = ".pls" if pls else ".m3u"
        if destination.suffix.lower() not in (".m3u", ".m3u8", ".pls"):
            destination = destination.with_suffix(extension)
        else:
            pls = destination.suffix.lower() == ".pls"
        try:
            if destination.suffix.lower() == ".pls":
                lines = ["[playlist]"]
                for index, media in enumerate(paths, 1):
                    lines.extend((f"File{index}={media}",
                                  f"Title{index}={self.window.name_of(media)}",
                                  f"Length{index}=-1"))
                lines.extend((f"NumberOfEntries={len(paths)}", "Version=2"))
            else:
                lines = ["#EXTM3U"]
                for media in paths:
                    lines.extend((f"#EXTINF:-1,{self.window.name_of(media)}", str(media)))
            destination.write_text("\n".join(lines) + "\n", encoding="utf-8")
        except OSError as exc:
            QMessageBox.warning(self, "Export impossible", f"La playlist n’a pas pu être écrite : {exc}")
            return
        self.window.osd(f"Playlist exportée : {destination.name}")

    def _edit_selected_playlist(self):
        if self.selected_playlist:
            self._edit_playlist(self.selected_playlist)

    def _edit_playlist(self, original_name):
        creating = original_name is None
        dialog = QDialog(self)
        dialog.setWindowTitle("Nouvelle playlist" if creating else "Modifier la playlist")
        layout = QVBoxLayout(dialog)
        form = QFormLayout()
        name_edit = QLineEdit(original_name or "")
        name_edit.setPlaceholderText("Nom de la playlist")
        form.addRow("Nom", name_edit)
        layout.addLayout(form)

        images = self.window.cfg.get("playlist_images", {})
        existing_image = images.get(original_name, "") if isinstance(images, dict) and original_name else ""
        selected_image = [""]
        image_row = QHBoxLayout()
        image_label = QLabel(Path(existing_image).name if existing_image else "Aucune image")
        image_label.setObjectName("note")
        image_row.addWidget(image_label, 1)
        choose_image = QPushButton("Choisir une image…")
        def pick_image():
            path, _filter = QFileDialog.getOpenFileName(
                dialog, "Choisir une image de playlist", str(Path.home()),
                "Images (*.png *.jpg *.jpeg *.bmp *.webp)",
            )
            if path:
                selected_image[0] = path
                image_label.setText(Path(path).name)
        choose_image.clicked.connect(pick_image)
        image_row.addWidget(choose_image)
        layout.addLayout(image_row)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(dialog.accept)
        buttons.rejected.connect(dialog.reject)
        layout.addWidget(buttons)
        dialog.resize(440, 150)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return

        name = name_edit.text().strip()
        if not name:
            QMessageBox.warning(self, "Nom invalide", "Saisis un nom pour la playlist.")
            return
        if creating:
            if name in self.window.playlists or name in self.window.smart_playlists:
                QMessageBox.warning(self, "Playlist existante", "Une playlist porte déjà ce nom.")
                return
            self.window.playlists[name] = []
            self.window.save_soon()
        elif not self.window.rename_playlist(original_name, name):
            QMessageBox.warning(self, "Nom indisponible", "Ce nom est vide ou déjà utilisé.")
            return

        if selected_image[0] and not self.window.set_playlist_image(name, selected_image[0]):
            QMessageBox.warning(self, "Image indisponible", "L’image de playlist n’a pas pu être enregistrée.")
        self.refresh()
        if creating:
            self._show_playlist(name)

    def _open(self, item):
        self._show_playlist(item.data(Qt.ItemDataRole.UserRole))

    def _delete_selected_playlist(self):
        if self.selected_playlist:
            self._delete_playlist(self.selected_playlist)

    def _delete_current_playlist(self):
        if self.current_playlist:
            self._delete_playlist(self.current_playlist)

    def _delete_playlist(self, name):
        answer = QMessageBox.question(
            self, "Supprimer la playlist", f"Supprimer la playlist « {name} » ?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if answer != QMessageBox.StandardButton.Yes:
            return
        if name in self.window.smart_playlists:
            smart = self.window.cfg.get("smart_playlists", {})
            smart.pop(name, None)
            self.window.cfg.set("smart_playlists", smart)
        else:
            self.window.playlists.pop(name, None)
        images = self.window.cfg.get("playlist_images", {})
        if isinstance(images, dict) and name in images:
            images.pop(name, None)
            self.window.cfg.set("playlist_images", images)
        if self.current_playlist == name:
            self.current_playlist = None
            self.pages.setCurrentIndex(0)
        if self.window.active_playlist == name:
            self.window.set_active_playlist(None)
        self.window.save_soon()
        self.refresh()

    def _show_playlist(self, name):
        self.selected_playlist = name
        self.current_playlist = name
        self._current_is_smart = False
        self.edit_playlist_button.setEnabled(True)
        self.delete_playlist_button.setEnabled(True)
        self.detail_title.setText(name)
        self.edit_current_button.show()
        self.add_tracks_button.show()
        self.remove_tracks_button.show()
        self._refresh_tracks()
        self.pages.setCurrentIndex(1)

    def _show_smart_playlist(self, name):
        self.selected_playlist = name
        self.current_playlist = name
        self._current_is_smart = True
        marker = "smart" if self.window.cfg.get("language") == "en" else "intelligente"
        self.detail_title.setText(f"{name}  ·  {marker}")
        self.edit_current_button.hide()
        self.edit_playlist_button.setEnabled(False)
        self.delete_playlist_button.setEnabled(True)
        self.add_tracks_button.hide()
        self.remove_tracks_button.hide()
        self._refresh_tracks()
        self.pages.setCurrentIndex(1)

    def _refresh_tracks(self):
        self.tracks.clear()
        paths = (self.window.smart_playlist_tracks(self.current_playlist)
                 if self.current_playlist in self.window.smart_playlists
                 else self.window.playlists.get(self.current_playlist, []))
        for path in paths:
            item = QListWidgetItem(self.window.name_of(path))
            item.setData(Qt.ItemDataRole.UserRole, path)
            item.setToolTip(path)
            self.tracks.addItem(item)
        if self.current_playlist == self.window.active_playlist:
            self.window.refresh_playlist_sidebar()

    def _play_track(self, item):
        queue = (self.window.smart_playlist_tracks(self.current_playlist)
                 if self.current_playlist in self.window.smart_playlists
                 else list(self.window.playlists.get(self.current_playlist, [])))
        self.window.play_path(item.data(Qt.ItemDataRole.UserRole), queue=queue,
                              playlist_name=None if self.current_playlist in self.window.smart_playlists
                              else self.current_playlist)

    def _add_tracks(self):
        if not self.window.library:
            QMessageBox.information(self, "Bibliothèque vide", "Ajoute d’abord des fichiers à ta bibliothèque.")
            return
        dialog = QDialog(self)
        dialog.setWindowTitle("Ajouter des musiques à la playlist")
        layout = QVBoxLayout(dialog)
        choices = QListWidget()
        choices.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        for path in self.window.library:
            item = QListWidgetItem(self.window.name_of(path))
            item.setData(Qt.ItemDataRole.UserRole, path)
            item.setToolTip(path)
            choices.addItem(item)
        layout.addWidget(QLabel("Sélectionne un ou plusieurs médias de ta bibliothèque :"))
        layout.addWidget(choices)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(dialog.accept)
        buttons.rejected.connect(dialog.reject)
        layout.addWidget(buttons)
        dialog.resize(520, 460)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        playlist = self.window.playlists.setdefault(self.current_playlist, [])
        for item in choices.selectedItems():
            path = item.data(Qt.ItemDataRole.UserRole)
            if path not in playlist:
                playlist.append(path)
        self.window.save_soon()
        self._refresh_tracks()
        self.refresh()

    def _remove_tracks(self):
        selected = self.tracks.selectedItems()
        if not selected:
            return
        playlist = self.window.playlists.get(self.current_playlist, [])
        removed = {item.data(Qt.ItemDataRole.UserRole) for item in selected}
        self.window.playlists[self.current_playlist] = [path for path in playlist if path not in removed]
        self.window.save_soon()
        self._refresh_tracks()
        self.refresh()


class QueuePanel(QWidget):
    """File d’attente éditable et enregistrée avec la configuration du lecteur."""
    def __init__(self, window):
        super().__init__()
        self.window = window
        layout = QVBoxLayout(self)
        title = QLabel("File d’attente")
        title.setObjectName("title")
        layout.addWidget(title)
        layout.addWidget(QLabel("Choisis l’ordre de lecture. Double-clique sur un titre pour commencer."))
        self.list = QListWidget()
        self.list.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.list.itemDoubleClicked.connect(self._play)
        layout.addWidget(self.list, 1)
        actions = QHBoxLayout()
        add = QPushButton("Ajouter des médias…")
        add.clicked.connect(self._add)
        remove = QPushButton("Retirer")
        remove.clicked.connect(self._remove)
        up = QPushButton("Monter")
        up.clicked.connect(lambda: self._move(-1))
        down = QPushButton("Descendre")
        down.clicked.connect(lambda: self._move(1))
        clear = QPushButton("Vider la file")
        clear.clicked.connect(self._clear)
        for button in (add, remove, up, down, clear):
            actions.addWidget(button)
        layout.addLayout(actions)

    def refresh(self):
        self.list.clear()
        for path in self.window.queue:
            item = QListWidgetItem(self.window.name_of(path))
            item.setData(Qt.ItemDataRole.UserRole, path)
            item.setToolTip(path)
            self.list.addItem(item)

    def _save(self):
        self.window.cfg.set("queue", list(self.window.queue))
        self.window.save_soon()
        self.refresh()

    def _add(self):
        if not self.window.library:
            QMessageBox.information(self, "Bibliothèque vide", "Ajoute d’abord des médias à ta bibliothèque.")
            return
        dialog = QDialog(self)
        dialog.setWindowTitle("Ajouter à la file d’attente")
        layout = QVBoxLayout(dialog)
        choices = QListWidget()
        choices.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        for path in self.window.library:
            item = QListWidgetItem(self.window.name_of(path))
            item.setData(Qt.ItemDataRole.UserRole, path)
            item.setToolTip(path)
            choices.addItem(item)
        layout.addWidget(QLabel("Sélectionne un ou plusieurs médias :"))
        layout.addWidget(choices)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(dialog.accept)
        buttons.rejected.connect(dialog.reject)
        layout.addWidget(buttons)
        dialog.resize(520, 460)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            self.window.queue.extend(item.data(Qt.ItemDataRole.UserRole) for item in choices.selectedItems())
            self._save()

    def _play(self, item):
        path = item.data(Qt.ItemDataRole.UserRole)
        self.window.play_path(path, queue=list(self.window.queue))

    def _remove(self):
        rows = sorted((self.list.row(item) for item in self.list.selectedItems()), reverse=True)
        for row in rows:
            self.window.queue.pop(row)
        if rows:
            self._save()

    def _move(self, direction):
        rows = sorted(self.list.row(item) for item in self.list.selectedItems())
        if not rows:
            return
        queue = self.window.queue
        row = rows[0]
        target = row + direction
        if 0 <= target < len(queue):
            queue[row], queue[target] = queue[target], queue[row]
            self._save()
            self.list.setCurrentRow(target)

    def _clear(self):
        self.window.queue.clear()
        self._save()


class SettingsPanel(QWidget):
    def __init__(self, window):
        super().__init__()
        self.window = window
        layout = QVBoxLayout(self)
        title = QLabel("Paramètres")
        title.setObjectName("title")
        layout.addWidget(title)
        layout.addWidget(QLabel("Personnalise le lecteur et ses fonctions principales."))

        form = QFormLayout()
        layout.addLayout(form)
        self.language = QComboBox()
        self.language.addItem("Français", "fr")
        self.language.addItem("English", "en")
        self.language.currentIndexChanged.connect(self._set_language)
        form.addRow("Langue / Language", self.language)
        import version as _version
        update_row = QHBoxLayout()
        self.auto_update = QCheckBox("Vérifier au démarrage")
        self.auto_update.toggled.connect(self._set_auto_update)
        update_row.addWidget(self.auto_update)
        check_update = QPushButton("Rechercher maintenant")
        check_update.clicked.connect(lambda: self.window.check_updates(manual=True))
        update_row.addWidget(check_update)
        update_row.addStretch(1)
        form.addRow(f"Mises à jour (v{_version.__version__})", update_row)
        self.accent = QLineEdit()
        self.accent.setPlaceholderText("ex. #ff6b35")
        accent_row = QHBoxLayout()
        accent_row.addWidget(self.accent, 1)
        choose_accent = QPushButton("Choisir…")
        choose_accent.clicked.connect(self._choose_accent)
        accent_row.addWidget(choose_accent)
        apply_accent = QPushButton("Appliquer")
        apply_accent.clicked.connect(self._apply_accent)
        accent_row.addWidget(apply_accent)
        reset_accent = QPushButton("Par défaut")
        reset_accent.clicked.connect(self._reset_accent)
        accent_row.addWidget(reset_accent)
        form.addRow("Couleur d’accent", accent_row)

        self.elements = QLineEdit()
        self.elements.setPlaceholderText("ex. #20242b")
        elements_row = QHBoxLayout()
        elements_row.addWidget(self.elements, 1)
        choose_elements = QPushButton("Choisir…")
        choose_elements.clicked.connect(self._choose_elements)
        elements_row.addWidget(choose_elements)
        apply_elements = QPushButton("Appliquer")
        apply_elements.clicked.connect(self._apply_elements)
        elements_row.addWidget(apply_elements)
        reset_elements = QPushButton("Par défaut")
        reset_elements.clicked.connect(self._reset_elements)
        elements_row.addWidget(reset_elements)
        form.addRow("Couleur des éléments", elements_row)

        self.background = QLineEdit()
        self.background.setPlaceholderText("ex. #20242b")
        background_row = QHBoxLayout()
        background_row.addWidget(self.background, 1)
        choose_background = QPushButton("Choisir…")
        choose_background.clicked.connect(self._choose_background)
        background_row.addWidget(choose_background)
        apply_background = QPushButton("Appliquer")
        apply_background.clicked.connect(self._apply_background)
        background_row.addWidget(apply_background)
        reset_background = QPushButton("Par défaut")
        reset_background.clicked.connect(self._reset_background)
        background_row.addWidget(reset_background)
        form.addRow("Couleur du fond", background_row)

        self.background_mode = QComboBox()
        self.background_mode.addItem("Couleur", "color")
        self.background_mode.addItem("Image", "image")
        self.background_mode.addItem("Image floue", "blur")
        self.background_mode.currentIndexChanged.connect(self._set_background_mode)
        form.addRow("Type de fond", self.background_mode)
        image_row = QHBoxLayout()
        choose_image = QPushButton("Importer une image…")
        choose_image.clicked.connect(self._import_background_image)
        image_row.addWidget(choose_image)
        self.background_image_label = QLabel("Aucune image importée")
        self.background_image_label.setObjectName("note")
        self.background_image_label.setWordWrap(True)
        image_row.addWidget(self.background_image_label, 1)
        form.addRow("Image de fond", image_row)

        self.speed = QComboBox()
        for speed in SPEEDS:
            self.speed.addItem(f"{speed:g}×", speed)
        self.speed.currentIndexChanged.connect(self._set_speed)
        form.addRow("Vitesse de lecture", self.speed)

        self.repeat = QComboBox()
        for label, mode in (("Désactivée", "off"), ("Répéter ce titre", "one"), ("Répéter la liste", "all")):
            self.repeat.addItem(label, mode)
        self.repeat.currentIndexChanged.connect(self._set_repeat)
        form.addRow("Répétition", self.repeat)

        self.crossfade = QComboBox()
        self.crossfade.addItem("Désactivé", 0)
        for seconds in (2, 3, 5, 8, 10):
            self.crossfade.addItem(f"{seconds} secondes", seconds)
        self.crossfade.currentIndexChanged.connect(self._set_crossfade)
        form.addRow("Fondu entre les morceaux", self.crossfade)

        self.equalizer_enabled = QCheckBox("Activer l’égaliseur")
        self.equalizer_enabled.toggled.connect(self._set_equalizer_enabled)
        eq_row = QHBoxLayout()
        self.equalizer_preset = QComboBox()
        for label, preset in (("Plat", "flat"), ("Basses", "bass"), ("Aigus", "treble"),
                              ("Voix", "vocal"), ("Classique", "classical"), ("Personnalisé", "custom")):
            self.equalizer_preset.addItem(label, preset)
        self.equalizer_preset.currentIndexChanged.connect(self._set_equalizer_preset)
        eq_row.addWidget(self.equalizer_preset, 1)
        self.customize_eq_button = QPushButton("Personnaliser…")
        self.customize_eq_button.clicked.connect(self._customize_equalizer)
        eq_row.addWidget(self.customize_eq_button)
        form.addRow("Égaliseur", self.equalizer_enabled)
        form.addRow("Préréglage", eq_row)

        self.normalize_audio = QCheckBox("Égaliser le volume avec ReplayGain (si les tags sont présents)")
        self.normalize_audio.setToolTip("Le réglage est pris en compte à l’ouverture de la prochaine piste.")
        self.normalize_audio.toggled.connect(self._set_normalize_audio)
        form.addRow("Normalisation", self.normalize_audio)

        self.resume_playback = QCheckBox("Reprendre les morceaux à leur dernière position")
        self.resume_playback.toggled.connect(self._set_resume_playback)
        form.addRow("Reprise", self.resume_playback)

        sleep_row = QHBoxLayout()
        self.sleep_mode = QComboBox()
        self.sleep_mode.addItem("15 minutes", "15")
        self.sleep_mode.addItem("30 minutes", "30")
        self.sleep_mode.addItem("45 minutes", "45")
        self.sleep_mode.addItem("1 heure", "60")
        self.sleep_mode.addItem("À la fin du morceau en cours", "end")
        sleep_row.addWidget(self.sleep_mode, 1)
        self.sleep_button = QPushButton("Lancer le minuteur")
        self.sleep_button.clicked.connect(self._toggle_sleep_timer)
        sleep_row.addWidget(self.sleep_button)
        self.sleep_status = QLabel("")
        form.addRow("Minuteur de veille", sleep_row)
        form.addRow("État du minuteur", self.sleep_status)

        self.autoplay = QCheckBox("Passer automatiquement au média suivant")
        self.autoplay.toggled.connect(self._set_autoplay)
        form.addRow("Lecture", self.autoplay)
        self.lyrics = QCheckBox("Afficher les paroles pendant la lecture")
        self.lyrics.toggled.connect(self._set_lyrics)
        form.addRow("Paroles", self.lyrics)

        reset_row = QHBoxLayout()
        reset_row.addStretch(1)
        self.reset_app_button = QPushButton("Réinitialiser l’application…")
        self.reset_app_button.setObjectName("danger")
        self.reset_app_button.clicked.connect(self._reset_application)
        reset_row.addWidget(self.reset_app_button)
        layout.addLayout(reset_row)

        layout.addStretch(1)
        self.refresh()

    def _reset_application(self):
        answer = QMessageBox.warning(
            self, "Réinitialiser l’application",
            "Cette action effacera tous les espaces utilisateurs, les bibliothèques, "
            "les playlists et les réglages enregistrés, puis recréera l’espace Principal. "
            "Les fichiers audio et vidéo présents sur ton appareil ne seront pas supprimés.\n\n"
            "Continuer ?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if answer == QMessageBox.StandardButton.Yes:
            self.window.reset_application()

    def _set_auto_update(self, checked):
        self.window.cfg.set("auto_update", bool(checked))
        self.window.cfg.save()

    def refresh(self):
        cfg = self.window.cfg
        blockers = [QSignalBlocker(widget) for widget in
                    (self.auto_update, self.speed, self.repeat, self.crossfade, self.autoplay, self.lyrics,
                     self.equalizer_enabled, self.equalizer_preset, self.normalize_audio,
                     self.resume_playback,
                     self.background_mode, self.language)]
        self.language.setCurrentIndex(max(0, self.language.findData(cfg.get("language", "fr"))))
        self.auto_update.setChecked(bool(cfg.get("auto_update", True)))
        self.accent.setText(str(cfg.get("accent", "#ff6b35")))
        self.elements.setText(str(cfg.get("element_color", theme.PALETTE["panel"])))
        self.background.setText(str(cfg.get("background", theme.PALETTE["bg"])))
        self.background_mode.setCurrentIndex(max(0, self.background_mode.findData(cfg.get("background_mode", "color"))))
        image_path = cfg.get("background_image", "")
        self.background_image_label.setText(Path(image_path).name if image_path else "Aucune image importée")
        self.speed.setCurrentIndex(max(0, self.speed.findData(cfg.get("playback_rate", 1.0))))
        self.repeat.setCurrentIndex(max(0, self.repeat.findData(cfg.get("repeat_mode", "off"))))
        self.crossfade.setCurrentIndex(max(0, self.crossfade.findData(int(cfg.get("crossfade_seconds", 0) or 0))))
        self.equalizer_enabled.setChecked(bool(cfg.get("equalizer_enabled", False)))
        preset = cfg.get("equalizer_preset", "flat")
        self.equalizer_preset.setCurrentIndex(max(0, self.equalizer_preset.findData(preset)))
        self.normalize_audio.setChecked(bool(cfg.get("normalize_audio", False)))
        self.resume_playback.setChecked(bool(cfg.get("resume_playback", True)))
        self.autoplay.setChecked(bool(cfg.get("autoplay_next", True)))
        self.lyrics.setChecked(bool(cfg.get("show_lyrics", False)))
        self.update_sleep_status()

    def update_sleep_status(self, text=None):
        if text is not None:
            self.sleep_status.setText(text)
        elif self.window._sleep_deadline is not None or self.window._sleep_end_track is not None:
            self.sleep_status.setText("Minuteur actif")
            self.sleep_button.setText("Annuler le minuteur")
        else:
            self.sleep_status.setText("Aucun minuteur actif")
            self.sleep_button.setText("Lancer le minuteur")

    def _toggle_sleep_timer(self):
        if self.window._sleep_deadline is not None or self.window._sleep_end_track is not None:
            self.window.cancel_sleep_timer()
        else:
            self.window.start_sleep_timer(self.sleep_mode.currentData())
        self.update_sleep_status()

    def _set_equalizer_enabled(self, enabled):
        self.window.cfg.set("equalizer_enabled", bool(enabled))
        applied = self.window.apply_equalizer()
        if enabled and not applied and self.window.backend.available:
            QMessageBox.warning(self, "Égaliseur indisponible",
                                "Cette version de VLC ne permet pas d’activer l’égaliseur.")
            blocker = QSignalBlocker(self.equalizer_enabled)
            self.equalizer_enabled.setChecked(False)
            del blocker
            self.window.cfg.set("equalizer_enabled", False)
        self.window.save_soon()

    def _set_equalizer_preset(self, _index):
        preset = self.equalizer_preset.currentData()
        if preset in EQ_PRESETS:
            self.window.cfg.set("equalizer_preset", preset)
            self.window.cfg.set("equalizer_bands", EQ_PRESETS[preset])
            self.window.cfg.set("equalizer_preamp", 0.0)
            self.window.apply_equalizer()
            self.window.save_soon()

    def _customize_equalizer(self):
        dialog = EqualizerDialog(self.window.cfg.get("equalizer_bands", [0] * 10),
                                 self.window.cfg.get("equalizer_preamp", 0.0), self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            bands, preamp = dialog.values()
            self.window.cfg.set("equalizer_bands", bands)
            self.window.cfg.set("equalizer_preamp", preamp)
            self.window.cfg.set("equalizer_preset", "custom")
            self.equalizer_preset.setCurrentIndex(self.equalizer_preset.findData("custom"))
            self.equalizer_enabled.setChecked(True)
            self.window.apply_equalizer()
            self.window.save_soon()

    def _set_normalize_audio(self, enabled):
        self.window.cfg.set("normalize_audio", bool(enabled))
        self.window.backend.set_normalize_audio(enabled)
        self.window.save_soon()

    def _set_resume_playback(self, enabled):
        self.window.cfg.set("resume_playback", bool(enabled))
        self.window.save_soon()

    def _apply_accent(self):
        color = QColor(self.accent.text().strip())
        if not color.isValid():
            QMessageBox.warning(self, "Couleur invalide", "Entre une couleur valide, par exemple #ff6b35.")
            return
        self.window.set_accent(color.name())

    def _choose_accent(self):
        initial = QColor(self.accent.text().strip())
        if not initial.isValid():
            initial = QColor(theme.ACCENT)
        color = QColorDialog.getColor(initial, self, "Choisir la couleur d’accentuation")
        if color.isValid():
            self.accent.setText(color.name())
            self.window.set_accent(color.name())

    def _reset_accent(self):
        self.accent.setText(theme.ACCENT)
        self.window.set_accent(theme.ACCENT)

    def _choose_elements(self):
        initial = QColor(self.elements.text().strip())
        if not initial.isValid():
            initial = QColor(theme.PALETTE["panel"])
        color = QColorDialog.getColor(initial, self, "Choisir la couleur des éléments")
        if color.isValid():
            self.elements.setText(color.name())
            self.window.set_element_color(color.name())

    def _apply_elements(self):
        color = QColor(self.elements.text().strip())
        if not color.isValid():
            QMessageBox.warning(self, "Couleur invalide", "Entre une couleur valide, par exemple #20242b.")
            return
        self.window.set_element_color(color.name())

    def _reset_elements(self):
        color = theme.PALETTE["panel"]
        self.elements.setText(color)
        self.window.set_element_color(color)

    def _choose_background(self):
        initial = QColor(self.background.text().strip())
        if not initial.isValid():
            initial = QColor(theme.PALETTE["bg"])
        color = QColorDialog.getColor(initial, self, "Choisir la couleur du fond")
        if color.isValid():
            self.background.setText(color.name())
            self.background_mode.setCurrentIndex(self.background_mode.findData("color"))
            self.window.set_background(color.name())

    def _apply_background(self):
        color = QColor(self.background.text().strip())
        if not color.isValid():
            QMessageBox.warning(self, "Couleur invalide", "Entre une couleur valide, par exemple #20242b.")
            return
        self.background_mode.setCurrentIndex(self.background_mode.findData("color"))
        self.window.set_background(color.name())

    def _reset_background(self):
        color = theme.PALETTE["bg"]
        self.background.setText(color)
        self.background_mode.setCurrentIndex(self.background_mode.findData("color"))
        self.window.set_background(color)

    def _set_background_mode(self, _index):
        mode = self.background_mode.currentData()
        if mode in ("image", "blur"):
            key = "background_blurred_image" if mode == "blur" else "background_image"
            image_path = self.window.cfg.get(key, "")
            if not image_path or not Path(image_path).is_file():
                QMessageBox.information(self, "Image manquante", "Importe d’abord une image de fond.")
                blocker = QSignalBlocker(self.background_mode)
                self.background_mode.setCurrentIndex(self.background_mode.findData("color"))
                del blocker
                return
        self.window.set_background_mode(mode)

    def _import_background_image(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Choisir une image de fond", str(Path.home()),
            "Images (*.png *.jpg *.jpeg *.bmp *.webp)",
        )
        if not path:
            return
        source = Path(path)
        target_dir = self.window.cfg.profile_root / self.window.cfg.active_profile / "backgrounds"
        try:
            target_dir.mkdir(parents=True, exist_ok=True)
            original = target_dir / ("background" + source.suffix.lower())
            shutil.copy2(source, original)
            blurred = target_dir / "background_blurred.png"
            pixmap = QPixmap(str(original))
            if pixmap.isNull():
                raise ValueError("Le fichier image ne peut pas être lu.")
            target_size = QSize(1920, 1080)
            scaled = pixmap.scaled(target_size, Qt.AspectRatioMode.KeepAspectRatioByExpanding,
                                   Qt.TransformationMode.SmoothTransformation)
            x = max(0, (scaled.width() - target_size.width()) // 2)
            y = max(0, (scaled.height() - target_size.height()) // 2)
            pixmap = scaled.copy(x, y, target_size.width(), target_size.height())
            scene = QGraphicsScene()
            item = QGraphicsPixmapItem(pixmap)
            effect = QGraphicsBlurEffect()
            effect.setBlurRadius(34)
            item.setGraphicsEffect(effect)
            scene.addItem(item)
            scene.setSceneRect(QRectF(pixmap.rect()))
            image = QImage(pixmap.size(), QImage.Format.Format_ARGB32_Premultiplied)
            image.fill(Qt.GlobalColor.transparent)
            painter = QPainter(image)
            scene.render(painter, QRectF(image.rect()), QRectF(pixmap.rect()))
            painter.end()
            if not image.save(str(blurred)):
                raise OSError("Impossible d’enregistrer la version floue.")
        except (OSError, ValueError) as exc:
            QMessageBox.warning(self, "Import de l’image", f"Impossible d’importer cette image : {exc}")
            return
        self.window.cfg.set("background_image", str(original))
        self.window.cfg.set("background_blurred_image", str(blurred))
        self.background_image_label.setText(original.name)
        self.background_mode.setCurrentIndex(self.background_mode.findData("image"))
        self.window.set_background_mode("image")

    def _set_speed(self, _index):
        speed = self.speed.currentData()
        if speed is not None:
            self.window.set_rate(float(speed))

    def _set_repeat(self, _index):
        mode = self.repeat.currentData()
        if mode:
            self.window.set_repeat_mode(mode)

    def _set_crossfade(self, _index):
        seconds = self.crossfade.currentData()
        if seconds is not None:
            self.window.cfg.set("crossfade_seconds", int(seconds))
            self.window.save_soon()

    def _set_autoplay(self, enabled):
        self.window.cfg.set("autoplay_next", bool(enabled))
        self.window.save_soon()

    def _set_lyrics(self, enabled):
        self.window.set_lyrics_visible(bool(enabled))

    def _set_language(self, _index):
        language = self.language.currentData()
        if language:
            self.window.set_language(language)


class UserPanel(QWidget):
    """Gestion des espaces utilisateurs locaux de l'application."""
    def __init__(self, window):
        super().__init__()
        self.window = window
        layout = QVBoxLayout(self)
        layout.setSpacing(14)
        title = QLabel("Espaces utilisateurs")
        title.setObjectName("title")
        layout.addWidget(title)
        description = QLabel(
            "Qui écoute aujourd’hui ? Chaque profil garde sa bibliothèque, ses playlists et ses réglages."
        )
        description.setWordWrap(True)
        layout.addWidget(description)

        self.cards_host = QWidget()
        self.cards_grid = QGridLayout(self.cards_host)
        self.cards_grid.setContentsMargins(0, 8, 0, 0)
        self.cards_grid.setHorizontalSpacing(16)
        self.cards_grid.setVerticalSpacing(16)
        layout.addWidget(self.cards_host, 0, Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop)

        actions = QHBoxLayout()
        self.active_label = QLabel("")
        self.active_label.setObjectName("note")
        actions.addWidget(self.active_label, 1)
        self.edit_profile_button = QPushButton("Modifier le profil…")
        self.edit_profile_button.clicked.connect(self._edit_profile)
        actions.addWidget(self.edit_profile_button)
        self.delete_button = QPushButton("Supprimer l’espace sélectionné")
        self.delete_button.clicked.connect(self._delete_profile)
        actions.addWidget(self.delete_button)
        layout.addLayout(actions)
        layout.addStretch(1)
        self.refresh()

    def refresh(self):
        previous_group = getattr(self, "_profile_button_group", None)
        if previous_group is not None:
            for old_button in previous_group.buttons():
                previous_group.removeButton(old_button)

        while self.cards_grid.count():
            item = self.cards_grid.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()

        profiles = list(self.window.cfg.profiles)
        active_id = self.window.cfg.active_profile
        active = next((p for p in profiles if p["id"] == active_id), profiles[0])
        self._profile_button_group = previous_group or QButtonGroup(self)
        self._profile_button_group.setExclusive(True)
        self.active_label.setText(f"Profil actif : {active['name']}")
        self.delete_button.setEnabled(active_id != "principal")
        self.delete_button.setToolTip(
            "L’espace Principal ne peut pas être supprimé." if active_id == "principal" else ""
        )

        for index, profile in enumerate(profiles):
            card = QToolButton()
            card.setObjectName("profileCard")
            card.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextUnderIcon)
            card.setText(profile["name"] + ("\nEn cours" if profile["id"] == active_id else ""))
            card.setIcon(QIcon(self._avatar(profile["name"], profile["id"], profile.get("image", ""))))
            card.setIconSize(QSize(104, 104))
            card.setFixedSize(156, 166)
            card.setCheckable(True)
            card.setChecked(profile["id"] == active_id)
            self._profile_button_group.addButton(card)
            card.setToolTip(f"Ouvrir l’espace {profile['name']}")
            card.clicked.connect(lambda _checked=False, pid=profile["id"]: self._switch_profile(pid))
            self.cards_grid.addWidget(card, index // 4, index % 4)

        create = QToolButton()
        create.setObjectName("profileCard")
        create.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextUnderIcon)
        create.setText("Créer un espace")
        create.setIcon(QIcon(self._create_avatar()))
        create.setIconSize(QSize(104, 104))
        create.setFixedSize(156, 166)
        create.setToolTip("Créer un nouvel espace utilisateur")
        create.clicked.connect(self._create_profile)
        index = len(profiles)
        self.cards_grid.addWidget(create, index // 4, index % 4)

    @staticmethod
    def _avatar(name, profile_id, image_path=""):
        if image_path and Path(image_path).is_file():
            source = QPixmap(image_path)
            if not source.isNull():
                side = min(source.width(), source.height())
                x = (source.width() - side) // 2
                y = (source.height() - side) // 2
                return source.copy(x, y, side, side).scaled(
                    112, 112, Qt.AspectRatioMode.IgnoreAspectRatio,
                    Qt.TransformationMode.SmoothTransformation,
                )
        colors = ("#e85d75", "#8b78e6", "#319c91", "#d79b3d", "#548bd0", "#d66c45")
        color = QColor(colors[sum(map(ord, profile_id)) % len(colors)])
        pixmap = QPixmap(112, 112)
        pixmap.fill(Qt.GlobalColor.transparent)
        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setBrush(color)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawRoundedRect(4, 4, 104, 104, 22, 22)
        painter.setPen(Qt.GlobalColor.white)
        painter.drawText(pixmap.rect(), Qt.AlignmentFlag.AlignCenter, (name.strip()[:1] or "?").upper())
        painter.end()
        return pixmap

    @staticmethod
    def _create_avatar():
        pixmap = QPixmap(112, 112)
        pixmap.fill(Qt.GlobalColor.transparent)
        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setBrush(QColor("#292a30"))
        painter.setPen(QColor("#686a73"))
        painter.drawRoundedRect(4, 4, 104, 104, 22, 22)
        painter.setPen(QColor("#e4e4e7"))
        painter.drawText(pixmap.rect(), Qt.AlignmentFlag.AlignCenter, "+")
        painter.end()
        return pixmap

    def _switch_profile(self, profile_id):
        if profile_id and profile_id != self.window.cfg.active_profile:
            self.window.switch_profile(profile_id)

    def _edit_profile(self):
        profile_id = self.window.cfg.active_profile
        profile = next((p for p in self.window.cfg.profiles if p["id"] == profile_id), None)
        if profile is None:
            return
        dialog = QDialog(self)
        dialog.setWindowTitle("Modifier le profil")
        layout = QVBoxLayout(dialog)
        form = QFormLayout()
        name_edit = QLineEdit(profile["name"])
        form.addRow("Nom du profil", name_edit)
        layout.addLayout(form)

        selected_image = [""]
        image_row = QHBoxLayout()
        image_label = QLabel(
            Path(profile["image"]).name if profile.get("image") else "Avatar coloré par défaut"
        )
        image_label.setObjectName("note")
        image_row.addWidget(image_label, 1)
        choose_image = QPushButton("Choisir une image…")
        def pick_image():
            path, _filter = QFileDialog.getOpenFileName(
                dialog, "Choisir une image de profil", str(Path.home()),
                "Images (*.png *.jpg *.jpeg *.bmp *.webp)",
            )
            if path:
                selected_image[0] = path
                image_label.setText(Path(path).name)
        choose_image.clicked.connect(pick_image)
        image_row.addWidget(choose_image)
        layout.addLayout(image_row)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(dialog.accept)
        buttons.rejected.connect(dialog.reject)
        layout.addWidget(buttons)
        dialog.resize(440, 150)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        name = name_edit.text().strip()
        if not name or not self.window.rename_profile(profile_id, name):
            QMessageBox.warning(self, "Nom indisponible", "Ce nom est vide ou déjà utilisé.")
            return
        if selected_image[0] and not self.window.set_profile_image(profile_id, selected_image[0]):
            QMessageBox.warning(self, "Image indisponible", "L’image de profil n’a pas pu être enregistrée.")
        self.refresh()

    def _create_profile(self):
        from PySide6.QtWidgets import QInputDialog
        name, accepted = QInputDialog.getText(self, "Créer un espace utilisateur", "Nom de l’espace :")
        if accepted and name.strip():
            self.window.create_profile(name.strip())

    def _delete_profile(self):
        profile_id = self.window.cfg.active_profile
        if not profile_id or profile_id == "principal":
            return
        name = next((p["name"] for p in self.window.cfg.profiles if p["id"] == profile_id), "")
        answer = QMessageBox.question(
            self, "Supprimer l’espace utilisateur",
            f"Supprimer « {name} » et ses bibliothèques, playlists et préférences ? Cette action est définitive.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if answer == QMessageBox.StandardButton.Yes:
            self.window.delete_profile(profile_id)

