#pragma once

#include <Arduino.h>
#include <XboxSeriesXControllerESP32_asukiaaa.hpp>

class RC {
  public:
    bool is_connected = false;

    float LX = 0, LY = 0, RX = 0, RY = 0; // 左右摇杆值，范围-1~1
    float LT = 0, RT = 0;                 // 左右扳机值，范围0~1

    // 按钮
    bool A = false, B = false, X = false, Y = false;
    bool LB = false, RB = false;                                    // 扳机旁边的按钮
    bool LS = false, RS = false;                                    // 摇杆按下
    bool share = false, start = false, select = false, box = false; // 功能键

    RC(String mac);

    void begin();

    void onLoop();

  private:
    XboxSeriesXControllerESP32_asukiaaa::Core xbox;
};
