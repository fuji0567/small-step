#include "small_step_client.h"

#include <limits.h>
#include <stdio.h>
#include <string.h>

#include "device_config.h"
#include "esp_crt_bundle.h"
#include "esp_http_client.h"
#include "esp_log.h"
#include "secrets.h"
#include "wav.h"

#define MULTIPART_BOUNDARY "small-step-esp32-boundary"
#define HTTP_WRITE_CHUNK_BYTES 4096U

static const char *TAG = "small_step_http";

typedef struct {
    const uint8_t *memory;
    size_t memory_size;
    FILE *file;
    size_t wav_size;
} wav_source_t;

static bool build_endpoint(char *destination, size_t size, const char *path)
{
    size_t base_length = strlen(SMALL_STEP_API_BASE_URL);
    while (base_length > 0U && SMALL_STEP_API_BASE_URL[base_length - 1U] == '/') {
        --base_length;
    }
    int written = snprintf(
        destination,
        size,
        "%.*s%s",
        (int)base_length,
        SMALL_STEP_API_BASE_URL,
        path
    );
    return written > 0 && (size_t)written < size;
}

static bool write_all(esp_http_client_handle_t client, const uint8_t *data, size_t size)
{
    size_t offset = 0U;
    while (offset < size) {
        size_t remaining = size - offset;
        int requested = remaining > INT_MAX ? INT_MAX : (int)remaining;
        int written = esp_http_client_write(client, (const char *)(data + offset), requested);
        if (written <= 0) {
            return false;
        }
        offset += (size_t)written;
    }
    return true;
}

static bool write_wav_source(esp_http_client_handle_t client, wav_source_t *source)
{
    if (source->file != NULL) {
        uint8_t chunk[HTTP_WRITE_CHUNK_BYTES];
        rewind(source->file);
        while (!feof(source->file)) {
            size_t read_bytes = fread(chunk, 1U, sizeof(chunk), source->file);
            if (read_bytes > 0U && !write_all(client, chunk, read_bytes)) {
                return false;
            }
            if (ferror(source->file)) {
                return false;
            }
        }
        return true;
    }

    uint8_t header[SMALL_STEP_WAV_HEADER_BYTES];
    small_step_wav_header(header, (uint32_t)source->memory_size, SMALL_STEP_SAMPLE_RATE_HZ);
    return write_all(client, header, sizeof(header))
        && write_all(client, source->memory, source->memory_size);
}

static small_step_upload_result_t upload_wav(wav_source_t *source, const char *upload_id)
{
    char endpoint[320];
    if (!build_endpoint(endpoint, sizeof(endpoint), "/api/v1/edge/audio-jobs")) {
        ESP_LOGE(TAG, "API URL is too long");
        return SMALL_STEP_UPLOAD_REJECTED;
    }

    char prefix[512];
    int prefix_length = 0;
    if (SMALL_STEP_CHILD_ID[0] != '\0') {
        prefix_length = snprintf(
            prefix,
            sizeof(prefix),
            "--" MULTIPART_BOUNDARY "\r\n"
            "Content-Disposition: form-data; name=\"child_id\"\r\n\r\n"
            "%s\r\n",
            SMALL_STEP_CHILD_ID
        );
    }
    int audio_prefix_length = snprintf(
        prefix + prefix_length,
        sizeof(prefix) - (size_t)prefix_length,
        "--" MULTIPART_BOUNDARY "\r\n"
        "Content-Disposition: form-data; name=\"audio\"; filename=\"audio.wav\"\r\n"
        "Content-Type: audio/wav\r\n\r\n"
    );
    if (prefix_length < 0 || audio_prefix_length < 0
        || (size_t)(prefix_length + audio_prefix_length) >= sizeof(prefix)) {
        ESP_LOGE(TAG, "Multipart metadata is too long");
        return SMALL_STEP_UPLOAD_REJECTED;
    }
    prefix_length += audio_prefix_length;

    static const char suffix[] = "\r\n--" MULTIPART_BOUNDARY "--\r\n";
    size_t content_length = (size_t)prefix_length + source->wav_size + sizeof(suffix) - 1U;
    if (content_length > INT_MAX) {
        return SMALL_STEP_UPLOAD_REJECTED;
    }

    esp_http_client_config_t config = {
        .url = endpoint,
        .timeout_ms = SMALL_STEP_HTTP_TIMEOUT_MILLISECONDS,
        .crt_bundle_attach = esp_crt_bundle_attach,
        .user_agent = "small-step-esp32/1",
    };
    esp_http_client_handle_t client = esp_http_client_init(&config);
    if (client == NULL) {
        return SMALL_STEP_UPLOAD_RETRYABLE;
    }

    char content_type[96];
    snprintf(content_type, sizeof(content_type), "multipart/form-data; boundary=%s", MULTIPART_BOUNDARY);
    esp_http_client_set_method(client, HTTP_METHOD_POST);
    esp_http_client_set_header(client, "Content-Type", content_type);
    esp_http_client_set_header(client, "X-Edge-Api-Key", SMALL_STEP_EDGE_API_KEY);
    esp_http_client_set_header(client, "X-Edge-Upload-Id", upload_id);

    small_step_upload_result_t result = SMALL_STEP_UPLOAD_RETRYABLE;
    esp_err_t error = esp_http_client_open(client, (int)content_length);
    if (error == ESP_OK
        && write_all(client, (const uint8_t *)prefix, (size_t)prefix_length)
        && write_wav_source(client, source)
        && write_all(client, (const uint8_t *)suffix, sizeof(suffix) - 1U)
        && esp_http_client_fetch_headers(client) >= 0) {
        uint8_t response[256];
        while (esp_http_client_read(client, (char *)response, sizeof(response)) > 0) {
        }
        int status = esp_http_client_get_status_code(client);
        result = small_step_classify_upload_status(true, status);
        ESP_LOGI(TAG, "Audio upload HTTP status: %d", status);
    } else {
        ESP_LOGW(TAG, "Audio upload connection failed: %s", esp_err_to_name(error));
    }

    esp_http_client_close(client);
    esp_http_client_cleanup(client);
    return result;
}

bool small_step_send_heartbeat(void)
{
    char endpoint[320];
    if (!build_endpoint(endpoint, sizeof(endpoint), "/api/v1/edge/heartbeat")) {
        return false;
    }
    esp_http_client_config_t config = {
        .url = endpoint,
        .timeout_ms = SMALL_STEP_HTTP_TIMEOUT_MILLISECONDS,
        .crt_bundle_attach = esp_crt_bundle_attach,
        .user_agent = "small-step-esp32/1",
    };
    esp_http_client_handle_t client = esp_http_client_init(&config);
    if (client == NULL) {
        return false;
    }
    esp_http_client_set_method(client, HTTP_METHOD_POST);
    esp_http_client_set_header(client, "X-Edge-Api-Key", SMALL_STEP_EDGE_API_KEY);
    esp_err_t error = esp_http_client_perform(client);
    int status = error == ESP_OK ? esp_http_client_get_status_code(client) : 0;
    esp_http_client_cleanup(client);
    return error == ESP_OK && status >= 200 && status < 300;
}

small_step_upload_result_t small_step_upload_pcm(
    const int16_t *samples,
    size_t sample_count,
    const char *upload_id
)
{
    if (samples == NULL || sample_count == 0U || upload_id == NULL) {
        return SMALL_STEP_UPLOAD_REJECTED;
    }
    wav_source_t source = {
        .memory = (const uint8_t *)samples,
        .memory_size = sample_count * sizeof(int16_t),
        .file = NULL,
        .wav_size = SMALL_STEP_WAV_HEADER_BYTES + sample_count * sizeof(int16_t),
    };
    return upload_wav(&source, upload_id);
}

small_step_upload_result_t small_step_upload_wav_file(
    const char *path,
    const char *upload_id
)
{
    FILE *file = fopen(path, "rb");
    if (file == NULL) {
        return SMALL_STEP_UPLOAD_REJECTED;
    }
    if (fseek(file, 0L, SEEK_END) != 0) {
        fclose(file);
        return SMALL_STEP_UPLOAD_REJECTED;
    }
    long file_size = ftell(file);
    if (file_size <= 0L) {
        fclose(file);
        return SMALL_STEP_UPLOAD_REJECTED;
    }
    wav_source_t source = {
        .memory = NULL,
        .memory_size = 0U,
        .file = file,
        .wav_size = (size_t)file_size,
    };
    small_step_upload_result_t result = upload_wav(&source, upload_id);
    fclose(file);
    return result;
}
