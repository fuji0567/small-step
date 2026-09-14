#include <errno.h>
#include <stdbool.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>

#include "audio_recorder.h"
#include "device_config.h"
#include "esp_heap_caps.h"
#include "esp_log.h"
#include "esp_random.h"
#include "esp_spiffs.h"
#include "freertos/FreeRTOS.h"
#include "freertos/task.h"
#include "nvs_flash.h"
#include "secrets.h"
#include "small_step_client.h"
#include "wav.h"
#include "wifi_connection.h"

static const char *TAG = "small_step";
static TickType_t last_heartbeat;

static bool file_exists(const char *path)
{
    return access(path, F_OK) == 0;
}

static bool atomic_write(const char *temporary_path, const char *path, const void *data, size_t size)
{
    FILE *file = fopen(temporary_path, "wb");
    if (file == NULL) {
        return false;
    }
    bool success = fwrite(data, 1U, size, file) == size
        && fflush(file) == 0
        && fsync(fileno(file)) == 0;
    if (fclose(file) != 0) {
        success = false;
    }
    if (success && rename(temporary_path, path) != 0) {
        success = false;
    }
    if (!success) {
        remove(temporary_path);
    }
    return success;
}

static void generate_upload_id(char destination[37])
{
    uint8_t bytes[16];
    esp_fill_random(bytes, sizeof(bytes));
    bytes[6] = (uint8_t)((bytes[6] & 0x0fU) | 0x40U);
    bytes[8] = (uint8_t)((bytes[8] & 0x3fU) | 0x80U);
    snprintf(
        destination,
        37U,
        "%02x%02x%02x%02x-%02x%02x-%02x%02x-%02x%02x-%02x%02x%02x%02x%02x%02x",
        bytes[0], bytes[1], bytes[2], bytes[3], bytes[4], bytes[5], bytes[6], bytes[7],
        bytes[8], bytes[9], bytes[10], bytes[11], bytes[12], bytes[13], bytes[14], bytes[15]
    );
}

static bool save_upload_id(const char *upload_id)
{
    return atomic_write(
        SMALL_STEP_PENDING_ID_TEMP_PATH,
        SMALL_STEP_PENDING_ID_PATH,
        upload_id,
        strlen(upload_id)
    );
}

static bool load_upload_id(char upload_id[37])
{
    FILE *file = fopen(SMALL_STEP_PENDING_ID_PATH, "rb");
    if (file == NULL) {
        return false;
    }
    size_t bytes_read = fread(upload_id, 1U, 36U, file);
    fclose(file);
    upload_id[bytes_read] = '\0';
    return bytes_read == 36U;
}

static bool save_pending_audio(const small_step_audio_t *audio)
{
    FILE *file = fopen(SMALL_STEP_PENDING_WAV_TEMP_PATH, "wb");
    if (file == NULL) {
        ESP_LOGE(TAG, "Could not open retry audio file: errno=%d", errno);
        return false;
    }
    uint32_t pcm_bytes = (uint32_t)(audio->sample_count * sizeof(int16_t));
    uint8_t header[SMALL_STEP_WAV_HEADER_BYTES];
    small_step_wav_header(header, pcm_bytes, SMALL_STEP_SAMPLE_RATE_HZ);
    bool success = fwrite(header, 1U, sizeof(header), file) == sizeof(header)
        && fwrite(audio->samples, 1U, pcm_bytes, file) == pcm_bytes
        && fflush(file) == 0
        && fsync(fileno(file)) == 0;
    if (fclose(file) != 0) {
        success = false;
    }
    if (success && rename(SMALL_STEP_PENDING_WAV_TEMP_PATH, SMALL_STEP_PENDING_WAV_PATH) != 0) {
        success = false;
    }
    if (!success) {
        remove(SMALL_STEP_PENDING_WAV_TEMP_PATH);
    }
    return success;
}

static void clear_pending(void)
{
    remove(SMALL_STEP_PENDING_WAV_PATH);
    remove(SMALL_STEP_PENDING_ID_PATH);
}

static bool ensure_pending_upload_id(char upload_id[37])
{
    if (load_upload_id(upload_id)) {
        return true;
    }
    generate_upload_id(upload_id);
    return save_upload_id(upload_id);
}

static void maybe_send_heartbeat(void)
{
    TickType_t now = xTaskGetTickCount();
    TickType_t interval = pdMS_TO_TICKS(SMALL_STEP_HEARTBEAT_INTERVAL_SECONDS * 1000U);
    if (last_heartbeat != 0U && now - last_heartbeat < interval) {
        return;
    }
    if (small_step_wifi_wait(5000U) && small_step_send_heartbeat()) {
        last_heartbeat = now;
        ESP_LOGI(TAG, "Heartbeat sent");
    }
}

static void retry_pending_audio(void)
{
    char upload_id[37];
    if (!ensure_pending_upload_id(upload_id)) {
        ESP_LOGE(TAG, "Could not persist the retry upload ID");
        vTaskDelay(pdMS_TO_TICKS(SMALL_STEP_RETRY_INTERVAL_SECONDS * 1000U));
        return;
    }
    if (!small_step_wifi_wait(10000U)) {
        ESP_LOGW(TAG, "Wi-Fi unavailable; keeping one pending recording");
        vTaskDelay(pdMS_TO_TICKS(SMALL_STEP_RETRY_INTERVAL_SECONDS * 1000U));
        return;
    }
    small_step_upload_result_t result = small_step_upload_wav_file(
        SMALL_STEP_PENDING_WAV_PATH,
        upload_id
    );
    if (result == SMALL_STEP_UPLOAD_ACCEPTED) {
        clear_pending();
        ESP_LOGI(TAG, "Pending recording accepted and deleted locally");
    } else if (result == SMALL_STEP_UPLOAD_RETRYABLE) {
        ESP_LOGW(TAG, "Pending recording upload failed; retrying later");
        vTaskDelay(pdMS_TO_TICKS(SMALL_STEP_RETRY_INTERVAL_SECONDS * 1000U));
    } else {
        clear_pending();
        ESP_LOGE(
            TAG,
            "Pending recording rejected and deleted locally; check device configuration"
        );
    }
}

static void validate_configuration(void)
{
    if (strncmp(SMALL_STEP_API_BASE_URL, "https://", 8U) != 0) {
        ESP_LOGE(TAG, "SMALL_STEP_API_BASE_URL must use HTTPS");
        abort();
    }
    if (strstr(SMALL_STEP_WIFI_SSID, "YOUR_") != NULL
        || strstr(SMALL_STEP_EDGE_API_KEY, "YOUR_") != NULL
        || strstr(SMALL_STEP_API_BASE_URL, "YOUR_") != NULL) {
        ESP_LOGE(TAG, "Configure main/secrets.h before flashing");
        abort();
    }
}

static void initialize_storage(void)
{
    esp_vfs_spiffs_conf_t config = {
        .base_path = "/retry",
        .partition_label = "retry",
        .max_files = 4,
        .format_if_mount_failed = true,
    };
    ESP_ERROR_CHECK(esp_vfs_spiffs_register(&config));

    if (!file_exists(SMALL_STEP_PENDING_WAV_PATH) && file_exists(SMALL_STEP_PENDING_ID_PATH)) {
        remove(SMALL_STEP_PENDING_ID_PATH);
    }
    remove(SMALL_STEP_PENDING_WAV_TEMP_PATH);
    remove(SMALL_STEP_PENDING_ID_TEMP_PATH);
}

static void run_startup_diagnostics(void)
{
    const size_t required_audio_bytes =
        SMALL_STEP_SAMPLE_RATE_HZ * SMALL_STEP_RECORD_SECONDS * sizeof(int16_t);
    const size_t required_retry_bytes = required_audio_bytes + SMALL_STEP_WAV_HEADER_BYTES;
    size_t psram_total = heap_caps_get_total_size(MALLOC_CAP_SPIRAM);
    size_t psram_free = heap_caps_get_free_size(MALLOC_CAP_SPIRAM);
    size_t storage_total = 0U;
    size_t storage_used = 0U;
    esp_err_t storage_error = esp_spiffs_info("retry", &storage_total, &storage_used);

    ESP_LOGI(
        TAG,
        "Startup diagnostics: PSRAM total=%u free=%u required=%u",
        (unsigned int)psram_total,
        (unsigned int)psram_free,
        (unsigned int)required_audio_bytes
    );
    ESP_LOGI(
        TAG,
        "Startup diagnostics: retry storage total=%u used=%u required=%u",
        (unsigned int)storage_total,
        (unsigned int)storage_used,
        (unsigned int)required_retry_bytes
    );
    ESP_LOGI(
        TAG,
        "Startup diagnostics: PDM CLK GPIO=%d DATA GPIO=%d",
        SMALL_STEP_PDM_CLK_GPIO,
        SMALL_STEP_PDM_DATA_GPIO
    );

    if (psram_total < required_audio_bytes || psram_free < required_audio_bytes) {
        ESP_LOGE(TAG, "Startup diagnostics failed: recording buffer does not fit in PSRAM");
        abort();
    }
    if (storage_error != ESP_OK || storage_total < required_retry_bytes) {
        ESP_LOGE(TAG, "Startup diagnostics failed: retry storage is unavailable or too small");
        abort();
    }
    if (SMALL_STEP_PDM_CLK_GPIO == SMALL_STEP_PDM_DATA_GPIO) {
        ESP_LOGE(TAG, "Startup diagnostics failed: PDM clock and data GPIO must differ");
        abort();
    }
    ESP_LOGI(TAG, "Startup diagnostics passed");
}

void app_main(void)
{
    validate_configuration();
    esp_err_t nvs_error = nvs_flash_init();
    if (nvs_error == ESP_ERR_NVS_NO_FREE_PAGES || nvs_error == ESP_ERR_NVS_NEW_VERSION_FOUND) {
        ESP_ERROR_CHECK(nvs_flash_erase());
        nvs_error = nvs_flash_init();
    }
    ESP_ERROR_CHECK(nvs_error);
    initialize_storage();
    run_startup_diagnostics();
    ESP_ERROR_CHECK(small_step_wifi_init());
    ESP_ERROR_CHECK(small_step_audio_init());

    while (true) {
        maybe_send_heartbeat();
        if (file_exists(SMALL_STEP_PENDING_WAV_PATH)) {
            retry_pending_audio();
            continue;
        }

        ESP_LOGI(TAG, "Recording %u-second audio chunk", SMALL_STEP_RECORD_SECONDS);
        small_step_audio_t audio = {0};
        esp_err_t capture_error = small_step_audio_capture(&audio);
        if (capture_error != ESP_OK) {
            ESP_LOGE(TAG, "Audio capture failed: %s", esp_err_to_name(capture_error));
            vTaskDelay(pdMS_TO_TICKS(SMALL_STEP_RETRY_INTERVAL_SECONDS * 1000U));
            continue;
        }
        ESP_LOGI(TAG, "Audio level RMS=%lu peak=%u", (unsigned long)audio.rms, audio.peak);
        if (audio.rms < SMALL_STEP_SPEECH_RMS_THRESHOLD) {
            ESP_LOGI(TAG, "Quiet chunk discarded without upload");
            small_step_audio_release(&audio);
            continue;
        }

        char upload_id[37];
        generate_upload_id(upload_id);
        if (!save_upload_id(upload_id)) {
            ESP_LOGE(TAG, "Could not persist upload ID; discarding chunk safely");
            small_step_audio_release(&audio);
            continue;
        }

        small_step_upload_result_t upload_result = SMALL_STEP_UPLOAD_RETRYABLE;
        if (small_step_wifi_wait(10000U)) {
            upload_result = small_step_upload_pcm(
                audio.samples,
                audio.sample_count,
                upload_id
            );
        }
        if (upload_result == SMALL_STEP_UPLOAD_ACCEPTED) {
            remove(SMALL_STEP_PENDING_ID_PATH);
            ESP_LOGI(TAG, "Recording accepted; no local audio retained");
        } else if (upload_result == SMALL_STEP_UPLOAD_REJECTED) {
            remove(SMALL_STEP_PENDING_ID_PATH);
            ESP_LOGE(TAG, "Recording rejected and discarded; check device configuration");
        } else if (save_pending_audio(&audio)) {
            ESP_LOGW(TAG, "Upload failed; one recording saved for retry");
        } else {
            ESP_LOGE(TAG, "Upload and retry storage failed; recording discarded");
            remove(SMALL_STEP_PENDING_ID_PATH);
        }
        small_step_audio_release(&audio);
    }
}
