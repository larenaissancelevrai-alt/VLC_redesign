"""Small runtime French/English UI translator for VLC Redesign."""
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QLineEdit, QWidget


EN = {
    "Français": "French", "Langue / Language": "Language",
    "Accueil": "Home", "Vidéos": "Videos", "Vidéo": "Video", "Musique": "Music",
    "Réseau": "Network", "Découvrir": "Discover", "Télécharger": "Download",
    "Playlists": "Playlists", "File d’attente": "Queue", "Récents": "Recent",
    "Paramètres…": "Settings…", "Paramètres...": "Settings…", "Utilisateur": "User",
    "VLC Redesign": "VLC Redesign", "Aucun média en cours": "Nothing is playing",
    "En cours": "Now playing",
    "Profil actif : ": "Active profile: ",
    "Choisis l’ordre de lecture. Double-clique sur un titre pour commencer.":
        "Choose the playback order. Double-click a track to start playing.",
    "Réduire la barre latérale": "Collapse sidebar",
    "Déplier la barre latérale": "Expand sidebar",
    "Lire un flux audio/vidéo à partir d'une adresse réseau (URL)": "Play audio or video from a network address (URL)",
    "Rechercher et écouter des vidéos sur YouTube": "Search and play videos on YouTube",
    "Espaces utilisateurs": "User profiles",
    "Guide de VLC Redesign": "VLC Redesign Guide",
    "Bienvenue dans VLC Redesign": "Welcome to VLC Redesign",
    "Ton espace musique et vidéo, personnalisable pour chaque personne de la maison.":
        "Your music and video space, customizable for everyone at home.",
    "Profils avec avatar": "Profiles with avatars",
    " pour séparer les bibliothèques · Playlists en tuiles avec leurs propres couvertures · Couleurs et fonds personnalisables · File d’attente pour choisir les prochains titres.":
        " to keep libraries separate · Tiled playlists with their own artwork · Custom colors and backgrounds · A queue for upcoming tracks.",
    "Choisis ta couleur d’accent": "Choose your accent color",
    "Choisir une couleur…": "Choose a color…", "Choisir une couleur...": "Choose a color...",
    "Découvrir le guide et les nouveautés": "Explore the guide and what’s new",
    "Pour lire les médias, VLC Media Player doit être installé. S’il n’est pas détecté, installe-le puis redémarre VLC Redesign.":
        "VLC Media Player must be installed to play media. If it is not detected, install it and restart VLC Redesign.",
    "Rechercher": "Search", "Ajouter": "Add", "Annuler": "Cancel", "Enregistrer": "Save",
    "Favoris": "Favorites", "Fondu entre les morceaux": "Crossfade between tracks",
    "Égaliseur": "Equalizer", "Égaliseur personnalisé": "Custom equalizer",
    "Activer l’égaliseur": "Enable equalizer", "Préréglage": "Preset",
    "Personnaliser…": "Customize…", "Plat": "Flat", "Basses": "Bass",
    "Aigus": "Treble", "Voix": "Voice", "Classique": "Classical",
    "Préamplification": "Preamp", "Normalisation": "Normalization",
    "Égaliser le volume avec ReplayGain (si les tags sont présents)":
        "Normalize volume with ReplayGain (when tags are present)",
    "Le réglage est pris en compte à l’ouverture de la prochaine piste.":
        "This setting takes effect when the next track is opened.",
    "Reprise": "Resume", "Reprendre les morceaux à leur dernière position":
        "Resume tracks from their last position",
    "Minuteur de veille": "Sleep timer", "État du minuteur": "Timer status",
    "Lancer le minuteur": "Start timer", "Annuler le minuteur": "Cancel timer",
    "15 minutes": "15 minutes", "30 minutes": "30 minutes", "45 minutes": "45 minutes",
    "1 heure": "1 hour", "À la fin du morceau en cours": "At the end of the current track",
    "Aucun minuteur actif": "No timer active", "Minuteur actif": "Timer active",
    "Playlist intelligente…": "Smart playlist…", "Importer M3U / PLS…": "Import M3U / PLS…",
    "Exporter M3U / PLS…": "Export M3U / PLS…",
    "Nouvelle playlist intelligente": "New smart playlist", "Filtre facultatif": "Optional filter",
    "Limiter aux favoris": "Favorites only",
    "La liste se met à jour automatiquement depuis ta bibliothèque.":
        "This list updates automatically from your library.",
    "Artiste contient": "Artist contains", "Genre contient": "Genre contains",
    "Minuteur de veille activé.": "Sleep timer started.",
    "Minuteur terminé : lecture arrêtée.": "Timer finished: playback stopped.",
    "Fin du morceau : lecture arrêtée.": "Track finished: playback stopped.",
    "Lance un morceau avant de choisir la fin du morceau.":
        "Start a track before choosing the end-of-track timer.",
    "Égaliseur indisponible": "Equalizer unavailable",
    "Cette version de VLC ne permet pas d’activer l’égaliseur.":
        "This version of VLC does not support the equalizer.",
    "2 secondes": "2 seconds", "3 secondes": "3 seconds", "5 secondes": "5 seconds",
    "8 secondes": "8 seconds", "10 secondes": "10 seconds",
    "Ajouter aux favoris": "Add to favorites", "Retirer des favoris": "Remove from favorites",
    "Modifier les informations…": "Edit track information…", "Titre": "Title",
    "Artiste": "Artist", "Album": "Album", "Genre": "Genre",
    "Choisir une pochette (facultatif)": "Choose artwork (optional)",
    "Informations mises à jour": "Track information updated",
    "Fermer": "Close", "Par défaut": "Default", "Appliquer": "Apply", "Choisir…": "Choose…",
    "Choisir...": "Choose…", "Nouvelle playlist": "New playlist", "Supprimer": "Delete",
    "Supprimer la playlist": "Delete playlist", "Renommer / image…": "Rename / artwork…",
    "Ajouter des musiques…": "Add tracks…", "Retirer de la playlist": "Remove from playlist",
    "Créer un espace": "Create a profile", "Créer un espace…": "Create a profile…",
    "Modifier le profil…": "Edit profile…", "Supprimer l’espace sélectionné": "Delete selected profile",
    "Espaces utilisateurs": "User profiles", "Paramètres": "Settings",
    "Personnalise le lecteur et ses fonctions principales.": "Customize the player and its main features.",
    "Couleur d’accent": "Accent color", "Couleur d’accentuation": "Accent color",
    "Couleur des éléments": "Interface color", "Couleur du fond": "Background color",
    "Type de fond": "Background type", "Image de fond": "Background image",
    "Vitesse de lecture": "Playback speed", "Répétition": "Repeat",
    "Lecture": "Playback", "Paroles": "Lyrics", "Couleur": "Solid color",
    "Image": "Image", "Image floue": "Blurred image", "Désactivée": "Off",
    "Répéter ce titre": "Repeat this track", "Répéter la liste": "Repeat the list",
    "Passer automatiquement au média suivant": "Automatically play the next item",
    "Afficher les paroles pendant la lecture": "Show lyrics while playing",
    "Importer une image…": "Import an image…", "Importer une image...": "Import an image…",
    "Choisir une image…": "Choose an image…", "Aucune image": "No image",
    "Aucune image importée": "No image imported", "Avatar coloré par défaut": "Default avatar",
    "Profil actif": "Active profile", "En cours": "Active",
    "Qui écoute aujourd’hui ? Chaque profil garde sa bibliothèque, ses playlists et ses réglages.":
        "Who’s listening today? Each profile has its own library, playlists, and settings.",
    "Nom du profil": "Profile name", "Nom de la playlist": "Playlist name",
    "Nom": "Name", "Choisir une image": "Choose an image",
    "Créer un espace utilisateur": "Create a user profile", "Créer un nouvel espace utilisateur": "Create a new user profile",
    "Ouvrir la playlist": "Open playlist", "En cours": "Now playing",
    "Nombre de médias": "Items", "média(s)": "item(s)",
    "Playlist en cours": "Now playing", "Masquer": "Hide", "Afficher": "Show",
    "Nouvelle playlist…": "New playlist…", "Ajouter à la file d’attente": "Add to queue",
    "Ajouter à une playlist…": "Add to playlist…", "Retirer de la bibliothèque": "Remove from library",
    "Ajouter des fichiers…": "Add files…", "Ajouter un dossier…": "Add folder…",
    "Flux réseau…": "Network stream…", "Raccourcis clavier": "Keyboard shortcuts",
    "Lire": "Play", "Pause": "Pause", "Précédent": "Previous", "Suivant": "Next",
    "Vider la file": "Clear queue", "Monter": "Move up", "Descendre": "Move down",
    "Retirer": "Remove", "Ajouter des médias…": "Add media…", "Créer une playlist": "Create a playlist",
    "YouTube": "YouTube", "Télécharger un média": "Download media",
    "Colle le lien d’un média que tu as le droit de télécharger. Le fichier terminé sera ajouté à ta bibliothèque.":
        "Paste a link to media you are allowed to download. The finished file will be added to your library.",
    "Lien": "Link", "Format": "Format", "Format vidéo": "Video format",
    "Piste audio seule": "Audio only", "Langues audio": "Audio languages",
    "Format audio": "Audio format", "Dossier": "Folder",
    "Langues des sous-titres": "Subtitle languages",
    "fr, en ou all — plusieurs langues séparées par des virgules": "fr, en, or all — separate multiple languages with commas",
    "Auto, fr, en ou all — plusieurs langues séparées par des virgules": "Auto, fr, en, or all — separate multiple languages with commas",
    "Saisis les langues audio voulues, par exemple fr,en. « all » prend toutes les pistes disponibles.":
        "Enter the audio languages you want, for example fr,en. Use “all” for every available track.",
    "Saisis les langues de sous-titres avec la même méthode que pour l'audio.":
        "Enter subtitle languages the same way as audio languages.",
    "Télécharger la vidéo ouverte": "Download open video",
    "Rechercher un titre, un artiste ou une vidéo": "Search for a song, artist, or video",
    "Recherche et lecture utilisent le lecteur officiel YouTube. Aucun téléchargement n'est effectué.":
        "Search and playback use the official YouTube player. Nothing is downloaded.",
    "Le navigateur intégré n'est pas installé. Ouvre YouTube dans ton navigateur.":
        "The built-in browser is unavailable. Open YouTube in your browser.",
    "Pour les contenus YouTube, respecte les options de téléchargement proposées par YouTube et les droits du créateur.":
        "For YouTube content, follow YouTube’s download options and respect the creator’s rights.",
    "Je possède ce média ou j'ai l'autorisation de le télécharger.": "I own this media or have permission to download it.",
    "Télécharger les sous-titres disponibles": "Download available subtitles",
    "Colle le lien d'un média que tu as le droit de télécharger. Le fichier terminé sera ajouté à ta bibliothèque.":
        "Paste a link to media you are allowed to download. The finished file will be added to your library.",
    "Colle un lien commençant par http:// ou https://.": "Paste a link starting with http:// or https://.",
    "Choisis un dossier de destination.": "Choose a destination folder.",
    "Confirme d'abord que tu as le droit de télécharger ce média.": "First confirm that you have permission to download this media.",
    "Préparation du téléchargement…": "Preparing download…",
    "Préparation des outils de conversion (première utilisation)…": "Preparing conversion tools (first use)…",
    "Téléchargement en cours": "Downloading",
    "Finalisation du fichier…": "Finalizing file…",
    "Téléchargement annulé.": "Download canceled.",
    "Annulation en cours…": "Canceling…",
    "Saisis le nom d'un titre ou d'un artiste à rechercher.": "Enter a song or artist to search for.",
    "Ouvre une vidéo dans YouTube, puis colle son lien dans Télécharger.": "Open a YouTube video, then paste its link into Download.",
    "Ouvre d'abord la page d'une vidéo, puis réessaie.": "Open a video page first, then try again.",
    "Pistes audio": "Audio tracks", "Langue de la piste audio": "Audio track language",
    "Sous-titres": "Subtitles", "Langues": "Languages", "Dossier": "Folder",
    "Parcourir…": "Browse…", "Télécharger les sous-titres disponibles": "Download available subtitles",
    "Je possède ce média ou j’ai l’autorisation de le télécharger.": "I own this media or have permission to download it.",
    "Télécharger": "Download", "Annuler": "Cancel", "Chercher en ligne": "Search online",
    "Importer un .lrc / .txt…": "Import .lrc / .txt…", "Source : en ligne (cache)": "Source: online (cache)",
    "Aucun média dans la bibliothèque.": "No media in the library.",
    "Aucun média": "No media", "Sélectionner tout": "Select all",
    "Réinitialiser l’application…": "Reset application…",
    "Cette action effacera tous les espaces utilisateurs, les bibliothèques, les playlists et les réglages enregistrés, puis recréera l’espace Principal. Les fichiers audio et vidéo présents sur ton appareil ne seront pas supprimés.\n\nContinuer ?":
        "This will erase all user profiles, libraries, playlists, and saved settings, then recreate the Main profile. Audio and video files on your device will not be deleted.\n\nContinue?",
    "Réinitialiser l’application": "Reset application", "Oui": "Yes", "Non": "No",
    "VLC Media Player doit être installé pour lire les médias.": "VLC Media Player must be installed to play media.",
}

_SOURCE_ROLE = int(Qt.ItemDataRole.UserRole) + 700
_LAST_ROLE = int(Qt.ItemDataRole.UserRole) + 701


def translate_text(text, language):
    if language != "en" or not isinstance(text, str):
        return text
    direct = EN.get(text)
    if direct is not None:
        return direct

    # Keep layout padding used by the sidebar buttons while translating the label.
    stripped = text.strip()
    if stripped != text:
        return text[:len(text) - len(text.lstrip())] + EN.get(stripped, stripped) + text[len(text.rstrip()):]

    # Translate each display line while leaving user-created profile names intact.
    if "\n" in text:
        return "\n".join(EN.get(line, line) for line in text.split("\n"))

    # Dynamic labels such as “Profil actif : [profile name]” contain user data.
    for french, english in EN.items():
        if french.endswith(": ") and text.startswith(french):
            return english + text[len(french):]
    return text


def _translate_property(widget, getter_name, setter_name, property_prefix, language):
    getter = getattr(widget, getter_name, None)
    setter = getattr(widget, setter_name, None)
    if not callable(getter) or not callable(setter):
        return
    current = getter()
    source = widget.property(property_prefix + "Source")
    last = widget.property(property_prefix + "Last")
    if source is None or current != last:
        source = current
        widget.setProperty(property_prefix + "Source", source)
    translated = translate_text(source, language)
    if current != translated:
        setter(translated)
    widget.setProperty(property_prefix + "Last", translated)


def translate_tree(root, language):
    """Translate static and changing UI labels while preserving user-entered text."""
    widgets = [root, *root.findChildren(QWidget)]
    for widget in widgets:
        if hasattr(widget, "windowTitle") and hasattr(widget, "setWindowTitle"):
            _translate_property(widget, "windowTitle", "setWindowTitle", "vlcI18nTitle", language)
        if not isinstance(widget, QLineEdit) and hasattr(widget, "text") and hasattr(widget, "setText"):
            _translate_property(widget, "text", "setText", "vlcI18nText", language)
        if hasattr(widget, "toolTip") and hasattr(widget, "setToolTip"):
            _translate_property(widget, "toolTip", "setToolTip", "vlcI18nTip", language)
        if hasattr(widget, "placeholderText") and hasattr(widget, "setPlaceholderText"):
            _translate_property(widget, "placeholderText", "setPlaceholderText", "vlcI18nPlaceholder", language)

        # Combo item data (UserRole) stays intact; custom roles hold source labels.
        count = getattr(widget, "count", None)
        item_text = getattr(widget, "itemText", None)
        set_item_text = getattr(widget, "setItemText", None)
        item_data = getattr(widget, "itemData", None)
        set_item_data = getattr(widget, "setItemData", None)
        if all(callable(fn) for fn in (count, item_text, set_item_text, item_data, set_item_data)):
            for index in range(count()):
                source = item_data(index, _SOURCE_ROLE)
                last = item_data(index, _LAST_ROLE)
                current = item_text(index)
                if source is None or current != last:
                    source = current
                    set_item_data(index, source, _SOURCE_ROLE)
                translated = translate_text(source, language)
                if current != translated:
                    set_item_text(index, translated)
                set_item_data(index, translated, _LAST_ROLE)

    # Menus and toolbar actions are QObjects rather than QWidget children.
    try:
        from PySide6.QtGui import QAction
        for action in root.findChildren(QAction):
            _translate_property(action, "text", "setText", "vlcI18nText", language)
            _translate_property(action, "toolTip", "setToolTip", "vlcI18nTip", language)
    except ImportError:
        pass
