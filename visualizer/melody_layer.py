# visualizer/melody_layer.py
import numpy as np
from config import COLORS, MELODY_LAYER_PARAMS, BASE_PARAMS
from visualizer.base_layer import BaseLayer
from pitch_utils import PitchConverter

class MelodyLayer(BaseLayer):
    def __init__(self):
        super().__init__()
        self.times = []
        self.freqs = []
        self.volumes = []
        self.scatter = None
        self.ax = None
        self.time_window = MELODY_LAYER_PARAMS['time_window']
        self.possible_misjudgment_peak_time = None
        self.possible_misjudgment_peak_freq = None
        self.reference_lines = []
        self.show_reference = True
        self.redraw_ref_lines = True
        self.dynamic_freq_range = True
        self.pitch_converter = PitchConverter(reference=BASE_PARAMS['reference_pitch'])
        self.target_ylim_min_midi = self.pitch_converter.frequency_to_midi(MELODY_LAYER_PARAMS['freq_range'][0])
        self.target_ylim_max_midi = self.pitch_converter.frequency_to_midi(MELODY_LAYER_PARAMS['freq_range'][1])
        self.bind_param('show_ref_lines', self.set_show_reference, self.get_show_reference)
        self.bind_param('melody_dynamic_freq_range', self.set_dynamic_freq_range, self.get_dynamic_freq_range)

    def initialize(self, fig, position):
        self.ax = fig.add_axes(position, frameon=False)
        self.ax.set_xscale('linear')
        self.ax.set_yscale('log')
        self.ax.set_xlim(-MELODY_LAYER_PARAMS['time_window'], 0)
        self.ax.set_ylim(self.pitch_converter.midi_to_frequency(self.target_ylim_min_midi), self.pitch_converter.midi_to_frequency(self.target_ylim_max_midi))
        self.scatter = self.ax.scatter(
            [], [], 
            c=[], 
            cmap=COLORS['melody_colormap'],
            vmin=MELODY_LAYER_PARAMS['volume_range'][0],
            vmax=MELODY_LAYER_PARAMS['volume_range'][1],
            alpha=MELODY_LAYER_PARAMS['alpha'],
            edgecolors='none',
            s=MELODY_LAYER_PARAMS['point_size'],
            zorder=0
        )
    def draw_reference_line(self, base_freq=440):
        """带可见性控制的参考线绘制方法"""
        self.redraw_ref_lines = False
        # 清空旧参考线（避免重复绘制）
        for line in self.reference_lines:
            line.remove()
        self.reference_lines.clear()
        
        # 计算半音频率范围
        semitone_ratios = 2 ** (np.arange(-50, 50.1, 100)/1200)  # ±50音分范围[3,5](@ref)
        ymin, ymax = self.ax.get_ylim()
        
        for semitone in range(-48, 49):
            if (semitone%2 == 0): continue
            # 计算中心频率[1,2](@ref)
            center_freq = base_freq * (2 ** (semitone/12))
            
            # 计算频率边界[3,5](@ref)
            freq_band = [center_freq * r for r in semitone_ratios]
            lower_edge = min(freq_band)
            upper_edge = max(freq_band)
            if upper_edge < ymin or lower_edge > ymax: continue
            
            # 绘制并存储参考线对象[3,5](@ref)
            ref_line = self.ax.axhspan(lower_edge, upper_edge,
                color=COLORS['melody_reference_line'], 
                alpha=MELODY_LAYER_PARAMS['reference_line_alpha'],
                linewidth=0,
                zorder=-10,
                animated=True)
            ref_line.set_visible(self.show_reference)
            self.reference_lines.append(ref_line)
            
    def set_show_reference(self, value):
        if self.show_reference != value:
            self.show_reference = value
            # 批量设置可见性（比重新绘制更高效）[3,5](@ref)
            for line in self.reference_lines:
                line.set_visible(self.show_reference)

    def get_show_reference(self):
        return self.show_reference
    
    def set_dynamic_freq_range(self, value):
        if self.dynamic_freq_range != value:
            self.dynamic_freq_range = value
            if not self.dynamic_freq_range:
                self.target_ylim_min_midi = self.pitch_converter.frequency_to_midi(MELODY_LAYER_PARAMS['freq_range'][0])
                self.target_ylim_max_midi = self.pitch_converter.frequency_to_midi(MELODY_LAYER_PARAMS['freq_range'][1])
                self.ax.set_ylim(*MELODY_LAYER_PARAMS['freq_range'])
                self.redraw_ref_lines = True
            else:
                self.calculate_target_ylim()

    def get_dynamic_freq_range(self):
        return self.dynamic_freq_range
    
    def process(self, chunk, data_protocol):
        current_time = data_protocol.current_time
        peaks = data_protocol.peaks
        volume = data_protocol.volume
        # 过滤无效时间
        if current_time <= 0: return

        # 时间窗口动态调整
        visible_start = current_time - self.time_window
        self.ax.set_xlim(visible_start, current_time)  # 保证最小值
        has_new_melody = False
        # 添加新数据点
        for i, (freq, db) in enumerate(peaks):
            # 取频率最低的主峰作为旋律音高
            if i == len(peaks) - 1 or \
                (db + MELODY_LAYER_PARAMS['peak_db_offset']) > MELODY_LAYER_PARAMS['main_peak_threshold'] * (peaks[i + 1][1] + MELODY_LAYER_PARAMS['peak_db_offset']):
                self.times.append(current_time)
                self.freqs.append(freq)
                self.volumes.append(volume)
                has_new_melody = True
                break

        # 限制数据存储量
        outdated = False
        cutoff = current_time - self.time_window
        valid_indices = [i for i, t in enumerate(self.times) if t >= cutoff and t <= current_time]
        if valid_indices:
            start_idx = valid_indices[0]
            self.times = self.times[start_idx:]
            self.freqs = self.freqs[start_idx:]
            self.volumes = self.volumes[start_idx:]
            if start_idx != 0: outdated = True
        else:
            self.times.clear()
            self.freqs.clear()
            self.volumes.clear()

        if has_new_melody and len(self.freqs) > 1:
            # 因为可能存在旋律音的倍频被错误判断为旋律的情况，所以需要识别这种错误判断的开始和结束
            multiplication = self.is_frequency_multiplication_relationship(self.freqs[-2], self.freqs[-1], MELODY_LAYER_PARAMS['multiplication_tolerance'])
            if multiplication != 0:
                if abs(multiplication) != 1:
                    if None == self.possible_misjudgment_peak_freq:
                        # print(f'misjudgment start, time: {current_time:.1f}, former freq: {self.freqs[-2]:.1f}, current freq: {self.freqs[-1]:.1f}, multiplication: {multiplication}, len: {len(self.freqs)}')
                        self.possible_misjudgment_peak_time = self.times[-2]
                        self.possible_misjudgment_peak_freq = self.freqs[-2]
                    else:
                        # 又回到了异常频率的初始音高，则大概率是误判了
                        regress_multiplication = self.is_frequency_multiplication_relationship(self.possible_misjudgment_peak_freq, self.freqs[-1], MELODY_LAYER_PARAMS['multiplication_tolerance'])
                        if abs(regress_multiplication) == 1:
                            # print(f'misjudgment end, peak time: {self.possible_misjudgment_peak_time:.1f}, freq: {self.possible_misjudgment_peak_freq:.1f}, duration: {current_time - self.possible_misjudgment_peak_time:.2f}, regress multiplication: {regress_multiplication}, len: {len(self.freqs)}')
                            self.fix_misjudgment()
                        # else:
                            # print(f'misjudgment continue with another freq, time: {current_time:.1f}, freq: {self.freqs[-1]:.1f}, regress multiplication: {regress_multiplication}, len: {len(self.freqs)}')
                # elif None != self.possible_misjudgment_peak_freq:
                    # print(f'misjudgment continue, time: {current_time:.1f}, freq: {self.freqs[-1]:.1f}, multiplication: {multiplication}, len: {len(self.freqs)}')

            elif None != self.possible_misjudgment_peak_freq:
                self.possible_misjudgment_peak_time = None
                self.possible_misjudgment_peak_freq = None
                # print('misjudgment false')
            # 音高切换的时间大于阈值，则结束误判记录状态，阈值需要根据实际演奏的乐曲来设定，如果乐曲中没有较短的八度、十二度、十五度的叠音、颤音等装饰音，则可以适当调大阈值
            if self.possible_misjudgment_peak_freq != None:
                if current_time - self.possible_misjudgment_peak_time > MELODY_LAYER_PARAMS['misjudgment_max_duration']:
                    self.possible_misjudgment_peak_time = None
                    self.possible_misjudgment_peak_freq = None
                    # print(f'misjudgment timeout, len: {len(self.freqs)}')

        if self.dynamic_freq_range:
            # 有新数据或有旧数据过期时需要重新设置 y 轴范围
            if has_new_melody or outdated:
                self.calculate_target_ylim()
            current_ylim = self.ax.get_ylim()
            current_ylim_min_midi = self.pitch_converter.frequency_to_midi(current_ylim[0])
            current_ylim_max_midi = self.pitch_converter.frequency_to_midi(current_ylim[1])
            need_reset_ylim = False
            actual_ylim_min_midi = current_ylim_min_midi
            actual_ylim_max_midi = current_ylim_max_midi
            if abs(current_ylim_min_midi - self.target_ylim_min_midi) > 0.2:
                need_reset_ylim = True
                actual_ylim_min_midi = current_ylim_min_midi + (self.target_ylim_min_midi - current_ylim_min_midi) * MELODY_LAYER_PARAMS['freq_range_fade_speed']
            if abs(current_ylim_max_midi - self.target_ylim_max_midi) > 0.2:
                need_reset_ylim = True
                actual_ylim_max_midi = current_ylim_max_midi + (self.target_ylim_max_midi - current_ylim_max_midi) * MELODY_LAYER_PARAMS['freq_range_fade_speed']
            if need_reset_ylim:
                self.ax.set_ylim(self.pitch_converter.midi_to_frequency(actual_ylim_min_midi), self.pitch_converter.midi_to_frequency(actual_ylim_max_midi))
                self.redraw_ref_lines = True
    def calculate_target_ylim(self):
        min_freq = max(min(self.freqs), MELODY_LAYER_PARAMS['freq_range'][0])
        max_freq = min(max(self.freqs), MELODY_LAYER_PARAMS['freq_range'][1])
        self.target_ylim_min_midi = int(round(self.pitch_converter.frequency_to_midi(min_freq))) - 8
        self.target_ylim_max_midi = int(round(self.pitch_converter.frequency_to_midi(max_freq))) + 4
    def draw(self, data_protocol):
        if not MELODY_LAYER_PARAMS['visible']: return []
        # 更新图形数据
        if self.times:
            self.scatter.set_offsets(np.column_stack([self.times, self.freqs]))
            self.scatter.set_array(np.array(self.volumes))
        else:
            self.scatter.set_offsets(np.empty((0, 2)))
            self.scatter.set_array(np.array([]))

        if self.redraw_ref_lines:
            self.draw_reference_line(BASE_PARAMS['reference_pitch'])

        return [self.scatter] + self.reference_lines
    
    def clean(self):
        self.times = []
        self.freqs = []
        self.volumes = []

    def is_frequency_multiplication_relationship(self, freq1, freq2, tolerance):
        """
        判断两个频率是否存在直接或间接的倍频关系，基于5倍范围内的整数倍率关系。
        :param freq1: 频率1（单位：Hz）
        :param freq2: 频率2（单位：Hz）
        :param tolerance: 容忍度，允许的频率比值的误差范围
        :return: 若存在倍频关系，返回符号化的比值（绝对值≥1，正负号表示大小关系）；否则返回0
        """
        # 排除零频率的情况
        if freq1 == 0 or freq2 == 0:
            return 0

        # 确定较大和较小的频率，并计算比值（确保ratio >= 1）
        larger, smaller = (freq1, freq2) if freq1 > freq2 else (freq2, freq1)
        ratio = larger / smaller

        # 预生成所有有效比值集合（k1/k2，其中k1∈[1,5], k2∈[1,k1]）
        valid_ratios = set()
        for k1 in range(1, 6):
            for k2 in range(1, k1 + 1):
                valid_ratios.add(k1 / k2)

        # 寻找最接近的有效比值
        closest_ratio = None
        min_diff = float('inf')
        for candidate in valid_ratios:
            current_diff = abs(ratio - candidate)
            if current_diff < min_diff:
                min_diff = current_diff
                closest_ratio = candidate

        # 判断是否在容忍度范围内
        if min_diff <= tolerance:
            # 根据原始顺序确定符号
            sign = 1 if freq1 > freq2 else -1
            return sign * closest_ratio
        else:
            return 0
    def fix_misjudgment(self):
        """
        修复误判的旋律音
        """
        if self.possible_misjudgment_peak_freq == None or len(self.freqs) < 3:
            return
        for i in range(0, len(self.freqs)):
            freq = self.freqs[-i-2]
            time = self.times[-i-2]
            multiplication = self.is_frequency_multiplication_relationship(self.possible_misjudgment_peak_freq, freq, MELODY_LAYER_PARAMS['multiplication_tolerance'])
            if multiplication == 0:
                # print(f'warning: try to fix non multiplication relationship data, time: {time:.1f}, freq: {freq:.1f}, len: {len(self.freqs)}')
                continue
            if abs(multiplication) == 1:
                # 修复完成
                # print(f'fix done, total point fixed: {i}')
                break
            else:
                fixed = freq * multiplication if multiplication > 0 else freq / abs(multiplication)
                # print(f'fixing, time: {time:.1f}, freq: {freq:.1f}, multiplication: {multiplication:.1f}, fixed: {fixed:.1f}')
                self.freqs[-i-2] = fixed
        self.possible_misjudgment_peak_time = None
        self.possible_misjudgment_peak_freq = None