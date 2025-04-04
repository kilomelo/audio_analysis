# visualizer/peak_layer.py
import numpy as np
from collections import defaultdict
from matplotlib import patheffects
from peak_detector import PeakDetector
from pitch_utils import PitchConverter
from config import BASE_PARAMS, PEAK_LAYER_PARAMS, COLORS
from visualizer.base_layer import BaseLayer

class PeakLayer(BaseLayer):
    def __init__(self):
        """接收频率轴参数"""
        self.detector = None
        self.pitch_converter = PitchConverter(reference=BASE_PARAMS['reference_pitch'])
        self.artifacts = {'lines': [], 'texts': []}
        self.ax = None
        self.cache = []  # 新增缓存，存储格式: [{'freq': float, 'note_name': str, 'timestamp': float}]

    def initialize(self, fig, position):
        """初始化图层"""
        self.fig = fig
        self.ax = fig.add_axes(position, frameon=False)
        self.ax.set_xscale('log')
        self.ax.set_yscale('linear')
        self.ax.set_xlim(*BASE_PARAMS['freq_range'])
        self.ymax = 100
        self.ax.set_ylim((0,self.ymax))
        self.line, = self.ax.plot([], [], color=COLORS['spectrum_curve'], lw=1.2, alpha=0.8)
        
    def process(self, chunk, data_protocol):
        """
        处理峰值数据
        :param data_protocol
        """
        if (data_protocol.x_subband is None) or \
            (data_protocol.x_new is None) or \
            (data_protocol.spectrum is None) or \
            (data_protocol.volume is None):
            return []
        current_time = data_protocol.current_time
        # 清理过期缓存（保留最近N秒的数据）
        cache_threshold = current_time - PEAK_LAYER_PARAMS['untishake_time_threshold']
        self.cache = [entry for entry in self.cache if entry['timestamp'] >= cache_threshold]
        len2 = len(self.cache)
        
        # 音量阈值检查
        if data_protocol.volume < PEAK_LAYER_PARAMS['volume_threshold']:
            return []
        
        if not self.detector:  # 延迟初始化
            self.detector = PeakDetector(
                x_subband=data_protocol.x_subband,
                x_new=data_protocol.x_new
            )

        # 获取频谱数据
        interp_data, db_subband = data_protocol.spectrum
        try:
            peaks = self.detector.detect_peaks(interp_data, db_subband)
            data_protocol.update(
                peaks=peaks
            )

            for freq, _ in peaks:
                note_name, _ = self.pitch_converter.get_nearest_pitch_info(freq)
                self.cache.append({
                    'freq': freq,
                    'note_name': note_name,
                    'timestamp': current_time
                })
        except Exception as e:
            print(f"峰值计算失败: {str(e)}")

    def draw(self, data_protocol):
        """绘制峰值"""
        # 绘制标注
        if not PEAK_LAYER_PARAMS['visible']: return []
        self._clear_artifacts()
        # 按音名分组并计算平均频率
        note_groups = defaultdict(list)
        for entry in self.cache:
            if entry['note_name']:  # 过滤无效音名
                note_groups[entry['note_name']].append(entry['freq'])
        for i, (freq, _) in enumerate(data_protocol.peaks):
            # 获取音高信息
            note_name, _ = self.pitch_converter.get_nearest_pitch_info(freq)
            if not note_name or note_name not in note_groups.keys():
                average_freq = freq
            else:
                average_freq = np.mean(note_groups[note_name])
            # if i == 0: print(f'freq delta between cache and peaks: {freq - average_freq:.1f}, cache cnt: {len(note_groups[note_name])},\n\t freq: {freq:.1f}, average_freq: {average_freq:.1f}, note_name: {note_name}')
            _, cents = self.pitch_converter.get_nearest_pitch_info(average_freq)
            # 绘制频率竖线
            self._draw_vertical_line(average_freq)
            # 绘制文本标注
            self._draw_text_label(average_freq, note_name, cents, i)
            # 绘制音分横线
            if note_name and abs(cents) >= 1:
                self._draw_cents_line(average_freq, cents)

        return self.artifacts['lines'] + self.artifacts['texts']
            
    def _clear_artifacts(self):
        """清除旧的绘图元素"""
        for artist in self.artifacts['lines'] + self.artifacts['texts']:
            if artist:
                artist.remove()
        self.artifacts = {'lines': [], 'texts': []}

    def _draw_vertical_line(self, freq):
        """绘制频率竖线"""
        vline = self.ax.vlines(
            x=freq,
            ymin=0,
            ymax=self.ymax,
            colors=COLORS['peaks_line'],
            linewidth=1.2,
            alpha=0.8,
            linestyle='--',
            zorder = PEAK_LAYER_PARAMS['zorder'],
        )
        self.artifacts['lines'].append(vline)

    def _draw_text_label(self, freq, note_name, cents, index):
        """绘制文本标注"""
        text_line1 = f"{freq:.1f} Hz"
        text_line2 = f"{note_name} {int(cents):+d}" if note_name else ""
        
        # 动态计算文本位置
        text_x = freq * (1 + PEAK_LAYER_PARAMS['text_x_offset'])
        text_y = PEAK_LAYER_PARAMS['text_y_offset'] + (PEAK_LAYER_PARAMS['text_fontsize'] * 0.65) * (index % 2)
        text = self.ax.text(
            text_x, text_y,
            f"{text_line1}\n{text_line2}",
            color=COLORS['peaks_hint_text'],
            fontsize=PEAK_LAYER_PARAMS['text_fontsize'],
            ha='left',
            va='bottom',
            bbox=dict(
                facecolor=COLORS['peaks_hint_text_box'],
                alpha=PEAK_LAYER_PARAMS['text_box_alpha'],
                edgecolor='none',
                pad=1
            ),
            path_effects=[
                patheffects.withStroke(linewidth=1.5, foreground="black")],
            zorder = PEAK_LAYER_PARAMS['zorder'],
        )
        self.artifacts['texts'].append(text)

    def _draw_cents_line(self, freq, cents):
        """绘制音分偏差横线"""
        # 计算线宽
        cent_abs = min(abs(cents), PEAK_LAYER_PARAMS['deviation_max_cent'])
        width_ratio = cent_abs / PEAK_LAYER_PARAMS['deviation_max_cent']
        line_width = PEAK_LAYER_PARAMS['deviation_max_width'] * width_ratio
        
        if cents > 0:
            x_start = freq
            x_end = freq * (1 + line_width * 0.001)  # 对数坐标适配
            color = COLORS['peaks_cents_above']
        else:
            x_end = freq
            x_start = freq / (1 + line_width * 0.001)
            color = COLORS['peaks_cents_below']
        
        # 绘制横线
        hline = self.ax.hlines(
            y=0,
            xmin=x_start,
            xmax=x_end,
            colors=color,
            linewidth=PEAK_LAYER_PARAMS['deviation_linewidth'],
            alpha=PEAK_LAYER_PARAMS['deviation_alpha'],
            zorder = PEAK_LAYER_PARAMS['zorder']
        )
        self.artifacts['lines'].append(hline)

    def clean(self):
        self.cache = []