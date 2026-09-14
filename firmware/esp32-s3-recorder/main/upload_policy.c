#include "upload_policy.h"

small_step_upload_result_t small_step_classify_upload_status(
    bool transport_succeeded,
    int status_code
)
{
    if (!transport_succeeded) {
        return SMALL_STEP_UPLOAD_RETRYABLE;
    }
    if (status_code >= 200 && status_code < 300) {
        return SMALL_STEP_UPLOAD_ACCEPTED;
    }
    if (status_code == 408 || status_code == 425 || status_code == 429
        || status_code >= 500) {
        return SMALL_STEP_UPLOAD_RETRYABLE;
    }
    return SMALL_STEP_UPLOAD_REJECTED;
}
