# config.py - 存放所有配置参数和常量
BASE_PARAMS = {
    # 设备状态检测间隔（单位：秒），控制检查音频设备插拔的频率
    'device_check_interval': 2,
    # 音频采样率（单位：Hz），标准CD音质采样率
    'default_sample_rate': 44100,
    # 音频块大小（单位：采样点数），影响实时处理的延迟和计算效率
    'chunk_size': 2048,
    # FFT窗口长度（单位：采样点数），决定频率分辨率（越大分辨率越高）
    'n_fft': 2048,
    # 分贝转换参考值，用于librosa.amplitude_to_db()计算相对dB值
    'ref_value': 1.0,
    # 频谱处理范围(Hz)
    'freq_range': (200, 4000),
    # 标准音高 (Hz)，可设为440.0或442.0等常用值
    'reference_pitch': 442.0,
    # 窗口尺寸
    'window_size': (1600, 900),
    # 图表绘制间隔
    'render_interval': 1 / 60,
    # 计算间隔
    'compute_interval': 1 / 100,
}

COLORS = {
    'spectrum_curve': 'darkorange',
    'peaks_line': 'pink',
    'peaks_hint_text': 'pink',
    'peaks_hint_text_box': 'gray',
    'peaks_cents_above': 'yellow',
    'peaks_cents_below': 'fuchsia',
    'melody_colormap': 'spring',
    'melody_reference_line': 'cyan',
}

# 频谱曲线层参数
SPECTRUM_CURVE_LAYER_PARAMS = {
    'visible': True,                # 是否显示该层
    'zorder': 0,                    # 图层顺序，值越大越上层
    'smoothed_curve': False,        # 是否显示为平滑曲线
    'amplitude_range': (-60, 60),   # 幅度显示范围(dB)
    'line_width': 0.5,              # 线宽
    'alpha': 0.7,                   # 透明度
}

# 峰值层参数
PEAK_LAYER_PARAMS = {
    'visible': True,            # 是否显示该层
    'zorder': 2,                # 图层顺序，值越大越上层
    'untishake_time_threshold': 0.1, # 峰值去抖动时间阈值（秒）
    'prominence': 20.0,          # 峰值最小突出度（单位：dB），用于排除微小波动
    'height': -50.0,            # 峰值最小高度（单位：dB），绝对幅度阈值
    'distance': 80.0,           # 峰值间最小间距（单位：插值后数组的索引数），防止邻近假峰
    'min_db': -40,              # 显示标注的最小分贝值，高于此值才会显示文字标注
    'min_freq': 100.0,          # 检测的最低频率（Hz）
    'max_freq': 4000.0,         # 检测的最高频率（Hz） 
    'volume_threshold': -50.0,  # 音量阈值（单位：dB），低于此值不显示峰值
    'dynamic_threshold': 0.72,  # 动态阈值参数 (0.7即70%)
    'db_offset': 60,            # 分贝值偏移量，用于峰值筛选
    'num': 5,                   # 显示的峰值数量
    'text_fontsize': 12,        # 文字大小
    'text_x_offset': 0.02,      # 文本水平偏移比例（基于对数坐标），控制文字与竖线间距
    'text_y_offset': 5,         # 文本垂直偏移比例（基于图表底部）
    'text_box_alpha': 0.3,      # 文本框透明度
    'deviation_max_width': 100, # 最大宽度（单位：点）
    'deviation_max_cent': 25,   # 最大音分范围（绝对值）
    'deviation_linewidth': 30,  # 线宽
    'deviation_alpha': 0.5,     # 透明度
}
# 旋律层参数
MELODY_LAYER_PARAMS = {
    'visible': True,
    'zorder': 1,                # 图层顺序，值越大越上层
    'time_window': 10,
    'volume_range': (-60, 0),
    'freq_range': (150, 3000),
    'point_size': 15,           # 调大点确保可见
    'alpha': 0.9,
    'main_peak_threshold': 0.5,
    'peak_db_offset': 50,
    'multiplication_tolerance': 0.05,
    'misjudgment_max_duration': 0.2,
    'reference_line_alpha': 0.1,
}