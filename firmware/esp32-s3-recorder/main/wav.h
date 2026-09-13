#pragma once

#include <stddef.h>
#include <stdint.h>

#define SMALL_STEP_WAV_HEADER_BYTES 44U

void small_step_wav_header(
    uint8_t header[SMALL_STEP_WAV_HEADER_BYTES],
    uint32_t pcm_bytes,
    uint32_t sample_rate_hz
);
