"""Diagnostic de l'installation : Python, PySide6, VLC (y compris 32/64 bits), FFmpeg.

Utilisable seul (`python diagnose.py`) ou depuis l'assistant de démarrage.
Sans dépendance à Qt : fonctionne même si PySide6 n'est pas encore installé.
"""

import importlib.util
import os
import platform
import shutil
import struct
import sys

OK, WARN, ERROR = "ok", "warn", "error"

_VLC_DIRS_WINDOWS = (
    ("ProgramFiles", r"VideoLAN\VLC"),
    ("ProgramFiles(x86)", r"VideoLAN\VLC"),
    ("ProgramW6432", r"VideoLAN\VLC"),
    ("LOCALAPPDATA", r"Programs\VideoLAN\VLC"),
)
_VLC_PATHS_MAC = ("/Applications/VLC.app/Contents/MacOS",)


def python_bits():
    return 64 if struct.calcsize("P") * 8 == 64 else 32


def pe_bits(path):
    """32 ou 64 d'après l'en-tête PE d'une DLL Windows, None si illisible."""
    try:
        with open(path, "rb") as f:
            head = f.read(4096)
        offset = struct.unpack("<I", head[0x3C:0x40])[0]
        machine = struct.unpack("<H", head[offset + 4:offset + 6])[0]
    except (OSError, struct.error):
        return None
    return {0x8664: 64, 0xAA64: 64, 0x14C: 32}.get(machine)


def find_vlc_dirs(env=None):
    """Dossiers d'installation de VLC trouvés (Windows/macOS)."""
    env = os.environ if env is None else env
    found = []
    if sys.platform.startswith("win"):
        for var, sub in _VLC_DIRS_WINDOWS:
            base = env.get(var)
            if base:
                path = os.path.join(base, sub)
                if os.path.isfile(os.path.join(path, "libvlc.dll")) and path not in found:
                    found.append(path)
    elif sys.platform == "darwin":
        found = [p for p in _VLC_PATHS_MAC if os.path.isdir(p)]
    return found


def vlc_environment(env=None):
    """Variables à définir pour que python-vlc trouve VLC. {} si inutile/introuvable."""
    for path in find_vlc_dirs(env):
        if sys.platform.startswith("win"):
            if pe_bits(os.path.join(path, "libvlc.dll")) not in (None, python_bits()):
                continue          # mauvaise architecture : inutilisable avec ce Python
            return {"PYTHON_VLC_LIB_PATH": os.path.join(path, "libvlc.dll"),
                    "PYTHON_VLC_MODULE_PATH": os.path.join(path, "plugins")}
        return {"PYTHON_VLC_LIB_PATH": os.path.join(path, "lib", "libvlc.dylib"),
                "PYTHON_VLC_MODULE_PATH": os.path.join(path, "plugins")}
    return {}


def check_vlc(backend_available=None, backend_error=""):
    """(niveau, message) sur l'état de VLC. `backend_available` : résultat du vrai chargement."""
    if backend_available:
        return OK, "VLC est détecté et prêt."

    dirs = find_vlc_dirs()
    if sys.platform.startswith("win") and dirs:
        wrong = [d for d in dirs if pe_bits(os.path.join(d, "libvlc.dll")) not in (None, python_bits())]
        if wrong and len(wrong) == len(dirs):
            vlc_bits = pe_bits(os.path.join(wrong[0], "libvlc.dll"))
            return ERROR, (
                f"VLC {vlc_bits} bits est installé, mais votre Python est en {python_bits()} bits. "
                f"Les deux doivent avoir la même architecture : installez VLC {python_bits()} bits "
                "(ou un Python " + str(vlc_bits) + " bits).")
        return ERROR, ("VLC est installé mais n'a pas pu être chargé. Réinstallez VLC depuis "
                       "videolan.org puis relancez." + (f" Détail : {backend_error}" if backend_error else ""))
    if importlib.util.find_spec("vlc") is None:
        return ERROR, "Le module python-vlc n'est pas installé (pip install -r requirements.txt)."
    return ERROR, ("VLC Media Player est introuvable. Installez-le depuis videolan.org "
                   f"(version {python_bits()} bits) puis relancez." +
                   (f" Détail : {backend_error}" if backend_error else ""))


def check_pyside():
    if importlib.util.find_spec("PySide6") is None:
        return ERROR, "PySide6 n'est pas installé : exécutez « python -m pip install -r requirements.txt »."
    return OK, "PySide6 est installé."


def check_ffmpeg():
    if shutil.which("ffmpeg"):
        return OK, "FFmpeg est détecté : les miniatures de vidéos seront générées."
    return WARN, ("FFmpeg est absent (facultatif) : les vidéos auront une vignette générique. "
                  "Les pochettes des musiques fonctionnent sans lui.")


def check_python():
    version = sys.version_info
    if version < (3, 10):
        return ERROR, f"Python {version.major}.{version.minor} est trop ancien : il faut Python 3.10 ou plus."
    return OK, f"Python {version.major}.{version.minor}.{version.micro} ({python_bits()} bits)."


def run_all(backend_available=None, backend_error=""):
    """Liste de (nom, niveau, message)."""
    return [
        ("Python", *check_python()),
        ("PySide6", *check_pyside()),
        ("VLC", *check_vlc(backend_available, backend_error)),
        ("FFmpeg", *check_ffmpeg()),
    ]


def main():
    print(f"Système : {platform.platform()}")
    backend_ok, error = None, ""
    try:
        import vlc  # noqa: F401
        backend_ok = True
    except Exception as exc:
        backend_ok, error = False, str(exc)
    icons = {OK: "[ OK ]", WARN: "[ !  ]", ERROR: "[ XX ]"}
    worst = OK
    for name, level, message in run_all(backend_ok, error):
        print(f"{icons[level]} {name:8s} {message}")
        if level == ERROR:
            worst = ERROR
    return 0 if worst == OK else 1


if __name__ == "__main__":
    sys.exit(main())