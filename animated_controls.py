"""Small, theme-aware interaction animations for the app's buttons."""

from PySide6.QtCore import QEasingCurve, Property, QPropertyAnimation
from PySide6.QtGui import QBrush, QColor, QPainter, QPen
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QPushButton, QToolButton


class _AnimatedButton:
    def _init_interaction_animation(self):
        self._hover_amount = 0.0
        self._press_amount = 0.0
        self._hover_animation = QPropertyAnimation(self, b"hoverAmount", self)
        self._hover_animation.setDuration(170)
        self._hover_animation.setEasingCurve(QEasingCurve.Type.OutCubic)
        self._press_animation = QPropertyAnimation(self, b"pressAmount", self)
        self._press_animation.setDuration(90)
        self._press_animation.setEasingCurve(QEasingCurve.Type.OutCubic)

    def _animate(self, animation, prop, target):
        animation.stop()
        animation.setStartValue(prop())
        animation.setEndValue(target)
        animation.start()

    def _get_hover_amount(self):
        return self._hover_amount

    def _set_hover_amount(self, value):
        self._hover_amount = float(value)
        self.update()

    def _get_press_amount(self):
        return self._press_amount

    def _set_press_amount(self, value):
        self._press_amount = float(value)
        self.update()

    def enterEvent(self, event):
        self._animate(self._hover_animation, self._get_hover_amount, 1.0)
        super().enterEvent(event)

    def leaveEvent(self, event):
        self._animate(self._hover_animation, self._get_hover_amount, 0.0)
        self._animate(self._press_animation, self._get_press_amount, 0.0)
        super().leaveEvent(event)

    def mousePressEvent(self, event):
        self._animate(self._press_animation, self._get_press_amount, 1.0)
        super().mousePressEvent(event)

    def mouseReleaseEvent(self, event):
        self._animate(self._press_animation, self._get_press_amount, 0.0)
        super().mouseReleaseEvent(event)

    def paintEvent(self, event):
        super().paintEvent(event)
        strength = max(self._hover_amount, self._press_amount)
        if strength <= 0.01 or not self.isEnabled():
            return
        owner = self.window()
        colors = owner.colors() if hasattr(owner, "colors") else {}
        # Keep an unselected profile tile visually distinct from the selected
        # one: hover uses a soft neutral outline, selection keeps the accent.
        neutral_profile_hover = (
            self.objectName() == "profileCard" and self.isCheckable() and not self.isChecked()
        )
        color = QColor(
            colors.get("border", "#555860") if neutral_profile_hover
            else colors.get("accent", "#ff6b35")
        )
        color.setAlphaF(min(0.65 if neutral_profile_hover else 0.85, 0.18 + 0.48 * strength))
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        painter.setPen(QPen(color, 1.1 + 0.8 * self._press_amount))
        painter.setBrush(QBrush(Qt.BrushStyle.NoBrush))
        painter.drawRoundedRect(self.rect().adjusted(1, 1, -2, -2), 8, 8)
        painter.end()


class AnimatedPushButton(_AnimatedButton, QPushButton):
    hoverAmount = Property(float, _AnimatedButton._get_hover_amount, _AnimatedButton._set_hover_amount)
    pressAmount = Property(float, _AnimatedButton._get_press_amount, _AnimatedButton._set_press_amount)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._init_interaction_animation()


class AnimatedToolButton(_AnimatedButton, QToolButton):
    hoverAmount = Property(float, _AnimatedButton._get_hover_amount, _AnimatedButton._set_hover_amount)
    pressAmount = Property(float, _AnimatedButton._get_press_amount, _AnimatedButton._set_press_amount)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._init_interaction_animation()
