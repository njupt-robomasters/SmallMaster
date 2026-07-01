#pragma once

#include "config.hpp"
#include <cstdint>

class Stepper {
  public:
    Stepper(uint32_t (&hc595_buf)[HC595_BUF_LEN],
            uint8_t en_pin, uint8_t step_pin, uint8_t dir_pin,
            bool invert = false);

    void setEnable(bool is_enable);

    void setFreq(float freq);
    void setRPM(float rpm);

    void onLoop();

  private:
    uint32_t (&m_hc595_buf)[8];
    const uint8_t m_en_pin, m_dir_pin, m_step_pin;
    const bool m_invert;

    bool m_is_enable = false;
    uint32_t m_cnt = 0, m_arr = 0;
};
