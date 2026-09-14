#pragma once

#include <stddef.h>
#include <stdint.h>

#include "esp_err.h"

typedef struct {
    int16_t *samples;
    size_t sample_count;
    uint32_t rms;
    uint16_t peak;
} small_step_audio_t;

esp_err_t small_step_audio_init(void);
esp_err_t small_step_audio_capture(small_step_audio_t *audio);
void small_step_audio_release(small_step_audio_t *audio);
