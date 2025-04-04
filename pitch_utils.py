# pitch_utils.py
import numpy as np
import re

class PitchConverter:
    def __init__(self, reference=442.0):
        """
        初始化音高转换器
        :param reference: 基准音高（A4的频率），默认为442Hz
        """
        self.reference = reference
        self.note_names = ['C', 'C#', 'D', 'D#', 'E', 'F', 'F#', 'G', 'G#', 'A', 'A#', 'B']
    
    def frequency_to_midi(self, freq):
        """将频率转换为MIDI音符编号（关键修正点）"""
        if freq <= 0:
            return 0
        return 12 * np.log2(freq / self.reference) + 69
    
    def midi_to_note(self, midi_num):
        """将MIDI编号转换为音名（含八度）"""
        octave = (midi_num // 12) - 1
        note_index = int(round(midi_num)) % 12
        return f"{self.note_names[note_index]}{octave}"
    
    def get_nearest_pitch_info(self, freq):
        """
        获取最近音高信息（修正计算逻辑）
        :param freq: 输入频率（Hz）
        :return: (音名, 音分差)
        """
        if freq < 20 or freq > 14000 or self.reference <= 0:
            return ("", 0)
        
        try:
            # 计算最接近的MIDI编号
            midi_num = self.frequency_to_midi(freq)
            nearest_midi = int(round(midi_num))
            
            # 计算标准频率
            reference_freq = self.reference * (2 ** ((nearest_midi - 69)/12))
            
            # 计算音分差（增加保护条件）
            if reference_freq <= 0:
                return ("", 0)
                
            cent_diff = 1200 * np.log2(freq / reference_freq)
            cent_diff = int(round(cent_diff))
            
            # 生成音名
            note_name = self.midi_to_note(nearest_midi)
            return (note_name, cent_diff)
        except Exception as e:
            print(f"音高计算错误: {str(e)}")
            return ("", 0)
        
    def note_to_freq(self, note_str):
        """
        将音名（如'A4', 'C#3'）转换为对应的频率
        :param note_str: 音名字符串，例如 'C#4'
        :return: 对应频率（Hz）
        :raises ValueError: 如果格式无效或音名不存在
        """
        match = re.match(r"^([A-Ga-g](?:#|b)?)(-?\d+)$", note_str, re.IGNORECASE)
        if not match:
            raise ValueError(f"Invalid note format: '{note_str}'")

        note_part = match.group(1).upper()
        octave = int(match.group(2))

        try:
            note_index = self.note_names.index(note_part)
        except ValueError:
            raise ValueError(f"Note '{note_part}' not recognized. Valid notes are: {self.note_names}")

        midi_num = (octave + 1) * 12 + note_index
        freq = self.reference * (2 ** ((midi_num - 69) / 12))
        return freq