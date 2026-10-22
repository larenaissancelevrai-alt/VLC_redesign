"""Mini-lecteur vidéo flottant et conteneur qui signale ses redimensionnements."""
from PySide6.QtCore import Signal, Qt, QPoint, QTimer
from PySide6.QtWidgets import QWidget, QFrame, QLabel, QToolButton, QVBoxLayout, QHBoxLayout, QSizePolicy
from animated_controls import AnimatedToolButton as QToolButton

class OverlayHost(QWidget):
    resized = Signal()
    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.resized.emit()

class MiniPlayer(QFrame):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("miniPlayer")
        self.setParent(parent)
        self.setFixedSize(420, 280)
        self.setStyleSheet("QFrame#miniPlayer { background:#17191f; border:1px solid #555; border-radius:8px; }")
        self.title = QLabel("Lecture en cours")
        self.title.setStyleSheet("color:white; padding:4px;")
        self.play_button = QToolButton(); self.play_button.setText("▶")
        self.expand_button = QToolButton(); self.expand_button.setText("↗")
        self.close_button = QToolButton(); self.close_button.setText("✕")
        bar = QHBoxLayout(); bar.addWidget(self.title, 1); bar.addWidget(self.play_button); bar.addWidget(self.expand_button); bar.addWidget(self.close_button)
        self.video_host = QWidget(self); self.video_host.setStyleSheet("background:#08090b;")
        self.video_host.setMinimumSize(160, 100)
        self.video_host.setAttribute(Qt.WidgetAttribute.WA_NativeWindow, True)
        layout = QVBoxLayout(self); layout.setContentsMargins(6,6,6,6); layout.setSpacing(4); layout.addLayout(bar); layout.addWidget(self.video_host,1)
        self.video_layout = QVBoxLayout(self.video_host)
        self.video_layout.setContentsMargins(0, 0, 0, 0)
        self.video_layout.setSpacing(0)
        self.video_widget = None
        self._anchor = None
        self.hide()
    def set_anchor(self, anchor): self._anchor = anchor
    def set_title(self, title): self.title.setText(str(title))
    def place(self):
        if self.parentWidget():
            p=self.parentWidget(); self.move(max(0,p.width()-self.width()-18), max(0,p.height()-self.height()-18))
    def adopt(self, widget):
        if widget is None: return
        old_parent = widget.parentWidget()
        if old_parent is not None and old_parent.layout() is not None:
            old_parent.layout().removeWidget(widget)
        widget.setParent(self.video_host)
        self.video_widget = widget
        widget.setMinimumSize(0, 0)
        widget.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.video_layout.addWidget(widget)
        self.video_layout.activate()
        widget.setGeometry(self.video_host.contentsRect())
        widget.show()
        QTimer.singleShot(0, self._fit_video)

    def release_video(self):
        if self.video_widget is not None:
            self.video_layout.removeWidget(self.video_widget)
            self.video_widget = None

    def _fit_video(self):
        if self.video_widget is not None:
            self.video_layout.activate()
            self.video_widget.setGeometry(self.video_host.contentsRect())

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._fit_video()
