"""Fenêtres d'aide et de premier démarrage."""
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QLabel, QDialogButtonBox, QPushButton,
    QColorDialog, QHBoxLayout, QTextBrowser,
)
from PySide6.QtGui import QColor
from animated_controls import AnimatedPushButton as QPushButton

class HelpDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        english = bool(parent and getattr(parent, "cfg", None) and parent.cfg.get("language", "fr") == "en")
        self.setWindowTitle("VLC Redesign Guide" if english else "Guide de VLC Redesign")
        self.resize(720, 680)
        self.setMinimumSize(580, 500)
        layout = QVBoxLayout(self)
        title = QLabel("VLC Redesign Guide" if english else "Guide de VLC Redesign")
        title.setObjectName("title")
        layout.addWidget(title)

        colors = parent.colors() if parent and hasattr(parent, "colors") else {
            "text": "#e4e4e7", "dim": "#a0a0a8", "accent": "#ff6b35",
            "panel": "#171718", "border": "#343438",
        }
        browser = QTextBrowser()
        browser.setObjectName("helpText")
        browser.setOpenExternalLinks(False)
        browser.setStyleSheet(
            f"QTextBrowser#helpText {{ background: {colors['panel']}; color: {colors['text']}; "
            f"border: 1px solid {colors['border']}; border-radius: 10px; padding: 12px; }}"
        )
        browser.document().setDefaultStyleSheet(
            f"body {{ color: {colors['text']}; font-family: 'Segoe UI'; font-size: 14px; }}"
            f"h2 {{ color: {colors['accent']}; font-size: 17px; margin-top: 18px; }}"
            f"h3 {{ color: {colors['text']}; font-size: 15px; margin-top: 12px; }}"
            f"p, li {{ color: {colors['text']}; line-height: 1.4; }}"
            f".note {{ color: {colors['dim']}; }}"
        )
        if english:
            browser.setHtml("""
            <h2>Getting around</h2>
            <p>The sidebar opens Home, Videos, Music, Network, YouTube, Downloads, Playlists, Queue, and Recent items.
            Use the button at its top to collapse or expand it. Add media from the <b>…</b> menu or drag files into the library.
            Double-click an item to play it.</p>
            <h2>User profiles</h2>
            <p>Open <b>User</b> to select a profile tile or create a separate profile. Each profile keeps its own library,
            playlists, and settings. Edit a profile to change its name or picture. The Main profile cannot be deleted.</p>
            <h2>Playlists and artwork</h2>
            <p>Open a playlist tile to view and play its tracks. Add or remove tracks from the playlist page. Use
            <b>Rename / artwork…</b> to change its name or cover image.</p>
            <p>Create a <b>Smart playlist</b> to filter your library by artist, genre, or favorites. Import and export
            regular playlists in M3U or PLS format.</p>
            <h2>Queue</h2>
            <p>Add tracks to the queue from a media menu. Open <b>Queue</b> to review and reorder upcoming items.</p>
            <h2>Playback and sound</h2>
            <p>In <b>Settings</b>, configure a sleep timer, resume tracks from their last position, and adjust the
            10-band equalizer with presets or custom sliders. ReplayGain normalization works when the audio files
            contain ReplayGain tags. Crossfade overlaps audio tracks.</p>
            <h2>Appearance</h2>
            <ul><li><b>Accent color:</b> buttons, icons, and active states.</li>
            <li><b>Interface color:</b> panels such as the sidebar and playlists.</li>
            <li><b>Background color:</b> the page area behind those panels.</li></ul>
            <p>Choose a solid color, an image, or a blurred image as the background.</p>
            <h2>YouTube and downloads</h2>
            <p>Search and play videos on the <b>YouTube</b> page. On <b>Download</b>, paste a link, choose video or audio
            format and the tracks you need, then select a destination folder. Only download content you are authorized to use.</p>
            <h2>Resetting the app</h2>
            <p>In <b>Settings</b>, choose <b>Reset application…</b> to clear profiles, libraries, playlists, and saved settings.
            The app asks for confirmation first. Audio and video files in your folders are not deleted.</p>
            """)
        else:
            browser.setHtml("""
            <h2>Se repérer</h2>
            <p>La barre latérale donne accès à l’accueil, aux vidéos, à la musique, aux sources réseau,
            à YouTube, aux téléchargements, aux playlists, à la file d’attente et aux éléments récents.
            Le bouton en haut de la barre permet de la replier ou de la déplier.</p>
            <p>Ajoute des médias avec le menu <b>…</b> ou glisse-dépose des fichiers dans la bibliothèque.
            Double-clique sur un média pour le lire.</p>

            <h2>Profils utilisateur</h2>
            <p>Ouvre <b>Utilisateur</b> pour choisir un profil dans les tuiles, comme sur un service de vidéo.
            La tuile <b>Créer un espace</b> ajoute un profil séparé avec sa propre bibliothèque, ses playlists
            et ses réglages.</p>
            <p>Le bouton <b>Modifier le profil…</b> permet de changer son nom et d’importer une image.
            Le profil Principal ne peut pas être supprimé ; les autres se suppriment depuis cette page.</p>

            <h2>Playlists et images</h2>
            <p>Dans <b>Playlists</b>, sélectionne une tuile pour ouvrir son contenu. Tu peux y ajouter plusieurs
            titres de ta bibliothèque, les retirer, puis lancer directement un titre.</p>
            <p><b>Renommer / image…</b> permet de changer le nom et d’ajouter une couverture à une playlist.
            Les images sont conservées avec le profil utilisateur correspondant.</p>
            <p>Crée une <b>playlist intelligente</b> pour filtrer automatiquement ta bibliothèque par artiste, genre ou favoris.
            Les playlists classiques peuvent être importées ou exportées aux formats M3U et PLS.</p>

            <h2>File d’attente</h2>
            <p>Ajoute des titres à la file depuis leur menu ou depuis la bibliothèque. La page
            <b>File d’attente</b> permet de consulter et réorganiser les prochains médias.</p>

            <h2>Lecture et son</h2>
            <p>Dans <b>Paramètres</b>, règle un minuteur de veille, reprends un média à sa dernière position et règle
            l’égaliseur à 10 bandes avec des préréglages ou les curseurs personnalisés. ReplayGain égalise le volume
            lorsque les fichiers contiennent ces tags. Le fondu enchaîne les pistes audio en les faisant se chevaucher.</p>

            <h2>Personnaliser l’apparence</h2>
            <ul>
              <li><b>Couleur d’accent</b> : boutons, icônes et éléments actifs.</li>
              <li><b>Couleur des éléments</b> : panneaux d’interface, comme la barre latérale et les playlists.</li>
              <li><b>Couleur du fond</b> : zone de page située derrière les panneaux.</li>
            </ul>
            <p>Dans <b>Type de fond</b>, choisis une couleur, une image ou une image floutée. Les images importées
            restent disponibles dans le profil qui les a ajoutées.</p>

            <h2>YouTube et téléchargements</h2>
            <p>La page <b>YouTube</b> sert à rechercher et lire des vidéos. Dans <b>Télécharger</b>, colle une adresse,
            choisis le format vidéo ou audio et les pistes souhaitées, puis sélectionne le dossier de destination.
            Utilise ces fonctions uniquement pour les contenus que tu es autorisé à télécharger.</p>

            <h2>Réinitialiser l’application</h2>
            <p>Dans <b>Paramètres</b>, le bouton <b>Réinitialiser l’application…</b> remet les réglages à zéro et efface
            les profils, bibliothèques et playlists enregistrés. Une confirmation est demandée avant l’opération.
            Les fichiers audio et vidéo présents dans tes dossiers ne sont pas supprimés.</p>
            """)
        layout.addWidget(browser, 1)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        buttons.rejected.connect(self.reject)
        buttons.accepted.connect(self.accept)
        layout.addWidget(buttons)

class WizardDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.window = parent
        english = bool(parent and getattr(parent, "cfg", None) and parent.cfg.get("language", "fr") == "en")
        self.setWindowTitle("Welcome to VLC Redesign" if english else "Bienvenue dans VLC Redesign")
        self.resize(580, 500)
        self.setMinimumSize(520, 440)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 22, 24, 20)
        layout.setSpacing(14)

        title = QLabel("Welcome to VLC Redesign" if english else "Bienvenue dans VLC Redesign")
        title.setObjectName("title")
        layout.addWidget(title)
        intro = QLabel("Your music and video space, customizable for everyone at home." if english else
                       "Ton espace musique et vidéo, personnalisable pour chaque personne de la maison.")
        intro.setWordWrap(True)
        layout.addWidget(intro)

        features = QLabel(
            ("<b>Profiles with avatars</b> to keep libraries separate · "
             "<b>Tiled playlists</b> with their own covers · "
             "<b>Custom colors and backgrounds</b> · "
             "<b>Queue</b> for upcoming tracks." if english else
             "<b>Profils avec avatar</b> pour séparer les bibliothèques · "
             "<b>Playlists en tuiles</b> avec leurs propres couvertures · "
             "<b>Couleurs et fonds personnalisables</b> · "
             "<b>File d’attente</b> pour choisir les prochains titres.")
        )
        features.setWordWrap(True)
        features.setObjectName("note")
        layout.addWidget(features)

        color_title = QLabel("Choose your accent color" if english else "Choisis ta couleur d’accent")
        color_title.setObjectName("sectionTitle")
        layout.addWidget(color_title)
        self.color_button = QPushButton("Choose a color…" if english else "Choisir une couleur…")
        self.color_button.clicked.connect(self._choose_color)
        layout.addWidget(self.color_button)

        guide_row = QHBoxLayout()
        guide = QPushButton("Explore the guide and what’s new" if english else "Découvrir le guide et les nouveautés")
        guide.clicked.connect(self._open_guide)
        guide_row.addWidget(guide)
        guide_row.addStretch(1)
        layout.addLayout(guide_row)

        note = QLabel(
            ("VLC Media Player must be installed to play media. If it is not detected, install it and restart VLC Redesign."
             if english else "Pour lire les médias, VLC Media Player doit être installé. "
             "S’il n’est pas détecté, installe-le puis redémarre VLC Redesign.")
        )
        note.setWordWrap(True)
        note.setObjectName("note")
        layout.addWidget(note)

        layout.addStretch(1)
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def _choose_color(self):
        initial = QColor(self.window.cfg.get("accent")) if self.window else QColor()
        title = "Choose accent color" if self.window and self.window.cfg.get("language", "fr") == "en" else "Choisir la couleur d’accent"
        color = QColorDialog.getColor(initial, self, title)
        if color.isValid() and self.window:
            self.window.cfg.set("accent", color.name())
            self.window.apply_theme()

    def _open_guide(self):
        HelpDialog(self.window or self).exec()
