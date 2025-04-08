# mpl_canvas.py
import time
from collections import deque
import numpy as np
from matplotlib.figure import Figure
from matplotlib.animation import FuncAnimation
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
import matplotlib.pyplot as plt
from visualizer.spectrum_curve_layer import SpectrumCurveLayer
from visualizer.peak_layer import PeakLayer
from visualizer.melody_layer import MelodyLayer
from config import BASE_PARAMS

class DataProtocol:
    def __init__(self):
        self.x_subband = None   # 频率子带轴
        self.x_new = None       # 插值后的频率轴
        self.spectrum = None    # 频谱数据 (interp_data, db_subband)
        self.volume = -np.inf   # 总体音量
        self.peaks = []         # 峰值数据
        self.current_time = 0.0 # 当前时间
        self.artists = []

    def update(self, **kwargs):
        """安全更新数据字段"""
        for key, value in kwargs.items():
            if not hasattr(self, key):
                raise AttributeError(f"'DataProtocol' 没有字段 '{key}'")
            setattr(self, key, value)
class MplCanvas(FigureCanvas):
    """自定义Matplotlib画布"""
    def __init__(self, parent=None):
        self.data_buffer = deque(maxlen=3)  # 缓冲最近3帧数据
        self.latest_artists = []
        self.fig = Figure(facecolor='black')
        pos = [0, 0, 1, 1]
        super().__init__(self.fig)
        self.render_interval = BASE_PARAMS['render_interval']
        self.layers = [SpectrumCurveLayer(), PeakLayer(), MelodyLayer()]
        for layer in self.layers:
            layer.initialize(self.fig, pos)  # 使用独立坐标轴

    def compute(self, current_time, chunk):
        data = DataProtocol()
        data.update(current_time=current_time)
        for layer in self.layers:
            layer.process(chunk, data)
        self.data_buffer.append(data)

    def update_plot(self, frame):
        """低频渲染更新（消费者）"""
        try:
            # 获取最新数据
            if self.data_buffer:
                data = self.data_buffer.pop()
                artists = []
                for layer in self.layers:
                    a = layer.draw(data)
                    if a is None:
                        print(f'{layer}渲染失败')
                    # elif a == []:
                        # print(f'{layer}渲染为空')
                    else: artists.extend(a)
                self.latest_artists = artists
                
            return self.latest_artists
        except Exception as e:
            print(f"渲染失败: {str(e)}")
            return []

    def start_animation(self):
        # todo 改成填充默认数据
        # while len(self.data_buffer) == 0:
            # time.sleep(0.01)  # 短暂等待，避免阻塞
        """启动动画"""
        self.ani = FuncAnimation(
            self.fig, 
            self.update_plot,
            interval=self.render_interval*1000,
            blit=True,
            cache_frame_data=False
        )
        plt.show()

    def clean(self):
        self.data_buffer.clear()
        for layer in self.layers:
            layer.clean()

    def on_audio_params_changed(self, sample_rate, chunk_size, n_fft):
        """响应音频参数变化"""
        for layer in self.layers:
            layer.on_audio_params_changed(sample_rate, chunk_size, n_fft)

    def set_melody_reference_lines_visible(self, visible):
        self.layers[2].set_reference_lines_visible(visible)