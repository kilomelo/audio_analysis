# visualizer/base_layer.py
from abc import ABC, abstractmethod

class BaseLayer(ABC):
    @abstractmethod
    def initialize(self, fig, position):
        """初始化绘图资源"""
        pass

    @abstractmethod
    def process(self, chunk, data_protocol):
        """
        处理音频数据
        :param chunk: 原始音频块
        :param data_protocol: 数据共享容器
        """
        pass
    @abstractmethod
    def draw(self, data_protocol):
        """绘制绘图元素
        :return: list[Artist] 需要渲染的绘图元素
        """
        pass
    @abstractmethod
    def clean(self):
        """清理绘图资源"""
        pass
    def on_audio_params_changed(self, sample_rate, chunk_size, n_fft):
        """音频参数变化时调用"""
        pass