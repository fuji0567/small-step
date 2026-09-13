#pragma once

#include <stdbool.h>
#include <stddef.h>
#include <stdint.h>

bool small_step_send_heartbeat(void);
bool small_step_upload_pcm(
    const int16_t *samples,
    size_t sample_count,
    const char *upload_id
);
bool small_step_upload_wav_file(const char *path, const char *upload_id);
