"""Recherche et lecture YouTube intégrées, sans téléchargement de médias."""
from urllib.parse import quote

from PySide6.QtCore import QUrl
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import QHBoxLayout, QLabel, QLineEdit, QPushButton, QVBoxLayout, QWidget
from animated_controls import AnimatedPushButton as QPushButton

try:
    from PySide6.QtWebEngineWidgets import QWebEngineView
except ImportError:
    QWebEngineView = None


class YouTubePanel(QWidget):
    def __init__(self, window):
        super().__init__()
        self.window = window
        layout = QVBoxLayout(self)

        title = QLabel("YouTube Music")
        title.setObjectName("title")
        layout.addWidget(title)

        row = QHBoxLayout()
        self.search = QLineEdit()
        self.search.setPlaceholderText("Rechercher un titre, un artiste ou une vidéo")
        self.search.returnPressed.connect(self.search_youtube)
        row.addWidget(self.search, 1)
        search_button = QPushButton("Rechercher")
        search_button.clicked.connect(self.search_youtube)
        row.addWidget(search_button)
        external_button = QPushButton("Ouvrir dans le navigateur")
        external_button.clicked.connect(self.open_external)
        row.addWidget(external_button)
        self.download_button = QPushButton("Télécharger la vidéo ouverte")
        self.download_button.clicked.connect(self.send_video_to_downloader)
        row.addWidget(self.download_button)
        layout.addLayout(row)

        self.status = QLabel()
        self.status.setWordWrap(True)
        if QWebEngineView is not None:
            self.view = QWebEngineView(self)
            self.view.setUrl(self._youtube_url())
            layout.addWidget(self.view, 1)
            self.status.setText("Recherche et lecture utilisent le lecteur officiel YouTube. Aucun téléchargement n'est effectué.")
        else:
            self.view = None
            layout.addStretch(1)
            self.status.setText("Le navigateur intégré n'est pas installé. Ouvre YouTube dans ton navigateur.")
        layout.addWidget(self.status)

    def _search_url(self):
        query = self.search.text().strip()
        if not query:
            return self._youtube_url()
        return QUrl("https://music.youtube.com/search?q=" + quote(query) + self._language_query())

    def _language_query(self):
        return "&hl=en" if self.window.cfg.get("language", "fr") == "en" else "&hl=fr"

    def _youtube_url(self):
        return QUrl("https://music.youtube.com/?hl=en" if self.window.cfg.get("language", "fr") == "en"
                    else "https://music.youtube.com/?hl=fr")

    def search_youtube(self):
        if not self.search.text().strip():
            self.status.setText("Saisis le nom d'un titre ou d'un artiste à rechercher.")
            return
        url = self._search_url()
        if self.view is not None:
            self.view.setUrl(url)
        else:
            QDesktopServices.openUrl(url)

    def open_external(self):
        QDesktopServices.openUrl(self._search_url())

    def send_video_to_downloader(self):
        if self.view is None:
            self.status.setText("Ouvre une vidéo dans YouTube, puis colle son lien dans Télécharger.")
            return
        url = self.view.url().toString()
        if "youtube.com/watch" not in url and "youtu.be/" not in url:
            self.status.setText("Ouvre d'abord la page d'une vidéo, puis réessaie.")
            return
        self.window.downloads.url.setText(url)
        self.window.go_page("downloads")

    def opened(self):
        pass

    def update_language(self):
        """Reload the embedded YouTube page with the selected locale."""
        if self.view is not None:
            self.view.setUrl(self._search_url())
