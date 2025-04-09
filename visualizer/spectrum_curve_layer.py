# visualizer/spectrum_layer.py
import numpy as np
import librosa
from scipy.interpolate import interp1d
from config import SPECTRUM_CURVE_LAYER_PARAMS, BASE_PARAMS, COLORS
from visualizer.base_layer import BaseLayer

class SpectrumCurveLayer(BaseLayer):
    def __init__(self):
        super().__init__()
        self.sample_rate = None
        self.x_subband = None
        self.x_new = None
        self.line = None
        self.current_volume = -np.inf

    def on_audio_params_changed(self, sample_rate, chunk_size, n_fft):
        """响应音频参数变化"""
        print(f'[Layer] SpectrumCurveLayer: sample_rate changed to {sample_rate}')
        # 只有当参数实际变化时才更新
        if sample_rate != self.sample_rate:
            self.sample_rate = sample_rate
            self.n_fft = n_fft
            self._compute_freq_axis()

    def _compute_freq_axis(self):
        """预计算频率轴（同原逻辑）"""
        freqs = librosa.fft_frequencies(sr=self.sample_rate, n_fft=self.n_fft)
        self.original_freq_mask = (freqs >= BASE_PARAMS['freq_range'][0]) & (freqs <= BASE_PARAMS['freq_range'][1])
        self.x_subband = freqs[self.original_freq_mask]
        self.x_new = np.logspace(np.log10(BASE_PARAMS['freq_range'][0]), np.log10(BASE_PARAMS['freq_range'][1]), 2000)

    def initialize(self, fig, position):
        """初始化频谱线"""
        self.ax = fig.add_axes(position,frameon=False)
        self.ax.set_xscale('log')
        self.ax.set_yscale('linear')
        self.ax.set_xlim(*BASE_PARAMS['freq_range'])
        self.ax.set_ylim(*SPECTRUM_CURVE_LAYER_PARAMS['amplitude_range'])
        self.line, = self.ax.plot([], [],
            color=COLORS['spectrum_curve'],
            lw=SPECTRUM_CURVE_LAYER_PARAMS['line_width'],
            alpha=SPECTRUM_CURVE_LAYER_PARAMS['alpha'],
            zorder = SPECTRUM_CURVE_LAYER_PARAMS['zorder'],
            )

    def _compute_spectrum(self, chunk):
        """核心频谱计算逻辑"""
        # 数据填充
        if len(chunk) < self.n_fft:
            chunk = np.pad(chunk, (0, self.n_fft - len(chunk)))
        # --- 新增：计算音频块整体音量 ---
        rms = np.sqrt(np.mean(chunk**2))  # 计算RMS
        self.current_volume = librosa.amplitude_to_db([rms], ref=BASE_PARAMS['ref_value'])[0]  # 转换为dB
        # STFT计算
        D = librosa.stft(chunk, n_fft=self.n_fft, center=False)
        magnitude = np.abs(D)
        db_spectrum = librosa.amplitude_to_db(magnitude, ref=BASE_PARAMS['ref_value']).max(axis=1)
        
        # 使用预存的原始频率掩码
        self.db_subband = db_spectrum[self.original_freq_mask]  # 关键修复点
        
        # 双插值处理
        interp_data = {}
        try:
            # 平滑插值
            f_smooth = interp1d(self.x_subband, self.db_subband, 
                            kind='cubic', bounds_error=False, 
                            fill_value=-120)
            interp_data['smooth'] = f_smooth(self.x_new)
            
            # 原始插值
            f_raw = interp1d(self.x_subband, self.db_subband, 
                        kind='nearest', bounds_error=False,
                        fill_value=-120)
            interp_data['raw'] = f_raw(self.x_new)
        except Exception as e:
            print(f"插值异常: {str(e)}")
            interp_data['smooth'] = np.full_like(self.x_new, -120)
            interp_data['raw'] = np.full_like(self.x_new, -120)
            
        return interp_data, self.db_subband  # 返回插值数据和原始子带数据


    def process(self, chunk, data_protocol):
        if None == self.sample_rate: return
        # 计算频谱
        interp_data, db_subband = self._compute_spectrum(chunk)
        rms = np.sqrt(np.mean(chunk**2))  # 计算RMS
        volume = librosa.amplitude_to_db([rms], ref=BASE_PARAMS['ref_value'])[0]  # 转换为dB
        data_protocol.update(
            x_subband=self.x_subband if hasattr(self, 'x_subband') else None,
            x_new=self.x_new if hasattr(self, 'x_new') else None,
            spectrum=(interp_data, db_subband),
            volume=volume
        )
        
    
    def draw(self, data_protocol):
        if not SPECTRUM_CURVE_LAYER_PARAMS['visible']: return []
        if None == self.sample_rate: return
        # 更新频谱线
        interp_data = data_protocol.spectrum[0]
        self.line.set_data(self.x_new, interp_data['smooth'] if SPECTRUM_CURVE_LAYER_PARAMS['smoothed_curve'] else interp_data['raw'])
        return [self.line]
    def clean(self):
        self.line.set_data([], [])