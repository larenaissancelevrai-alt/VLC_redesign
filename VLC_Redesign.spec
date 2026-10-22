# -*- mode: python ; coding: utf-8 -*-
# Compilation : pyinstaller VLC_Redesign.spec --noconfirm
from PyInstaller.utils.hooks import collect_submodules, collect_data_files

hiddenimports = collect_submodules("yt_dlp") + collect_submodules("static_ffmpeg")
datas = collect_data_files("static_ffmpeg") + collect_data_files("yt_dlp")
# Si tu ajoutes un dossier de ressources (images, sons...), décommente :
# datas += [("assets", "assets")]

a = Analysis(
    ["main.py"],
    pathex=["."],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports + ["vlc", "diagnose", "version", "updater"],
    hookspath=[],
    runtime_hooks=[],
    excludes=["tkinter"],
    noarchive=False,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="VLC Redesign",
    console=False,          # pas de fenêtre noire
    icon="icon.ico" if __import__("os").path.exists("icon.ico") else None,
)

# Mode « dossier » : démarre plus vite et déclenche moins de faux positifs antivirus
coll = COLLECT(exe, a.binaries, a.datas, name="VLC Redesign")
