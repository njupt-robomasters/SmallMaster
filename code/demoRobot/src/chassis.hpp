#pragma once

#include <cstdint>
#include "utils.hpp"
#include "stepper.hpp"

class Chassis {
public:
    Chassis(Stepper &s1, Stepper &s2, Stepper &s3, Stepper &s4);

    void setEnable(bool is_enable);

    void setSpeed(float vx, float vy, float vrpm);

    void onLoop();

private:
    Stepper& m_s1, m_s2, m_s3, m_s4;

    DT m_dt;
    bool m_is_enable = false;
    float m_vx_target = 0, m_vy_target = 0, m_vr_target = 0;
    float m_vx = 0, m_vy = 0, m_vr = 0;

    void applyAcceleration(float &v, float v_target, float a, float dt);
};
