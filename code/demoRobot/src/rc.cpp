#include "rc.hpp"
#include "config.hpp"
#include "utils.hpp"

RC::RC(String mac) : xbox(mac) {}

void RC::begin() {
    xbox.begin();
}

void RC::onLoop() {
    xbox.onLoop();

    is_connected = xbox.isConnected() && !xbox.isWaitingForFirstNotification();
    if (!is_connected) {
        return;
    }

    // 读取左右摇杆值，归一化到-1~1范围内
    LX = mapf(xbox.xboxNotif.joyLVert, 0, 65535, 1, -1); // 垂直
    if (abs(LX) < XBOX_DEADLINE)
        LX = 0;
    LY = mapf(xbox.xboxNotif.joyLHori, 0, 65535, 1, -1); // 水平
    if (abs(LY) < XBOX_DEADLINE)
        LY = 0;
    RX = mapf(xbox.xboxNotif.joyRVert, 0, 65535, 1, -1); // 垂直
    if (abs(RX) < XBOX_DEADLINE)
        RX = 0;
    RY = mapf(xbox.xboxNotif.joyRHori, 0, 65535, 1, -1); // 水平
    if (abs(RY) < XBOX_DEADLINE)
        RY = 0;
    // Serial.printf("LX: %f, LY: %f, RX: %f, RY: %f\n", LX, LY, RX, RY);

    // 读取扳机值，归一化到0~1范围内
    LT = mapf(xbox.xboxNotif.trigLT, 0, 1023, 0, 1);
    RT = mapf(xbox.xboxNotif.trigRT, 0, 1023, 0, 1);

    // 按钮
    A = xbox.xboxNotif.btnA;
    B = xbox.xboxNotif.btnB;
    X = xbox.xboxNotif.btnX;
    Y = xbox.xboxNotif.btnY;
    LB = xbox.xboxNotif.btnLB;
    RB = xbox.xboxNotif.btnRB;
    LS = xbox.xboxNotif.btnLS;
    RS = xbox.xboxNotif.btnRS;
    share = xbox.xboxNotif.btnShare;
    start = xbox.xboxNotif.btnStart;
    select = xbox.xboxNotif.btnSelect;
    box = xbox.xboxNotif.btnXbox;
}
