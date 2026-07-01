#include <Arduino.h>
#include <OneButton.h>
#include <Preferences.h>

#include "air.hpp"
#include "hit.hpp"

static constexpr auto TIMEOUT_MS = 100;

Preferences preferences;
OneButton button(9, true); // GPIO9, 内部上拉
bool g_click = false;
bool g_long_click = false;
uint32_t g_last_cdc_receive_ms = 0;

void handleClick() {
    g_click = true;
}

void handleLongPressStart() {
    g_long_click = true;
}

void serialEvent() {
    uint8_t data[10];
    uint32_t i = 0;
    while (Serial.available()) {
        if (i < 10) {
            data[i++] = Serial.read();
        } else {
            i++;
            Serial.read();
        }
    }
    if (i == 10) {
        memcpy(Air::my_packet.dbus, data, 10);
        g_last_cdc_receive_ms = millis();
    }
}

void setup() {
    preferences.begin("armor", false);

    Serial.begin(115200);
    Serial0.begin(115200, SERIAL_8N1, 20, 21);

    // 绑定回调函数
    button.attachClick(handleClick);
    button.attachLongPressStart(handleLongPressStart);
    button.setClickMs(50);  // 短按时间（毫秒）
    button.setPressMs(500); // 长按时间（毫秒）

    Hit::begin();
    Air::begin();

    void loop2(void *pvParameters);
    xTaskCreate(loop2, "loop2", 8192, NULL, 1, NULL);
}

void loop() {
    Hit::onLoop();
}

void handle_air() {
    static Air::packet_t peer_packet_last;

    // 处理收到的数据包
    // 颜色变化
    if (Air::peer_packet.color != peer_packet_last.color && Air::peer_packet.color != 0) {
        Hit::color = Air::peer_packet.color;
        preferences.putUInt("color", Hit::color);
    }
    // 击打次数变化
    if (Air::peer_packet.hit_cnt != peer_packet_last.hit_cnt) {
        Hit::last_hit_ms = millis();
    }
    peer_packet_last = Air::peer_packet;

    // 发送自己的数据包
    Air::my_packet.color = Hit::color;
    Air::my_packet.hit_cnt = Hit::hit_cnt;
    if (millis() - g_last_cdc_receive_ms > TIMEOUT_MS) { // 超时数据清零
        memset(Air::my_packet.dbus, 0, sizeof(Air::my_packet.dbus));
    }
}

void handle_serial() {
    // 串口发送DBUS数据
    if (millis() - Air::last_air_ms > TIMEOUT_MS) { // 超时数据清零
        memset(Air::peer_packet.dbus, 0, sizeof(Air::peer_packet.dbus));
    }
    Serial0.write(Air::peer_packet.dbus, sizeof(Air::peer_packet.dbus));
    Serial0.flush();

    // CDC发送：颜色、击打次数、信号强度(tx, rx)、距离最后一次收到消息的毫秒数
    uint32_t latency_ms = millis() - Air::last_air_ms;
    Serial.printf("%d,%d,%d,%d,%d\n",
                  Air::my_packet.color,
                  Air::peer_packet.hit_cnt,
                  Air::peer_packet.rssi,
                  Air::my_packet.rssi,
                  latency_ms);
    Serial.flush();
}

void loop2(void *pvParameters) {
    while (1) {
        button.tick();
        Air::onLoop();

        if (!Air::is_pairing) { // 不在配对中
            if (g_long_click) { // 长按配对
                Air::entryPairing();
                Hit::detect_hit = false;
            } else if (g_click) { // 短按切换颜色
                if (Hit::color == Hit::RED) {
                    Hit::color = Hit::BLUE;
                } else {
                    Hit::color = Hit::RED;
                }
                preferences.putUInt("color", Hit::color);
            } else { // 正常运行业务逻辑
                handle_air();
                handle_serial();
            }
        } else {           // 在配对中
            if (g_click) { // 短按保存配对
                Air::savePairing();
                Hit::color = Hit::RED;
                preferences.putUInt("color", Hit::color);
                Hit::detect_hit = true;
            } else {
                if (Air::pairing_found) {
                    Hit::color = Hit::GREEN;
                } else {
                    Hit::color = Hit::YELLOW;
                }
            }
        }

        g_click = false;
        g_long_click = false;

        delay(10);
    }
}
