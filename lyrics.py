"""Paroles : lecture du format LRC, recherche locale et recherche en ligne (LRCLIB).

Sources, dans l'ordre :
  1. un fichier .lrc (synchronisé) ou .txt à côté du morceau, même nom ;
  2. les paroles intégrées aux tags du fichier (USLT, LYRICS, ©lyr) ;
  3. le cache des paroles déjà téléchargées (~/.vlc_redesign/lyrics) ;
  4. à la demande seulement : LRCLIB (https://lrclib.net), service ouvert et
     gratuit, sans clé. Seuls l'artiste, le titre, l'album et la durée sont
     envoyés.

Sans dépendance à Qt.
"""

import bisect
import hashlib
import json
import os
import re
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

CACHE_DIR = Path.home() / ".vlc_redesign" / "lyrics"
USER_AGENT = "VLCRedesign/1.0 (lecteur multimedia personnel)"
LRCLIB = "https://lrclib.net/api"

_TIME = re.compile(r"\[(\d{1,3}):(\d{1,2})(?:[.:](\d{1,3}))?\]")
_TAG = re.compile(r"^\[([A-Za-z]+):(.*)\]\s*$")
_WORD_TIME = re.compile(r"<\d{1,3}:\d{1,2}(?:[.:]\d{1,3})?>")


class LyricsError(Exception):
    """Erreur lisible par l'utilisateur (réseau, service indisponible…)."""


class Lyrics:
    """Liste de lignes (temps en ms, texte). `synced` vaut False pour un texte brut."""

    def __init__(self, lines, synced, source=""):
        self.lines = lines            # [(ms, texte)] ; ms = 0 partout si non synchronisé
        self.synced = synced
        self.source = source
        self._times = [t for t, _ in lines]

    def __bool__(self):
        return any(text.strip() for _, text in self.lines)

    def index_at(self, ms):
        """Index de la ligne en cours à `ms` (-1 avant la première ligne)."""
        if not self.synced:
            return -1
        return bisect.bisect_right(self._times, ms) - 1

    def to_lrc(self):
        if not self.synced:
            return "\n".join(text for _, text in self.lines)
        out = []
        for ms, text in self.lines:
            minutes, rest = divmod(ms, 60000)
            out.append(f"[{minutes:02d}:{rest // 1000:02d}.{(rest % 1000) // 10:02d}]{text}")
        return "\n".join(out)


def _to_ms(minutes, seconds, fraction):
    ms = int(minutes) * 60000 + int(seconds) * 1000
    if fraction:
        ms += int(fraction.ljust(3, "0")[:3])
    return ms


def parse_lrc(text, source=""):
    """Analyse un texte LRC ou brut. Renvoie un objet Lyrics (ou None si vide)."""
    if not text or not text.strip():
        return None
    text = text.replace("\r\n", "\n").replace("\r", "\n").lstrip("﻿")
    offset = 0
    timed = []
    plain = []
    for raw in text.split("\n"):
        line = raw.strip()
        if not line:
            plain.append("")
            continue
        stamps = list(_TIME.finditer(line))
        if stamps:
            content = _WORD_TIME.sub("", line[stamps[-1].end():]).strip()
            for m in stamps:
                timed.append((_to_ms(*m.groups()), content))
            continue
        tag = _TAG.match(line)
        if tag:
            if tag.group(1).lower() == "offset":
                try:
                    offset = int(tag.group(2).strip())
                except ValueError:
                    pass
            continue           # ar:, ti:, al:, by:… ne sont pas des paroles
        plain.append(line)

    if timed:
        # Spécification LRC : un offset positif fait apparaître les paroles plus tôt.
        timed = sorted(((max(0, t - offset), s) for t, s in timed), key=lambda x: x[0])
        return Lyrics(timed, True, source)

    while plain and not plain[0]:
        plain.pop(0)
    while plain and not plain[-1]:
        plain.pop()
    if not plain:
        return None
    return Lyrics([(0, line) for line in plain], False, source)


# ------------------------------------------------------------------ sources locales
def find_sidecar(media_path):
    """Chemin d'un .lrc/.txt portant le même nom que le média, ou None."""
    folder = os.path.dirname(media_path)
    stem = os.path.splitext(os.path.basename(media_path))[0].lower()
    try:
        names = {n.lower(): n for n in os.listdir(folder)}
    except OSError:
        return None
    for ext in (".lrc", ".txt"):
        real = names.get(stem + ext)
        if real:
            return os.path.join(folder, real)
    return None


def _read_text(path):
    raw = Path(path).read_bytes()
    for enc in ("utf-8-sig", "utf-16", "cp1252", "latin-1"):
        try:
            return raw.decode(enc)
        except UnicodeDecodeError:
            continue
    return raw.decode("utf-8", "replace")


def cache_path(media_path):
    key = hashlib.sha1(media_path.encode("utf-8")).hexdigest()[:24]
    return CACHE_DIR / f"{key}.lrc"


def save_cache(media_path, lyrics):
    try:
        CACHE_DIR.mkdir(parents=True, exist_ok=True)
        cache_path(media_path).write_text(lyrics.to_lrc(), encoding="utf-8")
    except OSError:
        pass


def load_file(path):
    """Charge un fichier de paroles choisi par l'utilisateur (.lrc ou .txt)."""
    return parse_lrc(_read_text(path), source=os.path.basename(path))


def load_local(media_path, embedded=None):
    """Cherche des paroles sans réseau. `embedded` : texte issu des tags (optionnel)."""
    side = find_sidecar(media_path)
    if side:
        try:
            found = parse_lrc(_read_text(side), source=os.path.basename(side))
            if found:
                return found
        except OSError:
            pass
    cached = cache_path(media_path)
    if cached.exists():
        try:
            found = parse_lrc(_read_text(cached), source="en ligne (cache)")
            if found:
                return found
        except OSError:
            pass
    if embedded:
        found = parse_lrc(embedded, source="intégrées au fichier")
        if found:
            return found
    return None


def guess_artist_title(media_path, info=None):
    """(artiste, titre) d'après les tags, sinon « Artiste - Titre » dans le nom du fichier."""
    info = info or {}
    artist, title = info.get("artist", ""), info.get("title", "")
    if artist and title:
        return artist, title
    stem = os.path.splitext(os.path.basename(media_path))[0]
    stem = re.sub(r"^\s*\d{1,3}\s*[-._)]\s*", "", stem)        # « 01 - » devant le titre
    if " - " in stem:
        left, right = stem.split(" - ", 1)
        return artist or left.strip(), title or right.strip()
    return artist, title or stem.strip()


# ---------------------------------------------------------------------- en ligne
def _http_json(url, timeout):
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return json.loads(response.read().decode("utf-8"))


def _from_record(record):
    synced = record.get("syncedLyrics")
    if synced:
        found = parse_lrc(synced, source="LRCLIB")
        if found:
            return found
    plain = record.get("plainLyrics")
    if plain:
        return parse_lrc(plain, source="LRCLIB")
    return None


def fetch_lrclib(artist, title, album="", duration_s=0, timeout=10, opener=_http_json):
    """Cherche des paroles sur LRCLIB. Renvoie un objet Lyrics, ou None si introuvable.

    Lève LyricsError si le service est injoignable. `opener` permet de tester sans réseau.
    """
    if not title.strip():
        raise LyricsError("Titre inconnu : impossible de chercher les paroles.")
    try:
        if artist.strip():
            params = {"track_name": title, "artist_name": artist}
            if album:
                params["album_name"] = album
            if 1 <= duration_s <= 3600:
                params["duration"] = int(duration_s)
            try:
                found = _from_record(opener(f"{LRCLIB}/get?" + urllib.parse.urlencode(params), timeout))
                if found:
                    return found
            except urllib.error.HTTPError as exc:
                if exc.code != 404:
                    raise
        query = f"{artist} {title}".strip()
        results = opener(f"{LRCLIB}/search?" + urllib.parse.urlencode({"q": query}), timeout)
        for record in results if isinstance(results, list) else []:
            if record.get("instrumental"):
                continue
            found = _from_record(record)
            if found:
                return found
        return None
    except urllib.error.HTTPError as exc:
        raise LyricsError(f"Le service de paroles a répondu {exc.code}.") from exc
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        raise LyricsError("Impossible de joindre le service de paroles (connexion ?).") from exc
    except (ValueError, KeyError) as exc:
        raise LyricsError("Réponse inattendue du service de paroles.") from exc