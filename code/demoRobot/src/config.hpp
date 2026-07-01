#pragma once

// 硬件结构参数
#define STEPPER_DIVIDER 8    // 步进电机驱动细分数
#define CHASSIS_RADIUS 0.130 // 底盘半径，单位：m
#define WHEEL_RADIUS 0.0515  // 轮子半径，单位：m

// 底盘
#define VXY_MAX 1  // 底盘平移速度，单位：m/s
#define VR_MAX 180 // 底盘旋转速度：单位：degree/s
#define AXY 2      // 底盘平移加速度，单位：m/s^2
#define AR 360     // 底盘旋转加速度，单位：degree/s^2

// 云台
#define PITCH_ANGLE_MIN 70  // 云台最小角度，单位：degree
#define PITCH_ANGLE_MID 90  // 云台中位角度，单位：degree
#define PITCH_ANGLE_MAX 110 // 云台最大角度，单位：degree
#define PITCH_SPEED_MAX 180 // 云台速度，单位：degree/s

#define XBOX_DEADLINE 0.1      // xbox摇杆死区，范围0~1
#define MUSIC_POWER 0.1        // 音乐注入功率，范围0~1
#define SINGLE_SHOOT_TIME 0.04 // 单发时间，单位：s

// 以下引脚位于单片机IO
#define PITCH_PIN 33

// 74HC595配置
#define HC595_CLK 25
#define HC595_LATCH 26
#define HC595_DATA 27
#define HC595_UPDATE_FREQ 50000 // 74HC595刷新频率
#define HC595_BUF_LEN 8         // 74HC595缓冲区长度

// 以下引脚位于74HC595
// X电机
#define X_EN 0
#define X_STEP 1
#define X_DIR 2
// Y电机
#define Y_EN 3
#define Y_STEP 4
#define Y_DIR 5
// Z电机
#define Z_EN 6
#define Z_STEP 7
#define Z_DIR 8
// E0电机
#define E0_EN 9
#define E0_STEP 10
#define E0_DIR 11
// E1电机
#define E1_EN 12
#define E1_STEP 13
#define E1_DIR 14
// 加热
#define H_BED 16 // 热床
#define H_E0 17  // 热端1
#define H_E1 18  // 热端2
// 风扇
#define H_FAN1 19
#define H_FAN2 20
