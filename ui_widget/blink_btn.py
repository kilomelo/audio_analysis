# ui_widget/blink_btn.py
from PyQt5.QtCore import QPropertyAnimation, QEasingCurve, pyqtProperty
from PyQt5.QtGui import QColor
from PyQt5.QtWidgets import QPushButton

class BlinkButton(QPushButton):
    """支持颜色渐变的按钮"""
    def __init__(self, parent=None):
        super().__init__(parent)
        self._blink_color = QColor(255, 255, 255)  # 初始颜色
        self.blink_anim = QPropertyAnimation(self, b"blink_color", self)
        self.setup_animation()

    def setup_animation(self):
        """配置呼吸动画参数"""
        self.blink_anim.setDuration(2000)
        self.blink_anim.setLoopCount(-1)
        self.blink_anim.setEasingCurve(QEasingCurve.Linear)

    def get_blink_color(self):
        return self._blink_color

    def set_blink_color(self, color):
        self._blink_color = color
        # 动态更新样式
        self.setStyleSheet(f"""
            QPushButton {{
                background-color: rgba({color.red()}, {color.green()}, {color.blue()}, {color.alpha()});
                color: white;
                border: none;
                padding: 8px 8px;
                border-radius: 5px;
            }}
        """)

    blink_color = pyqtProperty(QColor, get_blink_color, set_blink_color)

    def start_blink(self):
        """启动呼吸动画"""
        if self.blink_anim.state() != QPropertyAnimation.Running:
            self.blink_anim.setKeyValueAt(0.0, QColor(150, 50, 50, 255))
            self.blink_anim.setKeyValueAt(0.5, QColor(150, 50, 50, 50))
            self.blink_anim.setKeyValueAt(1.0, QColor(150, 50, 50, 255))
            self.blink_anim.start()

    def stop_blink(self):
        """停止动画并恢复默认"""
        self.blink_anim.stop()
        self.set_blink_color(QColor(100, 100, 100))