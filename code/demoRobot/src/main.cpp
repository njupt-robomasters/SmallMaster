#include <Arduino.h>

#include "config.hpp"
#include "utils.hpp"

#include "dbus.hpp"
#include "rc.hpp"

#include "hc595.hpp"
#include "stepper.hpp"

#include "chassis.hpp"
#include "gimbal.hpp"

#include "music.hpp"

// Xbox手柄，替换成自己的手柄蓝牙MAC地址
RC rc("40:8e:2c:92:72:aa");

// DBUS
DBUS dbus;

// 74HC595
HC595 hc595;

// 底盘
Stepper s1(hc595.buf, X_EN, X_STEP, X_DIR);
Stepper s2(hc595.buf, Y_EN, Y_STEP, Y_DIR);
Stepper s3(hc595.buf, Z_EN, Z_STEP, Z_DIR);
Stepper s4(hc595.buf, E0_EN, E0_STEP, E0_DIR);
Chassis chassis(s1, s2, s3, s4);

// 云台
Gimbal gimbal(hc595.buf, PITCH_PIN, H_BED);

// 音乐播放进程句柄
TaskHandle_t music_task_handle = NULL;

void serialEvent1() {
    uint8_t data[10];
    uint32_t i = 0;
    while (Serial1.available()) {
        if (i < 10) {
            data[i++] = Serial1.read();
        } else {
            i++;
            Serial1.read();
        }
    }
    if (i == 10) {
        dbus.parseData(data);
    }
}

void setup() {
    Serial.begin(115200);                      // CH340串口
    Serial1.begin(115200, SERIAL_8N1, 16, 17); // DBUS串口

    rc.begin();
    hc595.begin();
    gimbal.begin();

    void loop0(void *pvParameters);
    xTaskCreatePinnedToCore(loop0, "loop0", 8192, NULL, 1, NULL, 0); // 核心0任务
}

void loop() {
    // loop默认在核心1上运行
    // 不建议在核心1上运行其他代码，以免影响74HC595刷新
    chassis.onLoop();
    gimbal.onLoop();
    hc595.onLoop();
}

void music_task(void *pvParameters) {
    // 过滤掉开头的空白音符
    int i = 0;
    for (; i < sizeof(freqs) / sizeof(freqs[0]); i++) {
        if (freqs[i] != 0)
            break;
    }
    for (; i < sizeof(freqs) / sizeof(freqs[0]); i++) {
        if (freqs[i] == 0) {
            gimbal.disableInject();
            vTaskDelay(durations[i]);
        } else {
            gimbal.setInject(freqs[i], MUSIC_POWER);
            vTaskDelay(durations[i]);

            // 在音符之间添加10ms间隔，防止相同音符连音
            gimbal.disableInject();
            vTaskDelay(10);
        }
    }
    music_task_handle = NULL;
    vTaskDelete(NULL);
}

void loop0(void *pvParameters) {
    while (1) {
        rc.onLoop();
        if (!rc.is_connected) {
            // 手柄未连接，底盘和云台失能
            chassis.setEnable(false);
            gimbal.setEnable(false);
            // 停止音乐
            if (music_task_handle != NULL) {
                vTaskDelete(music_task_handle);
                music_task_handle = NULL;
                gimbal.disableInject();
            }
            delay(1); // 防止饿死任务看门狗
            continue;
        }

        // 手柄已连接，使能底盘和云台
        chassis.setEnable(true);
        gimbal.setEnable(true);

        // 底盘和云台运动
        // 手柄摇杆
        float vx = rc.LX * VXY_MAX; // 前进
        float vy = rc.LY * VXY_MAX; // 左移
        float vr = rc.RY * VR_MAX;  // 逆时针旋转
        float pitch_speed = rc.RX * PITCH_SPEED_MAX;
        // 键鼠控制
        if (dbus.is_connected) {
            if (dbus.w)
                vx += VXY_MAX;
            else if (dbus.s)
                vx -= VXY_MAX;
            if (dbus.a)
                vy += VXY_MAX;
            else if (dbus.d)
                vy -= VXY_MAX;
            vr += -dbus.mouse_x * VR_MAX * 5;
            pitch_speed += -dbus.mouse_y * PITCH_SPEED_MAX * 5;
        }
        // 应用
        chassis.setSpeed(vx, vy, vr);
        gimbal.setSpeed(pitch_speed);

        // 连射
        bool continue_shoot = false;
        // 左右扳机
        if (rc.LT > 0.1 || rc.RT > 0.1) {
            continue_shoot = true;
        }
        // 鼠标左键
        if (dbus.is_connected && dbus.left_button) {
            continue_shoot = true;
        }
        // 应用
        gimbal.setContinueShoot(continue_shoot);

        // 点射
        bool single_shoot = false;
        // 左右扳机上方的按键
        static bool lastLRB = false;
        bool btnLRB = rc.LB || rc.RB;
        if (btnLRB && btnLRB != lastLRB) {
            single_shoot = true;
        }
        lastLRB = btnLRB;
        // 鼠标右键
        static bool last_right_button = false;
        if (dbus.is_connected && dbus.right_button && dbus.right_button != last_right_button) {
            single_shoot = true;
        }
        last_right_button = dbus.right_button;
        // 应用
        if (single_shoot) {
            gimbal.triggerSingleShoot();
        }

        // 按X播放音乐
        static bool lastX = false;
        if (rc.X && rc.X != lastX) {
            if (music_task_handle == NULL) {
                xTaskCreatePinnedToCore(music_task, "music_task", 4096, NULL, 1, &music_task_handle, 0);
            }
        }
        lastX = rc.X;

        // 按B停止音乐
        static bool lastB = false;
        if (rc.B && rc.B != lastB) {
            if (music_task_handle != NULL) {
                vTaskDelete(music_task_handle);
                music_task_handle = NULL;
                gimbal.disableInject();
            }
        }
        lastB = rc.B;

        delay(1); // 防止饿死任务看门狗
    }
}
