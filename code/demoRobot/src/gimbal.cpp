#include "gimbal.hpp"
#include "config.hpp"
#include "utils.hpp"
#include <Arduino.h>

Gimbal::Gimbal(uint32_t (&hc595_buf)[HC595_BUF_LEN], uint8_t pitch_pin, uint8_t shoot_pin) : m_hc595_buf(hc595_buf), m_pitch_pin(pitch_pin), m_shoot_pin(shoot_pin) {
}

void Gimbal::begin() {
    ledcSetup(0, 50, 10);
    ledcAttachPin(m_pitch_pin, 0);
    ledcWrite(0, 0); // 舵机失能
}

void Gimbal::setEnable(bool is_enable) {
    if (m_is_enable == is_enable)
        return;
    m_is_enable = is_enable;

    if (is_enable) {
        // 舵机使能后默认回中
        setAngle(90);
    } else {
        // 舵机失能
        ledcWrite(0, 0);

        // 关闭发射
        m_is_continue_shoot = false;
        m_is_single_shoot = false;
        m_single_shoot_left_time = 0;
    }
}

void Gimbal::setAngle(float angle) {
    if (m_is_enable == false)
        return;
    angle = clampf(angle, 0, 180);
    uint32_t duty = mapf(angle, 0, 180, 0.5 / 20 * 1023, 2.5 / 20 * 1023);
    ledcWrite(0, duty);
}

// 设置pitch速度，单位：degree/s
void Gimbal::setSpeed(float speed) {
    m_speed = speed;
}

void Gimbal::setContinueShoot(bool is_enable) {
    m_is_continue_shoot = is_enable;
}

void Gimbal::triggerSingleShoot() {
    m_is_single_shoot = true;
    m_single_shoot_left_time = SINGLE_SHOOT_TIME;
}

void Gimbal::setInject(float freq, float power) {
    m_is_inject_enable = true;
    m_arr = HC595_UPDATE_FREQ / freq;
    m_ccr = m_arr * power;
}

void Gimbal::disableInject() {
    m_is_inject_enable = false;
}

void Gimbal::onLoop() {
    // 维护dt
    float dt = m_dt.update();

    // 云台匀速运动控制
    m_angle += m_speed * dt;
    m_angle = clampf(m_angle, PITCH_ANGLE_MIN, PITCH_ANGLE_MAX);
    setAngle(m_angle);

    // 单发控制
    if (m_single_shoot_left_time > 0) {
        m_single_shoot_left_time -= dt;
    }

    if (m_is_inject_enable) {
        // 优先音乐注入，注入期间不允许发射
        for (uint8_t i = 0; i < HC595_BUF_LEN; i++) {
            m_cnt++;
            if (m_cnt >= m_arr)
                m_cnt = 0;
            if (m_cnt < m_ccr) {
                setBit(m_hc595_buf[i], m_shoot_pin, true);
            } else {
                setBit(m_hc595_buf[i], m_shoot_pin, false);
            }
        }
    } else if (m_is_continue_shoot) {
        for (int i = 0; i < HC595_BUF_LEN; i++)
            setBit(m_hc595_buf[i], m_shoot_pin, true);
    } else if (m_is_single_shoot && m_single_shoot_left_time > 0) {
        for (int i = 0; i < HC595_BUF_LEN; i++)
            setBit(m_hc595_buf[i], m_shoot_pin, true);
    } else {
        for (int i = 0; i < HC595_BUF_LEN; i++)
            setBit(m_hc595_buf[i], m_shoot_pin, false);
    }
}
