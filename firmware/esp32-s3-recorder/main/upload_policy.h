#pragma once

#include <stdbool.h>

typedef enum {
    SMALL_STEP_UPLOAD_ACCEPTED,
    SMALL_STEP_UPLOAD_RETRYABLE,
    SMALL_STEP_UPLOAD_REJECTED,
} small_step_upload_result_t;

small_step_upload_result_t small_step_classify_upload_status(
    bool transport_succeeded,
    int status_code
);
