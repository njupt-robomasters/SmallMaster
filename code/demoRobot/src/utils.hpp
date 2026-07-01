#pragma once

#include <cstdint>

float clampf(float x, float min_val, float max_val);

float mapf(float x, float in_min, float in_max, float out_min, float out_max);

void setBit(uint32_t &data, uint8_t pos, bool val);

bool getBit(uint32_t data, uint8_t pos);

class DT {
public:
    float update();

private:
    uint32_t m_last_micros = 0;
};
