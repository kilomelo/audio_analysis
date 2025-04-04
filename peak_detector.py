# peak_detector.py
import numpy as np
from scipy.interpolate import interp1d
from scipy.signal import find_peaks
from config import SPECTRUM_CURVE_LAYER_PARAMS, PEAK_LAYER_PARAMS

class PeakDetector:
    def __init__(self, x_subband, x_new):
        """
        初始化峰值检测器
        :param x_subband: 原始FFT频率轴（筛选后）
        :param x_new: 插值后的对数频率轴
        """
        if x_subband is None or x_new is None:
            raise ValueError("频率轴参数不能为None")
        if not isinstance(x_subband, np.ndarray) or not isinstance(x_new, np.ndarray):
            raise TypeError("频率轴必须是numpy数组")
        self.x_subband = x_subband
        self.x_new = x_new
        self.freq_step = x_subband[1] - x_subband[0]  # 频率分辨率
        
    def _parabolic_interpolation(self, sub_idx, db_subband):
        """抛物线插值计算精确频率"""
        y0, y1, y2 = (
            db_subband[sub_idx-1],
            db_subband[sub_idx],
            db_subband[sub_idx+1]
        )
        delta = 0.5 * (y0 - y2) / (y0 - 2*y1 + y2 + 1e-9)
        delta = np.clip(delta, -0.5, 0.5)
        return self.x_subband[sub_idx] + delta * self.freq_step
    
    def detect_peaks(self, interp_data, db_subband):
        """
        执行峰值检测
        :param interp_data: 插值后的频谱数据（包含smooth/raw）
        :param db_subband: 原始子带频谱数据（用于精确计算）
        :return: 排序后的峰值列表 [(freq, dB), ...]
        """
        # 选择数据源
        data_source = interp_data['raw']
        
        # 频段筛选
        freq_mask = (self.x_new >= PEAK_LAYER_PARAMS['min_freq']) & \
            (self.x_new <= PEAK_LAYER_PARAMS['max_freq'])
        valid_x = self.x_new[freq_mask]
        valid_db = data_source[freq_mask]

        # 峰值检测
        try:
            peaks, properties = find_peaks(
                valid_db,
                prominence=PEAK_LAYER_PARAMS['prominence'],
                height=PEAK_LAYER_PARAMS['height'],
                distance=PEAK_LAYER_PARAMS['distance']
            )
        except Exception as e:
            raise RuntimeError(f"Peak detection failed: {str(e)}")

        # 获取所有峰值的频率和幅度（原始分贝值）
        peak_indices = peaks
        peak_freqs = valid_x[peak_indices]
        original_heights = valid_db[peak_indices]
        
        # 按频率从高到低排序（降序）
        sort_idx = np.argsort(peak_freqs)[::-1]
        sorted_heights = original_heights[sort_idx]
        sorted_freqs = peak_freqs[sort_idx]
        sorted_indices = peak_indices[sort_idx]
        
        # 动态筛选（严格比较原始分贝值）
        filtered_indices = []
        prev_height = None
        
        for i, (idx, h) in enumerate(zip(sorted_indices, sorted_heights)):
            h = h + PEAK_LAYER_PARAMS['db_offset']
            if i == 0:
                # 第一个峰值强制保留
                filtered_indices.append(idx)
                prev_height = h  # 记录原始分贝值
                continue
                
            # 关键逻辑：当前分贝值 >= 前一个峰值的分贝值 * dynamic_threshold
            if h >= prev_height * PEAK_LAYER_PARAMS['dynamic_threshold']:
                filtered_indices.append(idx)
                prev_height = h  # 更新为当前分贝值
        # 转换回原始peaks索引顺序
        mask = np.isin(peak_indices, filtered_indices)
        dynamic_filtered_peaks = peak_indices[mask]

        # 筛选显著峰值
        valid_mask = (properties["prominences"] > PEAK_LAYER_PARAMS['prominence']) & \
            (properties["peak_heights"] > PEAK_LAYER_PARAMS['min_db'])
        valid_mask = valid_mask & np.isin(peaks, dynamic_filtered_peaks)
        valid_peaks = peaks[valid_mask]

        precise_data = []
        for peak_idx in valid_peaks:
            approx_freq = valid_x[peak_idx]
            nearest_sub = np.argmin(np.abs(self.x_subband - approx_freq))
            sub_idx = np.clip(nearest_sub, 1, len(self.x_subband)-2)
            
            # 计算精确频率
            precise_freq = self._parabolic_interpolation(sub_idx, db_subband)
            
            # 获取显示dB值
            precise_db = np.interp(
                precise_freq, 
                self.x_new, 
                interp_data['smooth' if SPECTRUM_CURVE_LAYER_PARAMS['smoothed_curve'] else 'raw']
            )
            precise_data.append((precise_freq, precise_db))

        # 筛选并排序
        return self._sort_peaks(precise_data)
    
    def _sort_peaks(self, peaks):
        """排序策略：按幅度取前PEAK_LAYER_PARAMS['num']，然后按频率排序"""
        sorted_by_amplitude = sorted(peaks, key=lambda x: x[1], reverse=True)[:PEAK_LAYER_PARAMS['num']]
        return sorted(sorted_by_amplitude, key=lambda x: x[0])