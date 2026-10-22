"""Registre des raccourcis clavier (modifiables) et gestionnaire Qt.

Le registre (ACTIONS, effective, conflict) est du Python pur, donc testable sans
Qt. Le gestionnaire importe PySide6 au moment de sa création seulement.

Choix pensé pour un clavier AZERTY : aucun raccourci ne dépend d'un chiffre
(il faut Maj pour les taper) ni de crochets (AltGr).
"""

from collections import namedtuple

Action = namedtuple("Action", "id label default scope group")

# scope : "player" = seulement sur l'écran du lecteur ; "media" = lecteur et bibliothèque ;
#         "global" = partout.
ACTIONS = [
    Action("play_pause", "Lecture / Pause", "Space", "media", "Lecture"),
    Action("stop", "Arrêter", "S", "media", "Lecture"),
    Action("prev", "Média précédent", "P", "media", "Lecture"),
    Action("next", "Média suivant", "N", "media", "Lecture"),
    Action("seek_back", "Reculer de 10 s", "Left", "player", "Lecture"),
    Action("seek_fwd", "Avancer de 10 s", "Right", "player", "Lecture"),
    Action("seek_back_long", "Reculer de 1 min", "Ctrl+Left", "player", "Lecture"),
    Action("seek_fwd_long", "Avancer de 1 min", "Ctrl+Right", "player", "Lecture"),
    Action("speed_down", "Ralentir la lecture", "Ctrl+Down", "player", "Lecture"),
    Action("speed_up", "Accélérer la lecture", "Ctrl+Up", "player", "Lecture"),
    Action("speed_reset", "Vitesse normale", "Ctrl+Backspace", "player", "Lecture"),
    Action("vol_up", "Volume +5", "Up", "player", "Son"),
    Action("vol_down", "Volume −5", "Down", "player", "Son"),
    Action("mute", "Couper / rétablir le son", "M", "media", "Son"),
    Action("audio_cycle", "Piste audio suivante", "B", "player", "Pistes"),
    Action("sub_cycle", "Sous-titres suivants", "V", "player", "Pistes"),
    Action("import_audio", "Importer une piste audio…", "Ctrl+Shift+A", "player", "Pistes"),
    Action("import_subs", "Importer des sous-titres…", "Ctrl+Shift+S", "player", "Pistes"),
    Action("fullscreen", "Plein écran", "F", "player", "Affichage"),
    Action("leave_fs", "Quitter le plein écran", "Escape", "player", "Affichage"),
    Action("hide_ui", "Masquer / afficher les contrôles", "H", "player", "Affichage"),
    Action("lyrics", "Afficher / masquer les paroles", "L", "player", "Affichage"),
    Action("to_library", "Retour à la bibliothèque", "Backspace", "player", "Affichage"),
    Action("open_files", "Ajouter des fichiers…", "Ctrl+O", "global", "Bibliothèque"),
    Action("open_folder", "Ajouter un dossier…", "Ctrl+Shift+O", "global", "Bibliothèque"),
    Action("open_stream", "Ouvrir un flux réseau…", "Ctrl+U", "global", "Bibliothèque"),
    Action("search", "Rechercher", "Ctrl+F", "global", "Bibliothèque"),
    Action("page_home", "Aller à Accueil", "Ctrl+Shift+H", "global", "Bibliothèque"),
    Action("page_video", "Aller à Vidéos", "Ctrl+Shift+V", "global", "Bibliothèque"),
    Action("page_music", "Aller à Musique", "Ctrl+Shift+M", "global", "Bibliothèque"),
    Action("page_playlist", "Aller à Playlists", "Ctrl+Shift+P", "global", "Bibliothèque"),
    Action("page_discover", "Aller à Découvrir", "Ctrl+D", "global", "Bibliothèque"),
    Action("settings", "Paramètres", "Ctrl+,", "global", "Application"),
    Action("help", "Aide : raccourcis clavier", "F1", "global", "Application"),
    Action("quit", "Quitter", "Ctrl+Q", "global", "Application"),
]

BY_ID = {a.id: a for a in ACTIONS}
FIXED_ALIASES = [("F11", "fullscreen")]       # touches supplémentaires non modifiables


def effective(overrides=None):
    """{id: séquence} : valeurs par défaut, modifiées par `overrides`."""
    overrides = overrides or {}
    return {a.id: overrides.get(a.id, a.default) for a in ACTIONS}


def _norm(seq):
    return seq.replace(" ", "").lower()


def conflict(current, action_id, seq):
    """Libellé de l'action qui utilise déjà `seq` (autre que `action_id`), sinon None."""
    if not seq.strip():
        return None
    wanted = _norm(seq)
    for other_id, other_seq in current.items():
        if other_id != action_id and other_seq.strip() and _norm(other_seq) == wanted:
            return BY_ID[other_id].label
    for alias, target in FIXED_ALIASES:
        if _norm(alias) == wanted and target != action_id:
            return BY_ID[target].label
    return None


def groups():
    """[(nom du groupe, [Action…])] dans l'ordre d'apparition."""
    out = {}
    for action in ACTIONS:
        out.setdefault(action.group, []).append(action)
    return list(out.items())


class ShortcutManager:
    """Crée un QShortcut par action et permet de les remplacer à chaud."""

    def __init__(self, window, handlers, overrides=None):
        from PySide6.QtCore import Qt
        from PySide6.QtGui import QKeySequence, QShortcut
        self._qt = (Qt, QKeySequence, QShortcut)
        self.window = window
        self.sequences = effective(overrides)
        self.shortcuts = {}      # id → QShortcut
        self.aliases = []        # [(QShortcut, id)]
        self._on_player = False
        for action in ACTIONS:
            handler = handlers.get(action.id)
            if handler is not None:
                self.shortcuts[action.id] = self._make(self.sequences[action.id], handler)
        for seq, target in FIXED_ALIASES:
            if target in handlers:
                self.aliases.append((self._make(seq, handlers[target]), target))
        self.set_player_page(False)

    def _make(self, seq, handler):
        Qt, QKeySequence, QShortcut = self._qt
        shortcut = QShortcut(QKeySequence(seq), self.window)
        shortcut.setContext(Qt.ShortcutContext.WindowShortcut)
        shortcut.activated.connect(handler)
        return shortcut

    def set_player_page(self, on_player):
        """Active les raccourcis « player » seulement sur l'écran du lecteur."""
        self._on_player = on_player
        for action_id, shortcut in self.shortcuts.items():
            shortcut.setEnabled(on_player or BY_ID[action_id].scope != "player")
        for shortcut, target in self.aliases:
            shortcut.setEnabled(on_player or BY_ID[target].scope != "player")

    def rebind(self, action_id, seq):
        """Change la touche d'une action (séquence vide = désactivée)."""
        _Qt, QKeySequence, _QShortcut = self._qt
        self.sequences[action_id] = seq
        if action_id in self.shortcuts:
            self.shortcuts[action_id].setKey(QKeySequence(seq))

    def overrides(self):
        """Écarts par rapport aux valeurs par défaut, prêts à être enregistrés."""
        return {i: s for i, s in self.sequences.items() if s != BY_ID[i].default}