# control_panel.py
import os
from datetime import datetime
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QPushButton, 
    QListWidget, QListWidgetItem, QSlider, QLabel, QCheckBox
)
from PyQt5.QtCore import Qt, pyqtSignal
from ui_widget.blink_btn import BlinkButton

class ControlPanel(QWidget):
    # 自定义信号
    file_selected = pyqtSignal(str)
    start_end_record_clicked = pyqtSignal()
    record_mode_clicked = pyqtSignal()
    reduce_noise_toggled = pyqtSignal(int)
    slider_released = pyqtSignal(int)
    slider_moved = pyqtSignal(int)
    slider_pressed = pyqtSignal()
    melody_ref_lines_toggled = pyqtSignal(int)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._init_ui()
        self.slider_being_controlled = False  # 新增状态标志
        self._connect_internal_signals()

    def _init_ui(self):
        """初始化界面布局"""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(5, 5, 5, 5)
        
        # 进度条组件
        self.progress_slider = QSlider(Qt.Horizontal)
        self.time_label = QLabel("00:00 / 00:00")
        self._init_progress_style()
        
        # 文件列表
        self.file_list = QListWidget()
        self._init_list_style()
        
        # 布局结构
        layout.addWidget(self.progress_slider)
        layout.addWidget(self.time_label)
        layout.addWidget(self._create_btn_group())
        layout.addWidget(self._create_toggle_group())
        layout.addWidget(self.file_list)

    def _init_progress_style(self):
        """进度条样式初始化"""
        self.progress_slider.setStyleSheet("""
            QSlider::groove:horizontal {
                background: #404040;
                height: 6px;
                border-radius: 3px;
            }
            QSlider::sub-page:horizontal {
                background: #4080FF;
                border-radius: 3px;
            }
            QSlider::add-page:horizontal {
                background: #404040;
                border-radius: 3px;
            }
            QSlider::handle:horizontal {
                background: #FFFFFF;
                width: 12px;
                margin: -4px 0;
                border-radius: 6px;
            }
        """)

    def _init_list_style(self):
        """文件列表样式初始化"""
        self.file_list.setStyleSheet("""
            QListWidget::item:hover { background: #505050; }
            QListWidget::item:selected { background: #406080; }
        """)
        self.file_list.setAlternatingRowColors(True)

    def _create_btn_group(self):
        """创建按钮容器"""
        btn_group = QWidget()
        layout = QVBoxLayout(btn_group)
        # 按钮组
        self.btn_start_end_record = BlinkButton("Start record")
        self.btn_record_mode = QPushButton("Record mode")
        layout.addWidget(self.btn_start_end_record)
        layout.addWidget(self.btn_record_mode)
        return btn_group
    
    def _create_toggle_group(self):
        """创建勾选框容器"""
        toggle_group = QWidget()
        layout = QVBoxLayout(toggle_group)
        # 旋律层参考线勾选框
        self.toggle_melody_ref_lines = QCheckBox("Show Melody pitch reference line")
        # 保存额外降噪文件勾选框
        self.toggle_reduce_noise = QCheckBox("Save the noise-reduced audio")
        layout.addWidget(self.toggle_melody_ref_lines)
        layout.addWidget(self.toggle_reduce_noise)
        return toggle_group

    def _connect_internal_signals(self):
        """内部信号连接"""
        self.file_list.itemDoubleClicked.connect(
            lambda item: self.file_selected.emit(item.text())
        )
        self.btn_start_end_record.clicked.connect(self.start_end_record_clicked)
        self.btn_record_mode.clicked.connect(self.record_mode_clicked)
        self.toggle_reduce_noise.stateChanged.connect(self.reduce_noise_toggled)
        self.toggle_melody_ref_lines.stateChanged.connect(self.melody_ref_lines_toggled)
        self.progress_slider.sliderReleased.connect(
            lambda: self.slider_released.emit(self.progress_slider.value())
        )
        self.progress_slider.sliderPressed.connect(self._on_slider_pressed)
        self.progress_slider.sliderReleased.connect(self._on_slider_released)

    def update_button_state(self, is_file_mode, is_recording):
        """更新按钮状态"""
        self.btn_start_end_record.setEnabled(not is_file_mode)
        self.btn_record_mode.setEnabled(is_file_mode)
        
        if is_recording:
            self.btn_start_end_record.setText("Recording, click to stop")
            self.btn_start_end_record.start_blink()
        else:
            self.btn_start_end_record.setText("Start record")
            self.btn_start_end_record.stop_blink()

    def _on_slider_pressed(self):
        self.slider_being_controlled = True
        self.slider_pressed.emit()

    def _on_slider_released(self):
        self.slider_being_controlled = False
    # 公共接口
    def update_file_list(self):
        """更新文件列表"""
        self.file_list.clear()
        audio_files = [
            (f, os.path.getctime(f))  # 组成(文件名, 时间戳)元组
            for f in os.listdir('.')
            if f.lower().endswith(('.wav', '.mp3', '.ogg'))
        ]

        # 按时间戳降序排序（新文件在前）
        sorted_files = sorted(audio_files, key=lambda x: x[1], reverse=True)
        for file_name, _ in sorted_files:
            item = QListWidgetItem(file_name)
            item.setFlags(Qt.ItemIsEnabled | Qt.ItemIsSelectable)
            self.file_list.addItem(item)

    def set_slider_state(self, enabled, max_value=0):
        """设置进度条状态"""
        self.progress_slider.setEnabled(enabled)
        if enabled:
            self.progress_slider.setRange(0, max_value)
            self.progress_slider.setValue(0)
        else:
            self.progress_slider.setRange(0, 0)
            self.progress_slider.setValue(0)
            self.update_time_label(0, 0)
            
    def set_slider_value(self, value):
        """设置进度条值"""
        self.progress_slider.setValue(value)

    def update_time_label(self, current, total):
        """更新时间显示"""
        self.time_label.setText(
            f"{int(current//60)}:{int(current%60):02d} / "
            f"{int(total//60)}:{int(total%60):02d}"
        )