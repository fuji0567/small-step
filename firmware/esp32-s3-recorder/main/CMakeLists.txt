if(NOT EXISTS "${CMAKE_CURRENT_LIST_DIR}/secrets.h")
    message(FATAL_ERROR "Copy main/secrets.example.h to main/secrets.h and configure it before building")
endif()

idf_component_register(
    SRCS
        "main.c"
        "audio_recorder.c"
        "small_step_client.c"
        "upload_policy.c"
        "wifi_connection.c"
        "wav.c"
    INCLUDE_DIRS "."
    REQUIRES
        esp_driver_i2s
        esp_http_client
        esp_wifi
        nvs_flash
        spiffs
        mbedtls
)
