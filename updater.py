"""Mises à jour automatiques via les Releases GitHub (bibliothèque standard uniquement).

Principe : la dernière release GitHub contient un installateur « ...Setup.exe ».
Si son tag est plus récent que la version installée, l'application propose de le
télécharger, le lance en mode silencieux (il remplace l'ancienne version puis
relance l'application) et se ferme.
"""

import json
import os
import re
import subprocess
import sys
import tempfile
import urllib.request

TIMEOUT = 8


def is_frozen():
    """True quand l'application tourne depuis le .exe (PyInstaller)."""
    return bool(getattr(sys, "frozen", False))


def parse_version(text):
    """'v1.2.3' -> (1, 2, 3). Les parties non numériques sont ignorées."""
    parts = re.findall(r"\d+", str(text).split("-")[0])
    return tuple(int(p) for p in parts) or (0,)


def is_newer(latest, current):
    a, b = parse_version(latest), parse_version(current)
    size = max(len(a), len(b))
    return a + (0,) * (size - len(a)) > b + (0,) * (size - len(b))


def _request(url):
    return urllib.request.Request(url, headers={
        "User-Agent": "VLC-Redesign-Updater",
        "Accept": "application/vnd.github+json",
    })


def pick_asset(assets):
    """Choisit l'installateur (…Setup.exe) puis, à défaut, n'importe quel .exe."""
    exes = [a for a in assets if str(a.get("name", "")).lower().endswith(".exe")]
    for asset in exes:
        if "setup" in asset["name"].lower():
            return asset
    return exes[0] if exes else None


def check(current_version, repo):
    """Interroge GitHub. Renvoie un dict si une version plus récente existe, sinon None.

    Lève une exception en cas d'erreur réseau (à l'appelant de décider quoi en faire).
    """
    if not repo or "TON-" in repo:
        return None                      # dépôt pas encore configuré
    url = f"https://api.github.com/repos/{repo}/releases/latest"
    with urllib.request.urlopen(_request(url), timeout=TIMEOUT) as response:
        data = json.loads(response.read().decode("utf-8"))
    tag = str(data.get("tag_name", ""))
    if not tag or not is_newer(tag, current_version):
        return None
    asset = pick_asset(data.get("assets") or [])
    return {
        "version": tag.lstrip("vV"),
        "notes": (data.get("body") or "").strip(),
        "page": data.get("html_url", f"https://github.com/{repo}/releases/latest"),
        "url": asset["browser_download_url"] if asset else None,
        "name": asset["name"] if asset else None,
    }


def download(url, name, progress=None):
    """Télécharge l'installateur dans le dossier temporaire et renvoie son chemin."""
    target = os.path.join(tempfile.mkdtemp(prefix="vlc_redesign_update_"), name or "Setup.exe")
    request = urllib.request.Request(url, headers={"User-Agent": "VLC-Redesign-Updater"})
    with urllib.request.urlopen(request, timeout=30) as response, open(target, "wb") as out:
        total = int(response.headers.get("Content-Length") or 0)
        done = 0
        while True:
            chunk = response.read(256 * 1024)
            if not chunk:
                break
            out.write(chunk)
            done += len(chunk)
            if progress and total:
                progress(done / total)
    return target


def launch_installer(path):
    """Lance l'installateur en silencieux, détaché de l'application (Windows)."""
    flags = 0
    if sys.platform.startswith("win"):
        flags = 0x00000008 | 0x00000200      # DETACHED_PROCESS | CREATE_NEW_PROCESS_GROUP
    subprocess.Popen([path, "/SILENT", "/NORESTART", "/CLOSEAPPLICATIONS"],
                     creationflags=flags, close_fds=True)
