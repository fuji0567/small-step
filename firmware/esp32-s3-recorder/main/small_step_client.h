#pragma once

#include <stddef.h>
#include <stdint.h>

#include "upload_policy.h"

bool small_step_send_heartbeat(void);
small_step_upload_result_t small_step_upload_pcm(
    const int16_t *samples,
    size_t sample_count,
    const char *upload_id
);
small_step_upload_result_t small_step_upload_wav_file(
    const char *path,
    const char *upload_id
);
