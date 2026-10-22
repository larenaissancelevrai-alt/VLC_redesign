"""Interface de téléchargement pour les médias que l’utilisateur est autorisé à récupérer."""
import os
import shutil
import threading
from pathlib import Path

from PySide6.QtCore import QTimer
from PySide6.QtWidgets import (
    QCheckBox, QComboBox, QFileDialog, QFormLayout, QHBoxLayout, QLabel,
    QLineEdit, QProgressBar, QPushButton, QVBoxLayout, QWidget,
)
from animated_controls import AnimatedPushButton as QPushButton


class DownloaderPanel(QWidget):
    def __init__(self, window):
        super().__init__()
        self.window = window
        self.state = {"status": "", "percent": 0, "speed": "", "eta": "", "filename": ""}
        self.running = False
        self.cancel_event = threading.Event()

        root = QVBoxLayout(self)
        title = QLabel("Télécharger un média")
        title.setObjectName("title")
        root.addWidget(title)
        intro = QLabel(
            "Colle le lien d'un média que tu as le droit de télécharger. "
            "Le fichier terminé sera ajouté à ta bibliothèque."
        )
        intro.setWordWrap(True)
        root.addWidget(intro)

        form = QFormLayout()
        self.url = QLineEdit()
        self.url.setPlaceholderText("https://…")
        form.addRow("Lien", self.url)

        self.media_type = QComboBox()
        self.media_type.addItem("Piste audio seule", "audio")
        self.media_type.addItem("Vidéo", "video")
        self.media_type.currentIndexChanged.connect(self.update_format_controls)
        form.addRow("Format", self.media_type)

        self.audio_languages = QLineEdit()
        self.audio_languages.setPlaceholderText("Auto, fr, en ou all — plusieurs langues séparées par des virgules")
        self.audio_languages.setToolTip("Saisis les langues audio voulues, par exemple fr,en. « all » prend toutes les pistes disponibles.")
        form.addRow("Langues audio", self.audio_languages)

        self.audio_label = QLabel("Format audio")
        self.audio_format = QComboBox()
        self.audio_format.addItem("MP3", "mp3")
        self.audio_format.addItem("M4A", "m4a")
        self.audio_format.addItem("WAV", "wav")
        form.addRow(self.audio_label, self.audio_format)
        self.video_label = QLabel("Format vidéo")
        self.video_format = QComboBox()
        self.video_format.addItem("MP4", "mp4")
        self.video_format.addItem("MKV", "mkv")
        self.video_format.addItem("WebM", "webm")
        form.addRow(self.video_label, self.video_format)
        self.update_format_controls()

        destination_row = QHBoxLayout()
        self.destination = QLineEdit(str(Path.home() / "Downloads"))
        destination_row.addWidget(self.destination, 1)
        browse = QPushButton("Parcourir…")
        browse.clicked.connect(self.choose_destination)
        destination_row.addWidget(browse)
        form.addRow("Dossier", destination_row)
        self.download_subtitles = QCheckBox("Télécharger les sous-titres disponibles")
        form.addRow("Sous-titres", self.download_subtitles)
        self.subtitle_languages = QLineEdit()
        self.subtitle_languages.setPlaceholderText("fr, en ou all — plusieurs langues séparées par des virgules")
        self.subtitle_languages.setToolTip("Saisis les langues de sous-titres avec la même méthode que pour l'audio.")
        form.addRow("Langues des sous-titres", self.subtitle_languages)
        root.addLayout(form)

        self.rights = QCheckBox("Je possède ce média ou j'ai l'autorisation de le télécharger.")
        root.addWidget(self.rights)
        action_row = QHBoxLayout()
        self.start_button = QPushButton("Télécharger")
        self.start_button.clicked.connect(self.start_download)
        action_row.addWidget(self.start_button)
        self.cancel_button = QPushButton("Annuler")
        self.cancel_button.setEnabled(False)
        self.cancel_button.clicked.connect(self.cancel_download)
        action_row.addWidget(self.cancel_button)
        root.addLayout(action_row)

        self.progress = QProgressBar()
        self.progress.setRange(0, 100)
        self.progress.setValue(0)
        root.addWidget(self.progress)
        self.status = QLabel(
            "Pour les contenus YouTube, respecte les options de téléchargement proposées par YouTube "
            "et les droits du créateur."
        )
        self.status.setWordWrap(True)
        root.addWidget(self.status)
        root.addStretch(1)

        self.timer = QTimer(self)
        self.timer.setInterval(250)
        self.timer.timeout.connect(self.refresh_progress)

    def update_format_controls(self, _index=None):
        audio = self.media_type.currentData() == "audio"
        self.audio_label.setVisible(audio)
        self.audio_format.setVisible(audio)
        self.audio_languages.setVisible(True)
        self.video_label.setVisible(not audio)
        self.video_format.setVisible(not audio)

    def choose_destination(self):
        start = self.destination.text().strip() or str(Path.home())
        folder = QFileDialog.getExistingDirectory(self, "Choisir le dossier de téléchargement", start)
        if folder:
            self.destination.setText(folder)

    def start_download(self):
        url = self.url.text().strip()
        destination = self.destination.text().strip()
        if not url.startswith(("https://", "http://")):
            self.status.setText("Colle un lien commençant par http:// ou https://.")
            return
        if not destination:
            self.status.setText("Choisis un dossier de destination.")
            return
        if not self.rights.isChecked():
            self.status.setText("Confirme d'abord que tu as le droit de télécharger ce média.")
            return
        if self.running:
            return

        self.state = {"status": "starting", "percent": 0, "speed": "", "eta": "", "filename": ""}
        self.cancel_event.clear()
        self.running = True
        self.start_button.setEnabled(False)
        self.cancel_button.setEnabled(True)
        self.progress.setValue(0)
        self.status.setText("Préparation du téléchargement…")
        self.timer.start()
        media_type = self.media_type.currentData()
        audio_format = self.audio_format.currentData()
        video_format = self.video_format.currentData()
        audio_languages = [part.strip().lower() for part in self.audio_languages.text().replace(";", ",").split(",") if part.strip()]
        audio_languages = [lang for lang in audio_languages if lang not in ("auto", "automatique")]
        all_audio_tracks = "all" in audio_languages
        if all_audio_tracks:
            audio_languages = []
        download_subtitles = self.download_subtitles.isChecked()
        subtitle_languages = self.subtitle_languages.text().strip()

        def work():
            try:
                import yt_dlp
            except ImportError as exc:
                raise RuntimeError(
                    "yt-dlp n'est pas installé. Dans le dossier du projet, lance : "
                    "python -m pip install -r requirements.txt"
                ) from exc

            os.makedirs(destination, exist_ok=True)

            self.state["status"] = "preparing_tools"
            ffmpeg_path = shutil.which("ffmpeg")      # FFmpeg déjà installé : on l'utilise
            if not ffmpeg_path:
                try:
                    import static_ffmpeg
                    ffmpeg_path, _ffprobe_path = static_ffmpeg.run.get_or_fetch_platform_executables_else_raise()
                except Exception as exc:
                    raise RuntimeError(f"Impossible de préparer FFmpeg : {exc}") from exc

            def on_progress(data):
                if self.cancel_event.is_set():
                    raise yt_dlp.utils.DownloadCancelled("Téléchargement annulé par l'utilisateur.")
                status = data.get("status", "")
                self.state["status"] = status
                self.state["filename"] = data.get("filename", "")
                if status == "downloading":
                    total = data.get("total_bytes") or data.get("total_bytes_estimate") or 0
                    downloaded = data.get("downloaded_bytes") or 0
                    self.state["percent"] = int(downloaded * 100 / total) if total else -1
                    speed = data.get("speed") or 0
                    self.state["speed"] = f"{speed / 1024:.0f} Ko/s" if speed else ""
                    eta = data.get("eta")
                    self.state["eta"] = f"{int(eta)} s" if eta is not None else ""

            def on_postprocessor(data):
                if data.get("status") == "finished":
                    info_dict = data.get("info_dict") or {}
                    final_path = info_dict.get("filepath")
                    if final_path:
                        self.state["output_filepath"] = final_path

            audio = media_type == "audio"
            if audio:
                selected_format = audio_format
                format_selector = ",".join(f"bestaudio[language^={lang}]" for lang in audio_languages) if audio_languages else "bestaudio/best"
                postprocessors = [{
                    "key": "FFmpegExtractAudio",
                    "preferredcodec": audio_format,
                    "preferredquality": "192",
                }]
            else:
                selected_format = video_format
                video_selector = {
                    "mp4": "bv*[ext=mp4]+ba[ext=m4a]/bv*[ext=mp4]+ba/b[ext=mp4]/bv*+ba/b",
                    "mkv": "bv*+ba/b",
                    "webm": "bv*[ext=webm]+ba[ext=webm]/bv*[ext=webm]+ba/b[ext=webm]/bv*+ba/b",
                }[video_format]
                def video_selector_for_language(language):
                    audio_language_filter = f"[language^={language}]"
                    if video_format == "mp4":
                        return (
                            f"bv*[ext=mp4]+ba{audio_language_filter}[ext=m4a]/"
                            f"bv*[ext=mp4]+ba{audio_language_filter}/bv*+ba{audio_language_filter}"
                        )
                    if video_format == "webm":
                        return (
                            f"bv*[ext=webm]+ba{audio_language_filter}[ext=webm]/"
                            f"bv*[ext=webm]+ba{audio_language_filter}/bv*+ba{audio_language_filter}"
                        )
                    return f"bv*+ba{audio_language_filter}"

                format_selector = ",".join(
                    video_selector_for_language(lang) for lang in audio_languages
                ) if audio_languages else video_selector
                postprocessors = [{"key": "FFmpegVideoRemuxer", "preferedformat": video_format}]
            options = {
                "format": format_selector,
                "outtmpl": os.path.join(
                    destination,
                    "%(title)s [%(id)s] - %(format_id)s.%(ext)s" if all_audio_tracks or len(audio_languages) > 1
                    else "%(title)s [%(id)s].%(ext)s",
                ),
                "noplaylist": True,
                "windowsfilenames": True,
                "quiet": True,
                "no_warnings": True,
                "ffmpeg_location": os.path.dirname(ffmpeg_path),
                "postprocessors": postprocessors,
                "postprocessor_hooks": [on_postprocessor],
                "progress_hooks": [on_progress],
            }
            if download_subtitles:
                languages = [part.strip() for part in subtitle_languages.replace(";", ",").split(",") if part.strip()]
                options.update({
                    "writesubtitles": True,
                    "writeautomaticsub": True,
                    "subtitleslangs": languages or ["fr", "en"],
                    "subtitlesformat": "srt/best",
                })
            if not audio:
                options["merge_output_format"] = video_format
            before = set(os.listdir(destination))
            with yt_dlp.YoutubeDL(options) as downloader:
                if all_audio_tracks:
                    # Discover the available audio formats, then request the best
                    # downloadable format for each distinct language in one yt-dlp job.
                    info = downloader.extract_info(url, download=False)
                    formats = (info or {}).get("formats") or []
                    best_by_language = {}
                    for audio_entry in formats:
                        if audio_entry.get("vcodec") != "none" or not audio_entry.get("acodec"):
                            continue
                        language = (audio_entry.get("language") or "und").lower()
                        current = best_by_language.get(language)
                        score = (
                            audio_entry.get("abr") or 0,
                            audio_entry.get("quality") or 0,
                            audio_entry.get("filesize") or audio_entry.get("filesize_approx") or 0,
                        )
                        current_score = (
                            (current.get("abr") or 0),
                            (current.get("quality") or 0),
                            (current.get("filesize") or current.get("filesize_approx") or 0),
                        ) if current else None
                        if current is None or score > current_score:
                            best_by_language[language] = audio_entry
                    if not best_by_language:
                        raise RuntimeError("Aucune piste audio téléchargeable n'a été trouvée.")
                    if audio:
                        format_ids = [
                            str(entry.get("format_id")) for _language, entry in sorted(best_by_language.items())
                            if entry.get("format_id")
                        ]
                        options["format"] = ",".join(format_ids)
                    else:
                        available_languages = sorted(lang for lang in best_by_language if lang != "und")
                        options["format"] = ",".join(
                            video_selector_for_language(language)
                            for language in available_languages
                        ) or video_selector
                    with yt_dlp.YoutubeDL(options) as downloader:
                        info = downloader.extract_info(url, download=True)
                else:
                    info = downloader.extract_info(url, download=True)
                if not info:
                    raise RuntimeError("Aucun média n'a été téléchargé.")
                requested = info.get("requested_downloads") or []
                original_path = (requested[0].get("filepath") if requested else None) or downloader.prepare_filename(info)
                expected_path = os.path.splitext(original_path)[0] + "." + selected_format
                candidates = [
                    self.state.get("output_filepath"), info.get("filepath"),
                    expected_path, original_path,
                ]
                filepath = next((candidate for candidate in candidates if candidate and os.path.isfile(candidate)), None)
            if all_audio_tracks or len(audio_languages) > 1:
                audio_paths = sorted(
                    os.path.join(destination, name)
                    for name in set(os.listdir(destination)) - before
                    if name.lower().endswith("." + selected_format.lower())
                )
                if not audio_paths:
                    raise RuntimeError("yt-dlp n'a pas retrouvé les fichiers correspondant aux langues choisies.")
                filepath = audio_paths[0]
            else:
                audio_paths = [filepath] if filepath and os.path.isfile(filepath) else []
            if not filepath or not os.path.isfile(filepath):
                raise RuntimeError("yt-dlp n'a pas retrouvé le fichier téléchargé sur le disque.")
            subtitle_extensions = (".srt", ".vtt", ".ass", ".ssa", ".ttml")
            subtitles = [
                os.path.join(destination, name) for name in set(os.listdir(destination)) - before
                if name.lower().endswith(subtitle_extensions)
            ] if download_subtitles else []
            return audio_paths, media_type, sorted(subtitles)

        def done(result):
            filepaths, kind, subtitles = result
            for filepath in filepaths:
                if kind == "audio":
                    self.window.cfg.data["meta"][filepath] = {"kind": "audio"}
            was_present = sum(filepath in self.window.library for filepath in filepaths)
            added = self.window.add_paths(filepaths)
            if kind == "audio":
                self.window.save_soon()
            self.finish()
            if len(filepaths) > 1:
                name = f"{len(filepaths)} pistes audio" if kind == "audio" else f"{len(filepaths)} vidéos avec les pistes audio choisies"
            else:
                name = os.path.basename(filepaths[0])
            if added:
                suffix = f"{len(added)} fichier(s) ajouté(s) à la bibliothèque."
            elif was_present:
                suffix = "Déjà présent(s) dans la bibliothèque."
            else:
                suffix = "Enregistré(s), mais ce format n'est pas pris en charge par la bibliothèque."
            detail = f"\nSous-titres enregistrés : {len(subtitles)}" if subtitles else (
                "\nAucun sous-titre disponible pour les langues choisies."
                if download_subtitles else ""
            )
            self.status.setText(f"Téléchargement terminé : {name}\n{suffix}{detail}")
            self.progress.setValue(100)

        def failed(error):
            self.finish()
            if self.cancel_event.is_set():
                self.status.setText("Téléchargement annulé.")
            else:
                message = str(error)
                if any(term in message.lower() for term in ("javascript runtime", "js runtime", "yt-dlp-ejs")):
                    message += "\nPour YouTube, installe aussi Deno (moteur JavaScript recommandé par yt-dlp), puis relance l'application."
                self.status.setText(f"Le téléchargement a échoué : {message}")

        if not self.window.runner.run(work, done, failed, key="yt_dlp_download"):
            self.finish()
            self.status.setText("Un autre téléchargement est déjà en cours.")

    def refresh_progress(self):
        state = self.state
        if state.get("status") == "preparing_tools":
            self.progress.setRange(0, 0)
            self.status.setText("Préparation des outils de conversion (première utilisation)…")
        elif state.get("status") == "downloading":
            percent = state.get("percent", -1)
            if percent >= 0:
                self.progress.setValue(max(0, min(100, percent)))
                detail = f"{percent} %"
            else:
                self.progress.setRange(0, 0)
                detail = "Téléchargement en cours"
            if state.get("speed"):
                detail += f" · {state['speed']}"
            if state.get("eta"):
                detail += f" · reste {state['eta']}"
            self.status.setText(detail)
        elif state.get("status") == "finished":
            self.status.setText("Finalisation du fichier…")

    def finish(self):
        self.timer.stop()
        self.progress.setRange(0, 100)
        self.start_button.setEnabled(True)
        self.cancel_button.setEnabled(False)
        self.running = False

    def cancel_download(self):
        if self.running:
            self.cancel_event.set()
            self.cancel_button.setEnabled(False)
            self.status.setText("Annulation en cours…")
