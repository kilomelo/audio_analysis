# qapp.py
import sys
import os
import time
import threading
import numpy as np
from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QWidget, QHBoxLayout, QListWidgetItem
)
from PyQt5.QtCore import Qt
from audio_processor import RealtimeAudioProcessor, FileAudioProcessor
from visualizer.mpl_canvas import MplCanvas
from control_panel import ControlPanel
from config import BASE_PARAMS

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        if len(sys.argv) > 1:  # 文件模式
            self.audio_processor = FileAudioProcessor()
            self.audio_processor.load_audio_file(sys.argv[1])
        else:                  # 实时模式
            self.audio_processor = RealtimeAudioProcessor()
        self._init_ui()
        self.canvas.connect_control_panel(self.control_panel)
        self._connect_external_signals()
        self.compute_interval = BASE_PARAMS['compute_interval']
        # 控制参数
        self.processing = True
        # 创建独立线程
        self.compute_thread = threading.Thread(target=self._compute_loop)
        self.compute_thread.start()

        self.control_panel.set_slider_state(self._is_file_mode, self.audio_processor.get_total_frames() if self._is_file_mode else 0)
        self.control_panel.update_button_state(self._is_file_mode, (not self._is_file_mode) and self.audio_processor.is_recording)
        self.canvas.start_animation()

    @property
    def _is_file_mode(self) -> bool: return isinstance(self.audio_processor, FileAudioProcessor)

    def _init_ui(self):
        """初始化界面布局"""
        self.setWindowTitle("Audio Visualizer")
        self.setGeometry(100, 100, *BASE_PARAMS['window_size'])

        # 主布局分为左右两部分
        main_widget = QWidget()
        main_layout = QHBoxLayout()
        main_widget.setLayout(main_layout)

        # 左侧图表区
        self.canvas = MplCanvas(self)
        main_layout.addWidget(self.canvas, stretch=5)
        self.audio_processor.add_params_observer(self.canvas)
        
        # 右侧控件区
        self.control_panel = ControlPanel()
        main_layout.addWidget(self.control_panel, stretch=1)
        # 初始化控制面板状态
        self.control_panel.update_file_list()
        self.setCentralWidget(main_widget)

    def _connect_external_signals(self):
        """连接信号与槽"""
        self._control_bindings = {}
        self._control_bindings['rec/noise_reduce_file'] = self._on_reduce_noise_toggled
        self._control_bindings['file_selected'] = self._on_file_selected
        self._control_bindings['slider_value'] = self._on_slider_value_changed
        self.control_panel.param_changed.connect(self._on_control_changed)

        self.control_panel.start_end_record_clicked.connect(self._on_start_end_record_clicked)
        self.control_panel.record_mode_clicked.connect(self._on_record_mode_clicked)
        self.canvas.canvas_changed.connect(self.on_canvas_changed)

    def update_file_list(self):
        """加载音频文件列表"""
        audio_files = [
            f for f in os.listdir('.')
            if f.lower().endswith(('.wav', '.mp3', '.ogg'))
        ]
        for file in sorted(audio_files):
            item = QListWidgetItem(file)
            item.setFlags(Qt.ItemIsEnabled | Qt.ItemIsSelectable)
            self.file_list.addItem(item)

    def on_canvas_changed(self, param_path, value):
        self.control_panel.update_control(param_path, value)
    def _on_start_end_record_clicked(self):
        if self._is_file_mode: return
        if self.audio_processor.is_recording:
            self.audio_processor.stop_recording()
            self.control_panel.update_button_state(False, False)
            self.control_panel.update_file_list()
        else:
            self.audio_processor.start_recording()
            self.control_panel.update_button_state(False, True)

    def _on_record_mode_clicked(self):
        print("Record mode clicked")
        if not self._is_file_mode: return
        self.audio_processor.cleanup()
        self.audio_processor = RealtimeAudioProcessor()
        self.audio_processor.add_params_observer(self.canvas)
        self.canvas.clean()
        self.control_panel.set_slider_state(False, 0)
        self.control_panel.update_button_state(False, False)
        print('切换到录音模式')

    def _on_control_changed(self, param_path, value):
        """处理控制面板参数变化"""
        # print(f'qapp._on_control_changed({param_path}, {value})')
        if param_path not in self._control_bindings: return
        self._control_bindings[param_path](value)

    def _on_file_selected(self, file_name):
        """处理文件选择事件"""
        if not file_name: return
        if self._is_file_mode and self.audio_processor.file_path == file_name: return
        if not self._is_file_mode:
            print('切换到文件模式')
            self.audio_processor.cleanup()
            self.audio_processor = FileAudioProcessor()
            self.audio_processor.add_params_observer(self.canvas)
            
        self.canvas.clean()
        self.audio_processor.load_audio_file(file_name)
        self.control_panel.set_slider_state(True, self.audio_processor.get_total_frames())
        self.control_panel.update_button_state(True, False)
        print(f"Selected file: {file_name}")

    def _on_slider_value_changed(self, value):
        """滑块控件值变化"""
        if not self._is_file_mode: return
        self.audio_processor.seek(value)

    def _on_reduce_noise_toggled(self, checked):
        """保存额外降噪音频文件开关"""
        print(f"Reduce noise: {checked}")
        if not self._is_file_mode: self.audio_processor.reduce_noise = checked

    def _compute_loop(self):
        """高频计算循环"""
        while self.processing:
            start_time = time.time()

            # 更新进度条
            if self._is_file_mode:
                current_frame = self.audio_processor.get_current_frame()
                # 通过控制面板接口更新
                total_seconds = self.audio_processor.get_total_seconds()
                if self.control_panel.slider_being_controlled:
                    slider_time = total_seconds / self.audio_processor.get_total_frames() * self.control_panel.progress_slider.value()
                    self.control_panel.update_time_label(slider_time, total_seconds)
                else:
                    self.control_panel.set_slider_value(current_frame)
                    current_seconds = self.audio_processor.get_current_time()
                    self.control_panel.update_time_label(current_seconds, total_seconds)
            if self.audio_processor.data_ready.is_set():
                # 获取并处理数据
                chunk = self._get_audio_chunk()
                if chunk is not None:
                    self.canvas.compute(self.audio_processor.get_current_time(), self._get_audio_chunk())
                self.audio_processor.data_ready.clear()
            # 精确控制计算频率
            elapsed = time.time() - start_time
            sleep_time = max(0, self.compute_interval - elapsed)
            time.sleep(sleep_time)

    def _get_audio_chunk(self):
        """核心音频数据获取方法"""
        try:
            # 文件播放模式
            if self._is_file_mode:
                chunk = self.audio_processor.get_latest_block()
            # 实时音频输入模式
            else:
                if not self.audio_processor.device_available:
                    return np.zeros()
                chunk = self.audio_processor.get_latest_block()
            # 数据标准化
            if chunk is None:
                return np.zeros(self.audio_processor.n_fft)
            # 统一转换为单声道
            if len(chunk.shape) > 1:
                chunk = chunk.mean(axis=1)
            return chunk
            
        except Exception as e:
            print(f"音频数据获取失败: {str(e)}")
            return np.zeros(self.audio_processor.n_fft)  # 返回静音数据防止崩溃

    def keyPressEvent(self, event):
        if event.key() == Qt.Key_Left:
            print("Left key pressed")
        elif event.key() == Qt.Key_Right:
            print("Right key pressed")

    def clean(self):
        self.canvas.clean()
        self.processing = False
        self.compute_thread.join()
        self.audio_processor.cleanup()
        
    def closeEvent(self, event):        
        print("Closing application...")
        self.clean()

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec_())