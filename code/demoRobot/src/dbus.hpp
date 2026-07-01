#pragma once

#include <cstdint>

class DBUS {
  public:
    // 鼠标移动速度，归一化到±1
    float mouse_x = 0; // 鼠标X轴
    float mouse_y = 0; // 鼠标Y轴
    float mouse_z = 0; // 鼠标滚轮

    // 鼠标按键状态 (false-未按下, true-按下)
    bool left_button = false;  // 鼠标左键
    bool right_button = false; // 鼠标右键

    // 键盘按键状态 (false-未按下, true-按下)
    bool w = false, s = false, a = false, d = false;
    bool q = false, e = false;
    bool shift = false, ctrl = false;

    // DBUS连接状态
    bool is_connected = false;

    // 解析10字节数据包
    void parseData(const uint8_t data[10]) {
        // 解析鼠标X轴 (2字节，有符号)
        mouse_x = (int16_t)(data[0] | (data[1] << 8)) / 32768.0f;

        // 解析鼠标Y轴 (2字节，有符号)
        mouse_y = (int16_t)(data[2] | (data[3] << 8)) / 32768.0f;

        // 解析鼠标Z轴 (2字节，有符号)
        mouse_z = (int16_t)(data[4] | (data[5] << 8)) / 32768.0f;

        // 解析鼠标左键 (1字节，布尔值)
        left_button = data[6] & 1;

        // 解析鼠标右键 (1字节，布尔值)
        right_button = data[7] & 1;

        // 解析按键状态 (1字节，位图)
        w = (data[8] >> 0) & 1;
        s = (data[8] >> 1) & 1;
        a = (data[8] >> 2) & 1;
        d = (data[8] >> 3) & 1;
        q = (data[8] >> 4) & 1;
        e = (data[8] >> 5) & 1;
        shift = (data[8] >> 6) & 1;
        ctrl = (data[8] >> 7) & 1;

        // 解析DBUS连接状态 (1字节，布尔值)
        is_connected = data[9] & 1;
    }
};
