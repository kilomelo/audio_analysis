# visualizer/base_layer.py
from abc import ABC, ABCMeta, abstractmethod
from qtpy.QtCore import QObject, Signal

class ABCQMeta(type(QObject), ABCMeta):  # 合并两个元类
    pass

class BaseLayer(QObject, metaclass=ABCQMeta):
    param_changed = Signal(str, object)
    def __init__(self):
        QObject.__init__(self)
        self._params = {}
        self._bindings = {}

    def bind_param(self, name, setter, getter):
        """参数绑定注册"""
        self._bindings[name] = (setter, getter)
        
    def get_param(self, name):
        if name in self._bindings:
            return self._bindings[name][1]()
        return self._params.get(name)
    
    def set_param(self, name, value):
        if name in self._bindings:
            self._bindings[name][0](value)
        else:
            self._params[name] = value
        # self.param_changed.emit(name, value)
        
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