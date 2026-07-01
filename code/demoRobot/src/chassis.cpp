#include "chassis.hpp"
#include "config.hpp"
#include <Arduino.h>

Chassis::Chassis(Stepper &s1, Stepper &s2, Stepper &s3, Stepper &s4) : m_s1(s1), m_s2(s2), m_s3(s3), m_s4(s4) {
}

void Chassis::setEnable(bool is_enable) {
    if (m_is_enable == is_enable)
        return;
    m_is_enable = is_enable;

    // 应用到每一个轮子
    m_s1.setEnable(is_enable);
    m_s2.setEnable(is_enable);
    m_s3.setEnable(is_enable);
    m_s4.setEnable(is_enable);
}

void Chassis::setSpeed(float vx, float vy, float vr) {
    m_vx_target = vx;
    m_vy_target = vy;
    m_vr_target = vr;
}

void Chassis::onLoop() {
    // 缓加速
    float dt = m_dt.update();
    applyAcceleration(m_vx, m_vx_target, AXY, dt);
    applyAcceleration(m_vy, m_vy_target, AXY, dt);
    applyAcceleration(m_vr, m_vr_target, AR, dt);

    // 底盘旋转角速度（单位：degree/s -> 底盘旋转线速度（单位：m/s）
    float vz = m_vr / 360 * (2 * M_PI * CHASSIS_RADIUS);

    // 底盘运动学解算（全部为标准单位：m/s）
    float s1 = sqrtf(0.5f) * (+m_vx + m_vy) + vz;
    float s2 = sqrtf(0.5f) * (-m_vx + m_vy) + vz;
    float s3 = sqrtf(0.5f) * (-m_vx - m_vy) + vz;
    float s4 = sqrtf(0.5f) * (+m_vx - m_vy) + vz;

    // 设置轮电机速度
    m_s1.setRPM(s1 / (2 * M_PI * WHEEL_RADIUS) * 60);
    m_s2.setRPM(s2 / (2 * M_PI * WHEEL_RADIUS) * 60);
    m_s3.setRPM(s3 / (2 * M_PI * WHEEL_RADIUS) * 60);
    m_s4.setRPM(s4 / (2 * M_PI * WHEEL_RADIUS) * 60);

    // 更新轮电机
    m_s1.onLoop();
    m_s2.onLoop();
    m_s3.onLoop();
    m_s4.onLoop();
}

void Chassis::applyAcceleration(float &v, float v_target, float a, float dt) {
    if (v_target > v) {
        v += a * dt;
        if (v > v_target)
            v = v_target;
    } else {
        v -= a * dt;
        if (v < v_target)
            v = v_target;
    }
}
