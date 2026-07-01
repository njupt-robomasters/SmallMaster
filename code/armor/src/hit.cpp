#include "hit.hpp"
#include <Preferences.h>
#include <driver/adc.h>

static constexpr uint32_t SAMPLE_FREQ_HZ = 40000;                  // 这是总轮询采样率，每个通道的采样率只有1/4
static constexpr uint32_t SAMPLE_LEN = 10e-3 * SAMPLE_FREQ_HZ * 4; // 10ms的采样数据

extern Preferences preferences;

// public
uint32_t Hit::RED = Adafruit_NeoPixel::Color(255, 0, 0);
uint32_t Hit::BLUE = Adafruit_NeoPixel::Color(0, 0, 255);
uint32_t Hit::GREEN = Adafruit_NeoPixel::Color(0, 255, 0);
uint32_t Hit::YELLOW = Adafruit_NeoPixel::Color(255, 255, 0);
uint32_t Hit::color = 0;
bool Hit::detect_hit = true;
uint32_t Hit::hit_cnt = 0;
uint32_t Hit::last_hit_ms = 0;

// private
Adafruit_NeoPixel *Hit::ws2812s[4] = {
    new Adafruit_NeoPixel(3, 10, NEO_GRB + NEO_KHZ800), // front
    new Adafruit_NeoPixel(3, 5, NEO_GRB + NEO_KHZ800),  // back
    new Adafruit_NeoPixel(3, 6, NEO_GRB + NEO_KHZ800),  // left
    new Adafruit_NeoPixel(3, 7, NEO_GRB + NEO_KHZ800),  // right
};
uint8_t Hit::adc_pins[4] = {0, 4, 3, 1}; // front, back, left, right

static void continuous_adc_init(adc_channel_t *channel, uint8_t channel_num, uint32_t sample_freq_hz, uint32_t sample_len) {
    // ADC配置
    uint32_t adc1_chan_mask = 0;
    for (int i = 0; i < channel_num; i++) {
        adc1_chan_mask |= BIT(channel[i]);
    }
    adc_digi_init_config_t adc_dma_config = {
        .max_store_buf_size = sample_len * 2, // 两倍缓冲区
        .conv_num_each_intr = sample_len,
        .adc1_chan_mask = adc1_chan_mask,
        .adc2_chan_mask = 0,
    };
    ESP_ERROR_CHECK(adc_digi_initialize(&adc_dma_config));

    // 通道配置
    adc_digi_configuration_t dig_cfg = {
        .conv_limit_en = false,
        .conv_limit_num = 255,
        .pattern_num = channel_num,
        .sample_freq_hz = sample_freq_hz,
        .conv_mode = ADC_CONV_SINGLE_UNIT_1,
        .format = ADC_DIGI_OUTPUT_FORMAT_TYPE2,
    };
    adc_digi_pattern_config_t adc_pattern[SOC_ADC_PATT_LEN_MAX] = {0};
    for (int i = 0; i < channel_num; i++) {
        adc_pattern[i].atten = ADC_ATTEN_DB_0;
        adc_pattern[i].channel = channel[i];
        adc_pattern[i].unit = 0;
        adc_pattern[i].bit_width = SOC_ADC_DIGI_MAX_BITWIDTH;
    }
    dig_cfg.adc_pattern = adc_pattern;
    ESP_ERROR_CHECK(adc_digi_controller_configure(&dig_cfg));
}

void Hit::begin() {
    // 从flash读取颜色
    color = preferences.getUInt("color", RED);

    // 初始化WS2812
    for (int i = 0; i < 4; i++) {
        ws2812s[i]->begin();
    }

    // 初始化ADC
    adc_channel_t channel[4] = {ADC_CHANNEL_0, ADC_CHANNEL_4, ADC_CHANNEL_3, ADC_CHANNEL_1};
    continuous_adc_init(channel, sizeof(channel) / sizeof(adc_channel_t), SAMPLE_FREQ_HZ, SAMPLE_LEN);
    adc_digi_start();
}

void Hit::onLoop() {
    // 击打检测
    uint8_t buf[SAMPLE_LEN] = {0};
    memset(buf, 0x00, SAMPLE_LEN);
    uint32_t out_length = 0;
    adc_digi_read_bytes(buf, SAMPLE_LEN, &out_length, ADC_MAX_DELAY);
    for (int i = 0; i < out_length; i += SOC_ADC_DIGI_RESULT_BYTES) {
        adc_digi_output_data_t *p = (adc_digi_output_data_t *)&buf[i];
        uint32_t channel = p->type2.channel;
        uint32_t data = p->type2.data;
        if (data > HIT_THRESHOLD) {                                    // 检测到击打
            if (detect_hit && millis() - last_hit_ms > HIT_BLINK_MS) { // 不在上一次击打冷却期内，新的击打
                hit_cnt++;
                last_hit_ms = millis();
            }
        }
        // if (channel == 0) {
        //     Serial.printf("%d,%d\n", i, data);
        // }
    }

    // WS2812
    for (int i = 0; i < 4; i++) {
        Adafruit_NeoPixel *ws2812 = ws2812s[i];
        if (detect_hit && millis() - last_hit_ms < HIT_BLINK_MS) { // 击打闪烁使能，且在击打冷却期内，闪烁
            ws2812->clear();
            ws2812->show();
        } else { // 否则正常显示
            ws2812->clear();
            ws2812->fill(color, 0, 3);
            ws2812->show();
        }
    }
}
