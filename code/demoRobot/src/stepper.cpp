#include "stepper.hpp"
#include "config.hpp"
#include "utils.hpp"
#include <Arduino.h>

Stepper::Stepper(uint32_t (&hc595_buf)[8],
                 uint8_t en_pin, uint8_t step_pin, uint8_t dir_pin,
                 bool invert) : m_hc595_buf(hc595_buf),
                                m_en_pin(en_pin), m_step_pin(step_pin), m_dir_pin(dir_pin),
                                m_invert(invert) {
    for (int i = 0; i < HC595_BUF_LEN; i++)
        setBit(m_hc595_buf[i], m_en_pin, 1);
}

void Stepper::setEnable(bool is_enable) {
    if (m_is_enable == is_enable)
        return;
    m_is_enable = is_enable;

    for (int i = 0; i < HC595_BUF_LEN; i++)
        setBit(m_hc595_buf[i], m_en_pin, !is_enable);
}

void Stepper::setFreq(float freq) {
    // 设置正反转
    bool dir = (freq > 0) ^ m_invert;
    for (int i = 0; i < HC595_BUF_LEN; i++)
        setBit(m_hc595_buf[i], m_dir_pin, dir);

    // 计算分频系数
    m_arr = HC595_UPDATE_FREQ / abs(freq);
}

void Stepper::setRPM(float rpm) {
    // 计算step脉冲频率
    float freq = rpm / 60 * (360 / 1.8) * STEPPER_DIVIDER;
    setFreq(freq);
}

void Stepper::onLoop() {
    // 产生step脉冲
    for (int i = 0; i < HC595_BUF_LEN; i++) {
        m_cnt++;
        if (m_cnt >= m_arr) {
            m_cnt = 0;
        }
        if (m_cnt < m_arr / 2) {
            setBit(m_hc595_buf[i], m_step_pin, 0);
        } else {
            setBit(m_hc595_buf[i], m_step_pin, 1);
        }
    }
}
