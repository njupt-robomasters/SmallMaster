#pragma once

#include "config.hpp"
#include <cstdint>

class HC595 {
  public:
    uint32_t buf[HC595_BUF_LEN];

    void begin();

    void onLoop();
};
