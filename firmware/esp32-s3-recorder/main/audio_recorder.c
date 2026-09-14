#include "audio_recorder.h"

#include <math.h>
#include <stdbool.h>
#include <stdint.h>
#include <stdlib.h>

#include "device_config.h"
#include "driver/i2s_pdm.h"
#include "esp_heap_caps.h"
#include "esp_log.h"
#include "freertos/FreeRTOS.h"
#include "soc/soc_caps.h"

#define STEREO_FRAMES_PER_READ 1024U

static const char *TAG = "small_step_audio";
static i2s_chan_handle_t rx_channel;

esp_err_t small_step_audio_init(void)
{
    i2s_chan_config_t channel_config = I2S_CHANNEL_DEFAULT_CONFIG(I2S_NUM_0, I2S_ROLE_MASTER);
    esp_err_t error = i2s_new_channel(&channel_config, NULL, &rx_channel);
    if (error != ESP_OK) {
        return error;
    }

    i2s_pdm_rx_config_t pdm_config = {
        .clk_cfg = I2S_PDM_RX_CLK_DEFAULT_CONFIG(SMALL_STEP_SAMPLE_RATE_HZ),
        .slot_cfg = I2S_PDM_RX_SLOT_DEFAULT_CONFIG(
            I2S_DATA_BIT_WIDTH_16BIT,
            I2S_SLOT_MODE_STEREO
        ),
        .gpio_cfg = {
            .clk = SMALL_STEP_PDM_CLK_GPIO,
#if SOC_I2S_PDM_MAX_RX_LINES > 1
            .dins = {
                SMALL_STEP_PDM_DATA_GPIO,
                I2S_GPIO_UNUSED,
                I2S_GPIO_UNUSED,
                I2S_GPIO_UNUSED,
            },
#else
            .din = SMALL_STEP_PDM_DATA_GPIO,
#endif
            .invert_flags = {
                .clk_inv = false,
            },
        },
    };

#if SOC_I2S_PDM_MAX_RX_LINES > 1
    pdm_config.slot_cfg.slot_mask =
        I2S_PDM_RX_LINE0_SLOT_LEFT | I2S_PDM_RX_LINE0_SLOT_RIGHT;
#else
    pdm_config.slot_cfg.slot_mask = I2S_PDM_SLOT_BOTH;
#endif

    error = i2s_channel_init_pdm_rx_mode(rx_channel, &pdm_config);
    if (error != ESP_OK) {
        return error;
    }
    return i2s_channel_enable(rx_channel);
}

esp_err_t small_step_audio_capture(small_step_audio_t *audio)
{
    if (audio == NULL) {
        return ESP_ERR_INVALID_ARG;
    }

    const size_t target_frames = SMALL_STEP_SAMPLE_RATE_HZ * SMALL_STEP_RECORD_SECONDS;
    int16_t *samples = heap_caps_malloc(target_frames * sizeof(int16_t), MALLOC_CAP_SPIRAM | MALLOC_CAP_8BIT);
    if (samples == NULL) {
        ESP_LOGE(TAG, "PSRAM is required for the %u-second recording buffer", SMALL_STEP_RECORD_SECONDS);
        return ESP_ERR_NO_MEM;
    }

    int16_t *stereo = heap_caps_malloc(
        STEREO_FRAMES_PER_READ * 2U * sizeof(int16_t),
        MALLOC_CAP_INTERNAL | MALLOC_CAP_8BIT
    );
    if (stereo == NULL) {
        free(samples);
        return ESP_ERR_NO_MEM;
    }

    uint64_t sum_squares = 0U;
    uint32_t peak = 0U;
    size_t written_frames = 0U;
    while (written_frames < target_frames) {
        size_t bytes_read = 0U;
        esp_err_t error = i2s_channel_read(
            rx_channel,
            stereo,
            STEREO_FRAMES_PER_READ * 2U * sizeof(int16_t),
            &bytes_read,
            pdMS_TO_TICKS(2000)
        );
        if (error != ESP_OK) {
            free(stereo);
            free(samples);
            return error;
        }

        size_t frames_read = bytes_read / (2U * sizeof(int16_t));
        if (frames_read == 0U) {
            continue;
        }
        size_t remaining = target_frames - written_frames;
        if (frames_read > remaining) {
            frames_read = remaining;
        }

        uint64_t left_energy = 0U;
        uint64_t right_energy = 0U;
        for (size_t index = 0U; index < frames_read; ++index) {
            int32_t left = stereo[index * 2U];
            int32_t right = stereo[index * 2U + 1U];
            left_energy += (uint64_t)(left * left);
            right_energy += (uint64_t)(right * right);
        }
        size_t selected_slot = right_energy > left_energy ? 1U : 0U;
        for (size_t index = 0U; index < frames_read; ++index) {
            int32_t sample = stereo[index * 2U + selected_slot];
            samples[written_frames + index] = (int16_t)sample;
            sum_squares += (uint64_t)(sample * sample);
            uint32_t magnitude = sample < 0 ? (uint32_t)(-sample) : (uint32_t)sample;
            if (magnitude > peak) {
                peak = magnitude;
            }
        }
        written_frames += frames_read;
    }

    free(stereo);
    audio->samples = samples;
    audio->sample_count = written_frames;
    audio->rms = (uint32_t)sqrt((double)sum_squares / (double)written_frames);
    audio->peak = peak > UINT16_MAX ? UINT16_MAX : (uint16_t)peak;
    return ESP_OK;
}

void small_step_audio_release(small_step_audio_t *audio)
{
    if (audio == NULL) {
        return;
    }
    free(audio->samples);
    *audio = (small_step_audio_t){0};
}
