"""Lecture des métadonnées audio, sans dépendance externe.

Formats gérés : MP3 (ID3v2.2/2.3/2.4), FLAC (Vorbis comments + image) et
M4A/MP4 (atomes ilst). Renvoie le titre, l'artiste, l'album, les paroles
intégrées et la pochette (octets bruts JPEG/PNG).

Tout est écrit pour ne jamais lever d'exception : un fichier illisible ou
inattendu donne simplement un dictionnaire vide.
"""

import os
import struct

MAX_BLOCK = 40 * 1024 * 1024   # on refuse de charger un bloc de métadonnées plus gros


# ------------------------------------------------------------------- utilitaires
def _synchsafe(data):
    return (data[0] << 21) | (data[1] << 14) | (data[2] << 7) | data[3]


def _unsynchronise(data):
    """Annule l'« unsynchronisation » ID3 (0xFF 0x00 → 0xFF)."""
    return data.replace(b"\xff\x00", b"\xff")


def _decode(data, enc):
    """Décode un texte ID3 selon son octet d'encodage (0..3)."""
    try:
        if enc == 0:
            return data.decode("latin-1")
        if enc == 1:
            return data.decode("utf-16")          # avec BOM
        if enc == 2:
            return data.decode("utf-16-be")
        return data.decode("utf-8")
    except UnicodeDecodeError:
        return data.decode("utf-8", "replace")


def _split_terminated(data, enc):
    """Coupe `data` au premier terminateur nul de l'encodage. → (avant, après)."""
    if enc in (1, 2):
        i = 0
        while i + 1 < len(data):
            if data[i] == 0 and data[i + 1] == 0 and i % 2 == 0:
                return data[:i], data[i + 2:]
            i += 1
        return data, b""
    i = data.find(b"\x00")
    if i < 0:
        return data, b""
    return data[:i], data[i + 1:]


def _first_text(data):
    """Texte ID3 simple (encodage + texte), première valeur seulement."""
    if not data:
        return ""
    enc, body = data[0], data[1:]
    text = _decode(body, enc)
    return text.split("\x00")[0].strip()


def sniff_image(data):
    """'jpg', 'png', 'gif', 'webp', 'bmp' ou None d'après les premiers octets."""
    if data[:3] == b"\xff\xd8\xff":
        return "jpg"
    if data[:8] == b"\x89PNG\r\n\x1a\n":
        return "png"
    if data[:6] in (b"GIF87a", b"GIF89a"):
        return "gif"
    if data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        return "webp"
    if data[:2] == b"BM":
        return "bmp"
    return None


# -------------------------------------------------------------------------- MP3
_ID3_V22 = {"TT2": "TIT2", "TP1": "TPE1", "TAL": "TALB", "ULT": "USLT", "PIC": "APIC"}


def _read_id3(path):
    info = {}
    with open(path, "rb") as f:
        head = f.read(10)
        if len(head) < 10 or head[:3] != b"ID3":
            return info
        major, flags = head[3], head[5]
        size = _synchsafe(head[6:10])
        if size <= 0 or size > MAX_BLOCK:
            return info
        tag = f.read(size)

    if flags & 0x80 and major in (2, 3):     # unsynchronisation globale
        tag = _unsynchronise(tag)
    pos = 0
    if flags & 0x40 and major >= 3 and len(tag) >= 4:   # en-tête étendu
        ext = _synchsafe(tag[:4]) if major == 4 else struct.unpack(">I", tag[:4])[0] + 4
        pos = min(ext, len(tag))

    best_pic = None   # (priorité, octets)
    while True:
        if major == 2:
            if pos + 6 > len(tag):
                break
            fid = tag[pos:pos + 3].decode("latin-1")
            fsize = int.from_bytes(tag[pos + 3:pos + 6], "big")
            fflags, hdr = 0, 6
            fid = _ID3_V22.get(fid, fid)
        else:
            if pos + 10 > len(tag):
                break
            fid = tag[pos:pos + 4].decode("latin-1")
            raw = tag[pos + 4:pos + 8]
            fsize = _synchsafe(raw) if major == 4 else struct.unpack(">I", raw)[0]
            fflags = struct.unpack(">H", tag[pos + 8:pos + 10])[0]
            hdr = 10
        if not fid.strip("\x00") or fsize <= 0 or pos + hdr + fsize > len(tag):
            break
        data = tag[pos + hdr:pos + hdr + fsize]
        pos += hdr + fsize

        # frames compressées/chiffrées : on les ignore
        if major == 3 and fflags & 0x00C0:
            continue
        if major == 4:
            if fflags & 0x000C:
                continue
            if fflags & 0x0001 and len(data) >= 4:    # indicateur de longueur de données
                data = data[4:]
            if fflags & 0x0002:
                data = _unsynchronise(data)

        try:
            if fid == "TIT2":
                info.setdefault("title", _first_text(data))
            elif fid == "TPE1":
                info.setdefault("artist", _first_text(data))
            elif fid == "TALB":
                info.setdefault("album", _first_text(data))
            elif fid == "TCON":
                info.setdefault("genre", _first_text(data))
            elif fid == "USLT" and len(data) > 4 and "lyrics" not in info:
                enc = data[0]
                _desc, text = _split_terminated(data[4:], enc)   # 1 enc + 3 langue
                text = _decode(text, enc).strip()
                if text:
                    info["lyrics"] = text
            elif fid == "APIC":
                enc = data[0]
                if major == 2:
                    rest = data[4:]                              # enc + format(3)
                else:
                    _mime, rest = _split_terminated(data[1:], 0)
                if not rest:
                    continue
                ptype = rest[0]
                _desc, image = _split_terminated(rest[1:], enc)
                if image and sniff_image(image):
                    priority = 0 if ptype == 3 else 1            # 3 = pochette avant
                    if best_pic is None or priority < best_pic[0]:
                        best_pic = (priority, image)
        except Exception:
            continue

    if best_pic:
        info["cover"] = best_pic[1]
    return {k: v for k, v in info.items() if v}


# ------------------------------------------------------------------------- FLAC
def _read_flac(path):
    info = {}
    best_pic = None
    with open(path, "rb") as f:
        if f.read(4) != b"fLaC":
            return info
        while True:
            head = f.read(4)
            if len(head) < 4:
                break
            last = bool(head[0] & 0x80)
            btype = head[0] & 0x7F
            length = int.from_bytes(head[1:4], "big")
            if btype in (4, 6) and length <= MAX_BLOCK:
                block = f.read(length)
                if btype == 4:
                    _flac_comments(block, info)
                else:
                    pic = _flac_picture(block)
                    if pic and (best_pic is None or pic[0] < best_pic[0]):
                        best_pic = pic
            else:
                f.seek(length, os.SEEK_CUR)
            if last:
                break
    if best_pic:
        info["cover"] = best_pic[1]
    return {k: v for k, v in info.items() if v}


def _flac_comments(block, info):
    try:
        pos = 4 + struct.unpack("<I", block[:4])[0]          # vendor
        count = struct.unpack("<I", block[pos:pos + 4])[0]
        pos += 4
        for _ in range(count):
            n = struct.unpack("<I", block[pos:pos + 4])[0]
            entry = block[pos + 4:pos + 4 + n].decode("utf-8", "replace")
            pos += 4 + n
            key, _sep, value = entry.partition("=")
            key = key.upper()
            mapping = {"TITLE": "title", "ARTIST": "artist", "ALBUM": "album", "GENRE": "genre",
                       "LYRICS": "lyrics", "UNSYNCEDLYRICS": "lyrics"}
            if key in mapping and value.strip():
                info.setdefault(mapping[key], value.strip())
    except (struct.error, IndexError):
        pass


def _flac_picture(block):
    try:
        ptype, mlen = struct.unpack(">II", block[:8])
        pos = 8 + mlen
        dlen = struct.unpack(">I", block[pos:pos + 4])[0]
        pos += 4 + dlen + 16                                  # description + 4 entiers
        size = struct.unpack(">I", block[pos:pos + 4])[0]
        image = block[pos + 4:pos + 4 + size]
        if image and sniff_image(image):
            return (0 if ptype == 3 else 1, image)
    except (struct.error, IndexError):
        pass
    return None


# -------------------------------------------------------------------------- MP4
def _mp4_atoms(data, start=0, end=None):
    """Itère (type, début_données, fin_données) sur les atomes de data[start:end]."""
    end = len(data) if end is None else end
    pos = start
    while pos + 8 <= end:
        size = struct.unpack(">I", data[pos:pos + 4])[0]
        kind = data[pos + 4:pos + 8]
        hdr = 8
        if size == 1 and pos + 16 <= end:
            size = struct.unpack(">Q", data[pos + 8:pos + 16])[0]
            hdr = 16
        elif size == 0:
            size = end - pos
        if size < hdr or pos + size > end:
            break
        yield kind, pos + hdr, pos + size
        pos += size


def _mp4_child(data, start, end, name):
    for kind, s, e in _mp4_atoms(data, start, end):
        if kind == name:
            return s, e
    return None


def _read_mp4(path):
    info = {}
    with open(path, "rb") as f:
        total = os.fstat(f.fileno()).st_size
        pos = 0
        moov = None
        while pos + 8 <= total:
            f.seek(pos)
            head = f.read(16)
            size = struct.unpack(">I", head[:4])[0]
            kind = head[4:8]
            if size == 1:
                size = struct.unpack(">Q", head[8:16])[0]
            elif size == 0:
                size = total - pos
            if size < 8:
                break
            if kind == b"moov":
                if size > MAX_BLOCK:
                    return info
                f.seek(pos)
                moov = f.read(size)
                break
            pos += size
    if moov is None:
        return info

    node = (8, len(moov))
    for name in (b"udta", b"meta", b"ilst"):
        found = _mp4_child(moov, node[0] + (4 if name == b"ilst" else 0), node[1], name)
        if found is None:
            return info
        node = found
    # `meta` est une « full box » : 4 octets de version/flags avant ses enfants.
    for kind, s, e in _mp4_atoms(moov, node[0], node[1]):
        data_atom = _mp4_child(moov, s, e, b"data")
        if data_atom is None:
            continue
        payload = moov[data_atom[0] + 8:data_atom[1]]          # 4 type/flags + 4 locale
        if kind == b"\xa9nam":
            info.setdefault("title", payload.decode("utf-8", "replace").strip())
        elif kind == b"\xa9ART":
            info.setdefault("artist", payload.decode("utf-8", "replace").strip())
        elif kind == b"\xa9alb":
            info.setdefault("album", payload.decode("utf-8", "replace").strip())
        elif kind == b"\xa9gen":
            info.setdefault("genre", payload.decode("utf-8", "replace").strip())
        elif kind == b"\xa9lyr":
            info.setdefault("lyrics", payload.decode("utf-8", "replace").strip())
        elif kind == b"covr" and payload and sniff_image(payload):
            info.setdefault("cover", payload)
    return {k: v for k, v in info.items() if v}


# ------------------------------------------------------------------------ public
def read_info(path):
    """Métadonnées d'un fichier audio : dict avec title/artist/album/lyrics/cover."""
    ext = os.path.splitext(path)[1].lower()
    try:
        if ext == ".mp3":
            return _read_id3(path)
        if ext == ".flac":
            return _read_flac(path)
        if ext in (".m4a", ".mp4", ".m4b"):
            return _read_mp4(path)
        # extension trompeuse (mp3 sans extension…) : on essaie de deviner
        with open(path, "rb") as f:
            magic = f.read(4)
        if magic[:3] == b"ID3":
            return _read_id3(path)
        if magic == b"fLaC":
            return _read_flac(path)
    except (OSError, struct.error, ValueError, IndexError):
        pass
    return {}


COVER_NAMES = ("cover", "folder", "front", "album", "albumart", "poster", "thumb")
COVER_EXTS = (".jpg", ".jpeg", ".png", ".webp")


def find_folder_cover(path):
    """Image « pochette » à côté du média : <nom>.jpg, cover.jpg, folder.png, poster.jpg…"""
    folder = os.path.dirname(path)
    stem = os.path.splitext(os.path.basename(path))[0].lower()
    try:
        files = {name.lower(): name for name in os.listdir(folder)}
    except OSError:
        return None
    candidates = [stem] + list(COVER_NAMES)
    for base in candidates:
        for ext in COVER_EXTS:
            real = files.get(base + ext)
            if real:
                return os.path.join(folder, real)
    return None

class MetaCache:
    """Cache JSON des métadonnées et de l'état des pochettes."""
    def __init__(self, path):
        import json
        self.path = path
        self.data = {}
        self.dirty = False
        try:
            with open(path, "r", encoding="utf-8") as f:
                loaded = json.load(f)
            if isinstance(loaded, dict):
                self.data = loaded
        except (OSError, ValueError, TypeError):
            self.data = {}

    def get(self, key):
        value = self.data.get(str(key))
        return dict(value) if isinstance(value, dict) else None

    def put(self, key, info, nocover=False):
        # Les octets d'image ne sont pas sérialisables en JSON et n'ont pas
        # leur place dans ce cache léger.
        import json
        clean = {}
        if isinstance(info, dict):
            for k, v in info.items():
                if isinstance(v, (str, int, float, bool)) or v is None:
                    clean[k] = v
        clean["nocover"] = bool(nocover)
        self.data[str(key)] = clean
        self.dirty = True

    def save(self):
        if not self.dirty:
            return
        import json
        import tempfile
        folder = os.path.dirname(os.path.abspath(self.path))
        try:
            os.makedirs(folder, exist_ok=True)
            fd, tmp = tempfile.mkstemp(prefix="tags_", suffix=".tmp", dir=folder)
            try:
                with os.fdopen(fd, "w", encoding="utf-8") as f:
                    json.dump(self.data, f, ensure_ascii=False, indent=2)
                os.replace(tmp, self.path)
                self.dirty = False
            finally:
                if os.path.exists(tmp):
                    os.remove(tmp)
        except OSError:
            # Un cache impossible à écrire ne doit pas empêcher l'application.
            pass
