import mido
import math
import os

def note_number_to_frequency(note_number):
    """将MIDI音符编号转换为频率（Hz）"""
    return round(440 * math.pow(2, (note_number - 69) / 12.0))

def parse_midi_file(filename, track_number=0):
    """解析MIDI文件，提取指定音轨的音符频率和持续时间"""
    # 打开MIDI文件
    mid = mido.MidiFile(filename)
    
    # 检查音轨编号是否有效
    if track_number >= len(mid.tracks):
        raise ValueError(f"音轨编号 {track_number} 无效，文件只有 {len(mid.tracks)} 个音轨")
    
    # 首先在所有音轨中查找初始速度
    tempo = None
    for track in mid.tracks:
        for msg in track:
            if msg.type == 'set_tempo':
                tempo = msg.tempo
                break
        if tempo is not None:
            break
    
    # 如果没有找到速度信息，使用默认值（120 BPM）
    if tempo is None:
        tempo = 500000  # 500000 μs/beat = 120 BPM
    
    # 获取指定音轨
    track = mid.tracks[track_number]
    
    # 存储当前按下的音符及其开始时间
    active_notes = {}  # {note_number: start_time}
    # 存储结果：频率和持续时间
    frequencies = []
    durations = []  # 单位为毫秒
    
    # 当前时间（以秒为单位）
    current_time = 0.0
    # 上一个音符结束时间
    last_note_end_time = 0.0
    
    # 遍历指定音轨的所有MIDI消息
    for msg in track:
        # 更新时间（将ticks转换为秒）
        delta_time_seconds = mido.tick2second(msg.time, mid.ticks_per_beat, tempo)
        current_time += delta_time_seconds
        
        if msg.type == 'note_on' and msg.velocity > 0:
            # 音符按下事件
            if not active_notes:  # 如果没有其他音符正在演奏
                # 检查是否有间隔（空格）
                if current_time > last_note_end_time:
                    # 计算间隔时间（毫秒）
                    gap_duration = round((current_time - last_note_end_time) * 1000)
                    if gap_duration > 0:
                        frequencies.append(0)  # 0表示空格
                        durations.append(gap_duration)
                
                active_notes[msg.note] = current_time
            else:
                # 已经有音符在播放，比较频率
                current_note = next(iter(active_notes.keys()))  # 获取当前播放的音符
                if msg.note > current_note:  # 新音符频率更高
                    # 结束当前音符
                    start_time = active_notes[current_note]
                    duration_seconds = current_time - start_time
                    
                    frequency = note_number_to_frequency(current_note)
                    duration_ms = round(duration_seconds * 1000)
                    
                    # 只添加持续时间大于0的音符
                    if duration_ms > 0:
                        frequencies.append(frequency)
                        durations.append(duration_ms)
                    last_note_end_time = current_time
                    
                    # 开始新音符
                    active_notes = {msg.note: current_time}
                # 如果新音符频率更低，则忽略它，继续播放当前音符
                
        elif msg.type == 'note_off' or (msg.type == 'note_on' and msg.velocity == 0):
            # 音符释放事件
            if msg.note in active_notes:
                start_time = active_notes[msg.note]
                duration_seconds = current_time - start_time
                
                # 转换为频率和持续时间
                frequency = note_number_to_frequency(msg.note)
                duration_ms = round(duration_seconds * 1000)  # 转换为毫秒
                
                # 只添加持续时间大于0的音符
                if duration_ms > 0:
                    # 添加到结果数组
                    frequencies.append(frequency)
                    durations.append(duration_ms)
                    
                    # 更新最后一个音符结束时间
                    last_note_end_time = current_time
                
                # 从活跃音符中移除
                del active_notes[msg.note]
        
        elif msg.type == 'set_tempo':
            # 处理速度变化
            tempo = msg.tempo
    
    return frequencies, durations

def list_tracks(filename):
    """列出MIDI文件中的所有音轨"""
    mid = mido.MidiFile(filename)
    print(f"\nMIDI文件 '{os.path.basename(filename)}' 包含 {len(mid.tracks)} 个音轨:")
    print("-" * 60)
    
    for i, track in enumerate(mid.tracks):
        # 统计音轨中的音符事件数量
        note_on_count = sum(1 for msg in track if msg.type == 'note_on' and msg.velocity > 0)
        note_off_count = sum(1 for msg in track if msg.type == 'note_off' or (msg.type == 'note_on' and msg.velocity == 0))
        
        # 获取音轨名称
        track_name = "未命名"
        for msg in track:
            if msg.type == 'track_name':
                track_name = msg.name
                break
        
        # 获取乐器信息（如果有）
        instrument = "未知"
        for msg in track:
            if msg.type == 'program_change':
                instrument = f"乐器#{msg.program}"
                break
        
        print(f"音轨 {i}: '{track_name}'")
        print(f"  乐器: {instrument}")
        print(f"  事件总数: {len(track)}")
        print(f"  音符按下事件: {note_on_count}")
        print(f"  音符释放事件: {note_off_count}")
        print("-" * 60)

def get_midi_files_in_directory():
    """获取当前目录下的所有MIDI文件"""
    midi_files = []
    for file in os.listdir('.'):
        if file.lower().endswith(('.mid', '.midi')):
            midi_files.append(file)
    return midi_files

def main():
    print("MIDI文件解析器 - 音符频率和持续时间提取")
    print("=" * 50)
    
    # 显示当前目录下的MIDI文件
    midi_files = get_midi_files_in_directory()
    
    if midi_files:
        print("\n当前目录下的MIDI文件:")
        for i, file in enumerate(midi_files, 1):
            print(f"{i}. {file}")
        print("0. 手动输入文件名")
    else:
        print("\n目录下未找到MIDI文件")
        print("0. 手动输入文件名")
    
    # 选择文件
    try:
        choice = input("\n请选择文件编号（输入0手动输入文件名）: ")
        
        if choice == '0':
            filename = input("请输入MIDI文件路径: ").strip()
            # 移除可能的引号
            filename = filename.strip('"\'')
        else:
            index = int(choice) - 1
            if 0 <= index < len(midi_files):
                filename = midi_files[index]
            else:
                print("无效的选择!")
                return
                
        # 检查文件是否存在
        if not os.path.exists(filename):
            print(f"错误：文件 '{filename}' 不存在!")
            return
            
        # 列出所有音轨
        list_tracks(filename)
        
        # 选择音轨
        mid = mido.MidiFile(filename)
        track_count = len(mid.tracks)
        
        while True:
            try:
                track_input = input(f"\n请选择要处理的音轨编号 (0-{track_count-1}), 或输入 'q' 退出: ")
                
                if track_input.lower() == 'q':
                    print("程序退出")
                    return
                
                track_number = int(track_input)
                
                if 0 <= track_number < track_count:
                    break
                else:
                    print(f"音轨编号必须在 0 到 {track_count-1} 之间!")
                    
            except ValueError:
                print("请输入有效的数字!")
        
        # 解析选定的音轨
        print(f"\n正在解析音轨 {track_number}...")
        frequencies, durations = parse_midi_file(filename, track_number)
        
        # 转换为逗号分隔的字符串（整数格式）
        freq_str = ', '.join([str(f) for f in frequencies])
        dur_str = ', '.join([str(d) for d in durations])
        
        print(f"\n音轨 {track_number} 的频率数组（Hz, 0表示空格）:")
        print(freq_str)
        print(f"\n音轨 {track_number} 的持续时间数组（毫秒）:")
        print(dur_str)
        
        # 打印统计信息
        total_notes = sum(1 for f in frequencies if f > 0)
        total_silence = sum(1 for f in frequencies if f == 0)
        total_duration = sum(durations)
        
        print(f"\n统计信息:")
        print(f"音符数量: {total_notes}")
        print(f"空格数量: {total_silence}")
        print(f"总事件数量: {len(frequencies)}")
        print(f"总持续时间: {total_duration} 毫秒 ({total_duration/1000:.2f} 秒)")
        
        # 询问是否保存到文件
        save_choice = input("\n是否将结果保存到文件? (y/n): ").lower()
        if save_choice == 'y':
            output_filename = f"track_{track_number}_output.txt"
            with open(output_filename, 'w', encoding='utf-8') as f:
                f.write(f"MIDI文件: {filename}\n")
                f.write(f"音轨: {track_number}\n\n")
                f.write("频率数组（Hz, 0表示空格）:\n")
                f.write(freq_str + "\n")
                f.write("持续时间数组（毫秒）:\n")
                f.write(dur_str + "\n\n")
                f.write(f"音符数量: {total_notes}\n")
                f.write(f"空格数量: {total_silence}\n")
                f.write(f"总事件数: {len(frequencies)}\n")
                f.write(f"总持续时间: {total_duration} 毫秒\n")
            print(f"结果已保存到 '{output_filename}'")
        
    except KeyboardInterrupt:
        print("\n用户中断程序")
    except FileNotFoundError:
        print(f"错误：找不到文件 '{filename}'")
    except ValueError as e:
        print(f"错误: {e}")
    except Exception as e:
        print(f"处理MIDI文件时出错: {e}")

if __name__ == "__main__":
    main()