#pragma once

#include <stdbool.h>
#include <stdint.h>

#include "esp_err.h"

esp_err_t small_step_wifi_init(void);
bool small_step_wifi_wait(uint32_t timeout_milliseconds);
