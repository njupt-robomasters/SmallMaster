#include "utils.hpp"
#include <Arduino.h>

float clampf(float x, float min_val, float max_val) {
    if (x < min_val)
        return min_val;
    if (x > max_val)
        return max_val;
    return x;
}

float mapf(float x, float in_min, float in_max, float out_min, float out_max) {
    float run = in_max - in_min;
    float rise = out_max - out_min;
    float delta = x - in_min;
    return (delta * rise) / run + out_min;
}

void setBit(uint32_t &data, uint8_t pos, bool val) {
    if (val) {
        data |= (1 << pos); // 设置位为1：使用 OR 操作
    } else {
        data &= ~(1 << pos); // 设置位为0：使用 AND 操作与取反
    }
}

bool getBit(uint32_t data, uint8_t pos) {
    return (data >> pos) & 1;
}

float DT::update() {
    uint32_t now_micros = micros();
    float dt = (now_micros - m_last_micros) / 1e6f;
    m_last_micros = now_micros;
    return dt;
}
