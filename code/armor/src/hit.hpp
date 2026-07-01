#include <Adafruit_NeoPixel.h>
#include <Arduino.h>

class Hit {
  public:
    static uint32_t RED;
    static uint32_t BLUE;
    static uint32_t GREEN;
    static uint32_t YELLOW;

    static uint32_t color;
    static bool detect_hit;
    static uint32_t hit_cnt;
    static uint32_t last_hit_ms;

    static void begin();
    static void onLoop();

  private:
    static constexpr auto HIT_THRESHOLD = 2000;
    static constexpr auto HIT_BLINK_MS = 50;

    static Adafruit_NeoPixel *ws2812s[4];
    static uint8_t adc_pins[4]; // 压电片ADC
};
