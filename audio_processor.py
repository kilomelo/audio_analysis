# audio_processor.py - 音频处理模块
import sounddevice as sd
import soundfile as sf
import librosa
import noisereduce as nr
from scipy.io import wavfile
import numpy as np
from collections import deque
import threading
import time
from abc import ABC, abstractmethod
from datetime import datetime
from config import BASE_PARAMS

class BaseAudioProcessor(ABC):
    """音频处理器抽象基类，定义公共接口和基础功能"""
    def __init__(self, default_sample_rate: int, default_chunk_size: int, default_n_fft: int):
        """
        初始化基础音频参数和组件
        :param default_sample_rate: 默认采样率（Hz）
        :param default_chunk_size: 音频块大小（采样点数）
        """
        if default_sample_rate <= 0 or default_chunk_size <= 0 or default_n_fft <= 0:
            raise ValueError("Sample rate, chunk size and n_fft must be positive integers")
        self.base_sample_rate = default_sample_rate
        self.sample_rate = self.base_sample_rate
        self.base_chunk_size = default_chunk_size
        self.chunk_size = self.base_chunk_size
        self.base_n_fft = default_n_fft
        self.n_fft = self.base_n_fft
        self.data_ready = threading.Event()  # 数据就绪事件
        self.lock = threading.Lock()         # 线程安全锁
        self._observers = []                 # 参数观察者列表

    def add_params_observer(self, observer: callable) -> None:
        """
        添加参数变化观察者
        :param observer: 观察者回调函数，格式：func(sample_rate: int, chunk_size: int)
        """
        if observer not in self._observers:
            self._observers.append(observer)
            params = (self.sample_rate, self.chunk_size, self.n_fft)
            if callable(observer):
                observer(*params)
            elif hasattr(observer, 'on_audio_params_changed'):
                observer.on_audio_params_changed(*params)

    def _notify_observers(self) -> None:
        """通知所有观察者参数已更新"""
        params = (self.sample_rate, self.chunk_size, self.n_fft)
        for observer in self._observers:
            if callable(observer):
                observer(*params)
            elif hasattr(observer, 'on_audio_params_changed'):
                observer.on_audio_params_changed(*params)

    def set_sample_rate(self, sample_rate: int) -> None:
        """设置采样率"""
        self.sample_rate = sample_rate
        multiplier = max(round(self.sample_rate / self.base_sample_rate), 1)
        self.chunk_size = self.base_chunk_size * multiplier
        self.n_fft = self.base_n_fft * multiplier
        self._notify_observers()

    @abstractmethod
    def get_latest_block(self) -> np.ndarray:
        """获取最新音频块（需子类实现）"""
        pass

    @abstractmethod
    def get_current_time(self) -> float:
        """获取当前处理时间（需子类实现）"""
        pass

    @abstractmethod
    def cleanup(self) -> None:
        """清理资源（需子类实现）"""
        pass

class RealtimeAudioProcessor(BaseAudioProcessor):
    """实时音频输入处理器"""
    def __init__(self):
        super().__init__(
            default_sample_rate=BASE_PARAMS['default_sample_rate'],
            default_chunk_size=BASE_PARAMS['chunk_size'],
            default_n_fft=BASE_PARAMS['n_fft']
        )
        self.audio_blocks = deque(maxlen=100)  # 环形缓冲区存储最近100个块
        self.device_available = False        # 输入设备状态
        self.processed_blocks = 0            # 已处理块计数器
        self.start_time = time.time()        # 处理开始时间
        self.stream = None                   # 音频流对象
        self._init_device_monitor()          # 启动设备监控线程

        # 新增录音相关属性
        self.recording_lock = threading.Lock()    # 录音专用锁
        self._is_recording = False                # 录音状态标志
        self.recording_buffer = []                # 录音数据缓冲区
        self.active_recording_blocks = 0          # 录音块计数器

        self.reduce_noise = False                 # 录音保存时是否额外生成降噪后的音频

    def _init_device_monitor(self) -> None:
        """启动独立的设备状态监控线程"""
        def monitor_task():
            while True:
                try:
                    devices = sd.query_devices()
                    has_input = False
                    for d in devices:
                        if d['max_input_channels'] > 0:
                            has_input = True
                    if has_input != self.device_available:
                        self.device_available = has_input
                        self._handle_device_change()
                except Exception as e:
                    print(f"设备监控异常: {e}")
                time.sleep(BASE_PARAMS['device_check_interval'])

        threading.Thread(
            target=monitor_task,
            daemon=True
        ).start()

    def _handle_device_change(self) -> None:
        """处理设备连接/断开事件"""
        if self.device_available:
            input_device = sd.query_devices(sd.default.device[0])
            channels = input_device['max_input_channels']
            self.set_sample_rate(input_device['default_samplerate'])
            print(f"检测到输入设备（{channels}声道），启动音频流...")
            self._start_stream(channels)
        else:
            print("输入设备已断开")
            self._stop_stream()

    def _audio_callback(self, indata: np.ndarray, *_) -> None:
        """音频输入回调（由sounddevice驱动）"""
        with self.lock:
            if indata.ndim == 2 and indata.shape[1] >= 2:
                # 双声道：取平均值合并
                processed_data = indata.mean(axis=1)
            else:
                # 单声道：直接取数据
                processed_data = indata[:, 0] if indata.ndim == 2 else indata.flatten()
            self.audio_blocks.append(processed_data.copy())
            self.processed_blocks += 1

            # 新增录音数据收集
            with self.recording_lock:
                if self._is_recording:
                    self.recording_buffer.append(processed_data.copy())
                    self.active_recording_blocks += 1
        self.data_ready.set()

    def start_recording(self) -> None:
        """开始录音"""
        with self.recording_lock:
            if self._is_recording: return
            self._is_recording = True
            self.recording_buffer.clear()
            self.active_recording_blocks = 0
            print("录音已开始...")

    def stop_recording(self) -> None:
        """停止录音并保存文件"""
        with self.recording_lock:
            if not self._is_recording: return
            self._is_recording = False
            if len(self.recording_buffer) > 0:
                try:
                    audio_data = np.concatenate(self.recording_buffer)
                    # 维度修正
                    if audio_data.ndim == 1:
                        audio_data = audio_data.reshape(-1, 1)
                    timestamp = datetime.now().strftime("%H%M%S-%y%m%d")
                    filename = f"{timestamp}.wav"
                    sf.write(
                        filename, 
                        audio_data, 
                        int(self.sample_rate),
                        subtype='PCM_16'
                    )

                    if self.reduce_noise:
                        # 关键修改点1：直接对内存数据降噪
                        reduced_noise = nr.reduce_noise(
                            y=audio_data.flatten(),  # 兼容单声道/立体声
                            sr=int(self.sample_rate),  # 强制转为int类型
                            stationary=True
                        )
                        if reduced_noise.ndim == 1:
                            reduced_noise = reduced_noise.reshape(-1, 1)
                        filename = f"{timestamp}-denoise.wav"
                        # 强制采样率为整数
                        sf.write(
                            filename, 
                            reduced_noise, 
                            int(self.sample_rate),
                            subtype='PCM_16'
                        )
                    
                    print(f"已保存录音文件: {filename}")
                except Exception as e:
                    print(f"保存录音失败: {e}")
            self.recording_buffer.clear()
            print("录音已停止")

    @property
    def is_recording(self) -> bool:
        """获取当前录音状态"""
        with self.recording_lock:
            return self._is_recording

    def _start_stream(self, channels: int) -> None:
        """启动音频输入流"""
        self._stop_stream()  # 确保关闭现有连接
        try:
            self.stream = sd.InputStream(
                samplerate=self.sample_rate,
                channels=channels,
                blocksize=self.chunk_size,
                callback=self._audio_callback,
                dtype='float32'
            )
            self.stream.start()
        except Exception as e:
            print(f"音频流启动失败: {e}")

    def _stop_stream(self) -> None:
        """安全停止音频流"""
        if self.stream and self.stream.active:
            self.stream.stop()
            self.stream.close()
        self.stream = None

    def get_latest_block(self) -> np.ndarray:
        """获取最新的音频数据块（线程安全）"""
        with self.lock:
            return self.audio_blocks[-1] if self.audio_blocks else np.zeros(self.chunk_size)

    def get_current_time(self) -> float:
        """获取从开始处理到现在的持续时间"""
        return time.time() - self.start_time

    def cleanup(self) -> None:
        """清理资源"""
        self._stop_stream()

class FileAudioProcessor(BaseAudioProcessor):
    """音频文件处理器（支持循环播放）"""
    def __init__(self):
        super().__init__(
            default_sample_rate=BASE_PARAMS['default_sample_rate'],
            default_chunk_size=BASE_PARAMS['chunk_size'],
            default_n_fft=BASE_PARAMS['n_fft']
        )
        self.audio_blocks = []              # 预分割的音频块列表
        self.current_frame = 0              # 当前播放位置
        self.stream = None                  # 输出流对象
        self.loop_playback = True           # 循环播放标志

    def load_audio_file(self, file_path: str) -> None:
        """加载并预处理音频文件"""
        self.cleanup()
        self.file_path = file_path          # 音频文件路径
        
        try:
            # 使用librosa加载音频（保持原始采样率）
            y, original_sample_rate = librosa.load(
                self.file_path, sr=None, mono=True
            )
            
            # 如果文件采样率与系统不同，更新参数并通知观察者
            if original_sample_rate != self.sample_rate:
                self.set_sample_rate(original_sample_rate)

            # 将音频分割为固定大小的块
            total_frames = len(y)
            for i in range(0, total_frames, self.chunk_size):
                chunk = y[i:i+self.chunk_size]
                if len(chunk) < self.chunk_size:
                    chunk = np.pad(chunk, (0, self.chunk_size - len(chunk)))
                self.audio_blocks.append(chunk)
                
            print(f"文件加载完成，总时长：{total_frames/self.sample_rate:.2f}秒")
            self.start_stream()
        except Exception as e:
            raise RuntimeError(f"文件加载失败: {e}")

    def start_stream(self) -> None:
        """启动音频文件播放"""
        def _playback_callback(outdata: np.ndarray, *_) -> None:
            """音频输出回调（由sounddevice驱动）"""
            try:
                with self.lock:
                    if self.current_frame < len(self.audio_blocks):
                        outdata[:] = self.audio_blocks[self.current_frame].reshape(-1, 1)
                        self.current_frame += 1
                        self.data_ready.set()
                    else:
                        if self.loop_playback:
                            self.current_frame = 0
                            print("循环播放")
                        else:
                            raise sd.CallbackStop
            except Exception as e:
                print(f"播放异常: {e}")
                raise sd.CallbackStop

        # 创建并启动输出流
        self.stream = sd.OutputStream(
            samplerate=self.sample_rate,
            channels=1,
            blocksize=self.chunk_size,
            callback=_playback_callback,
            dtype='float32'
        )
        self.stream.start()

    def get_latest_block(self) -> np.ndarray:
        """获取当前播放的音频块（带防零处理）"""
        with self.lock:
            if self.current_frame == 0:
                return np.zeros(self.chunk_size) + 1e-6
            return self.audio_blocks[self.current_frame - 1]

    def get_current_time(self) -> float:
        """计算当前播放时间（防止零值）"""
        with self.lock:
            base_time = (self.current_frame * self.chunk_size) / self.sample_rate
            return max(base_time, 0.001)
        
    def get_total_seconds(self) -> float:
        return len(self.audio_blocks) * self.chunk_size / self.sample_rate  # 总时长（秒
        
    def get_total_frames(self):
        return len(self.audio_blocks)  # 总帧数
    
    def get_current_frame(self):
        return self.current_frame  # 当前帧数
    
    def seek(self, position):
        with self.lock:
            self.current_frame = min(max(0, position), len(self.audio_blocks) -1)

    def cleanup(self) -> None:
        """释放音频流资源"""
        if self.stream and self.stream.active:
            self.stream.stop()
            self.stream.close()
        self.audio_blocks = []
        self.current_frame = 0
        # print("文件播放器已清理")