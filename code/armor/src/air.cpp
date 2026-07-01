#include "air.hpp"

#include <Preferences.h>
#include <WiFi.h>
#include <esp_wifi.h>

extern Preferences preferences;

// public
Air::packet_t Air::my_packet, Air::peer_packet;
uint32_t Air::last_air_ms = 0;
bool Air::is_pairing = false;
bool Air::pairing_found = false;
// private
const uint8_t Air::empty_mac[6] = {0x00, 0x00, 0x00, 0x00, 0x00, 0x00};
const uint8_t Air::pairing_data[4] = {0x11, 0x45, 0x14, 0x00};
esp_now_peer_info_t Air::broadcast_peer;
esp_now_peer_info_t Air::peer;
int8_t Air::pairing_best_rssi;

void Air::begin() {
    // 使用 WiFi STA 接口运行 ESP-NOW 协议栈
    WiFi.mode(WIFI_MODE_STA);
    WiFi.disconnect();

    // 使用WiFi 14信道
    wifi_country_t config = {
        .cc = "JP",
        .schan = 1,
        .nchan = 14,
        .policy = WIFI_COUNTRY_POLICY_MANUAL,
    };
    esp_wifi_set_country(&config);
    esp_wifi_set_channel(14, WIFI_SECOND_CHAN_NONE);

    // 20dBm功率
    esp_wifi_set_max_tx_power(84);

    // 启用混杂模式，以获取发送方rssi
    esp_wifi_set_promiscuous(true);
    esp_wifi_set_promiscuous_rx_cb(promiscuous_rx_cb);

    // 初始化ESP-NOW
    esp_now_init();
    esp_now_register_recv_cb(onRecv);

    // 添加广播peer
    memset(broadcast_peer.peer_addr, 0xFF, 6);
    esp_now_add_peer(&broadcast_peer);

    if (preferences.isKey("peer_mac")) {
        preferences.getBytes("peer_mac", peer.peer_addr, 6);
        esp_now_add_peer(&peer);
    } else {
        memset(peer.peer_addr, 0x00, 6);
    }
}

void Air::entryPairing() {
    // 清除之前的配对
    esp_now_del_peer(peer.peer_addr);

    is_pairing = true;
    pairing_found = false;

    // 用于只配对最强的信号
    my_packet.rssi = -128;
    pairing_best_rssi = -128;
}

void Air::savePairing() {
    if (pairing_found) {
        // 添加peer
        esp_now_add_peer(&peer);
    } else {
        // 配对失败，清空设备mac
        memset(peer.peer_addr, 0x00, 6);
    }

    // 写入flash
    preferences.putBytes("peer_mac", peer.peer_addr, 6);

    is_pairing = false;
}

void Air::onLoop() {
    if (is_pairing) { // 配对模式
        esp_now_send(broadcast_peer.peer_addr, pairing_data, 4); // 发送配对请求
    } else if (memcmp(peer.peer_addr, empty_mac, 6) != 0) {      // 已有配对设备
        esp_now_send(peer.peer_addr, (uint8_t *)&my_packet, sizeof(packet_t));
    }
}

void Air::onRecv(const uint8_t *mac_addr, const uint8_t *data, int data_len) {
    if (is_pairing) { // 在配对中
        if (data_len == 4 && memcmp(pairing_data, data, 4) == 0) { // 配对magic正确
            if (my_packet.rssi > pairing_best_rssi) { // 只配对最强的信号
                pairing_best_rssi = my_packet.rssi;
                memcpy(peer.peer_addr, mac_addr, 6);
                pairing_found = true;
            }
        }
    } else if (memcmp(peer.peer_addr, mac_addr, 6) == 0) { // 是从配对设备发过来的
        if (data_len == sizeof(packet_t)) {                // 数据长度正确
            memcpy(&peer_packet, data, sizeof(packet_t));
            last_air_ms = millis();
        }
    }
}

typedef struct {
    unsigned frame_ctrl : 16;
    unsigned duration_id : 16;
    uint8_t addr1[6]; /* receiver address */
    uint8_t addr2[6]; /* sender address */
    uint8_t addr3[6]; /* filtering address */
    unsigned sequence_ctrl : 16;
    uint8_t addr4[6]; /* optional */
} wifi_ieee80211_mac_hdr_t;

typedef struct {
    wifi_ieee80211_mac_hdr_t hdr;
    uint8_t payload[0]; /* network data ended with 4 bytes csum (CRC32) */
} wifi_ieee80211_packet_t;

void Air::promiscuous_rx_cb(void *buf, wifi_promiscuous_pkt_type_t type) {
    if (type != WIFI_PKT_MGMT)
        return;

    const auto *ppkt = (wifi_promiscuous_pkt_t *)buf;
    const auto *ipkt = (wifi_ieee80211_packet_t *)ppkt->payload;
    const wifi_ieee80211_mac_hdr_t *hdr = &ipkt->hdr;

    if (is_pairing) { // 配对模式
        my_packet.rssi = ppkt->rx_ctrl.rssi;
    } else {
        if (memcmp(hdr->addr2, peer.peer_addr, 6) == 0) {
            my_packet.rssi = ppkt->rx_ctrl.rssi;
        }
    }
}
