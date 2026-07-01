#include <Arduino.h>
#include <esp_now.h>

class Air {
  public:
    struct alignas(1) packet_t {
        uint32_t color = 0;
        uint32_t hit_cnt = 0;
        uint8_t dbus[10] = {0};
        int8_t rssi;
    };

    static packet_t my_packet, peer_packet;
    static uint32_t last_air_ms;

    static bool is_pairing;
    static bool pairing_found;

    static void begin();
    static void entryPairing();
    static void savePairing();
    static void onLoop();

  private:
    static const uint8_t empty_mac[6];
    static const uint8_t pairing_data[4];

    static esp_now_peer_info_t broadcast_peer;
    static esp_now_peer_info_t peer;

    static int8_t pairing_best_rssi;

    static void onRecv(const uint8_t *mac_addr, const uint8_t *data, int data_len);

    static void promiscuous_rx_cb(void *buf, wifi_promiscuous_pkt_type_t type);
};
