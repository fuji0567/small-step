#include "wav.h"

#include <string.h>

static void write_u16_le(uint8_t *destination, uint16_t value)
{
    destination[0] = (uint8_t)(value & 0xffU);
    destination[1] = (uint8_t)((value >> 8U) & 0xffU);
}

static void write_u32_le(uint8_t *destination, uint32_t value)
{
    destination[0] = (uint8_t)(value & 0xffU);
    destination[1] = (uint8_t)((value >> 8U) & 0xffU);
    destination[2] = (uint8_t)((value >> 16U) & 0xffU);
    destination[3] = (uint8_t)((value >> 24U) & 0xffU);
}

void small_step_wav_header(
    uint8_t header[SMALL_STEP_WAV_HEADER_BYTES],
    uint32_t pcm_bytes,
    uint32_t sample_rate_hz
)
{
    memset(header, 0, SMALL_STEP_WAV_HEADER_BYTES);
    memcpy(header, "RIFF", 4U);
    write_u32_le(header + 4U, 36U + pcm_bytes);
    memcpy(header + 8U, "WAVE", 4U);
    memcpy(header + 12U, "fmt ", 4U);
    write_u32_le(header + 16U, 16U);
    write_u16_le(header + 20U, 1U);
    write_u16_le(header + 22U, 1U);
    write_u32_le(header + 24U, sample_rate_hz);
    write_u32_le(header + 28U, sample_rate_hz * 2U);
    write_u16_le(header + 32U, 2U);
    write_u16_le(header + 34U, 16U);
    memcpy(header + 36U, "data", 4U);
    write_u32_le(header + 40U, pcm_bytes);
}
