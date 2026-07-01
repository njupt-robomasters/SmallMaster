#pragma once

#include "config.hpp"
#include "utils.hpp"
#include <cstdint>

class Gimbal {
  public:
    Gimbal(uint32_t (&hc595_buf)[HC595_BUF_LEN], uint8_t pitch_pin, uint8_t shoot_pin);

    void begin();

    void setEnable(bool is_enable);

    void setAngle(float angle);
    void setSpeed(float speed);

    void setContinueShoot(bool enable);
    void triggerSingleShoot();

    void setInject(float freq, float power);
    void disableInject();

    void onLoop();

  private:
    uint32_t (&m_hc595_buf)[HC595_BUF_LEN];
    const uint8_t m_pitch_pin, m_shoot_pin;

    bool m_is_enable = false;

    // 用于pitch匀速运动
    DT m_dt;
    float m_angle = 90;
    float m_speed = 0;

    // 用于发弹
    bool m_is_continue_shoot = false, m_is_single_shoot = false;
    float m_single_shoot_left_time = 0;

    // 用于音乐注入
    bool m_is_inject_enable = false;
    uint32_t m_cnt, m_arr = 0, m_ccr = 0;
};
