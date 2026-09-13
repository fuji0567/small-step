import re
import shutil
import struct
import subprocess
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
FIRMWARE = ROOT / "firmware" / "esp32-s3-recorder"


def _macro_number(name: str) -> int:
    source = (FIRMWARE / "main" / "device_config.h").read_text(encoding="utf-8")
    match = re.search(rf"^#define {name} (\d+)U?$", source, re.MULTILINE)
    assert match is not None
    return int(match.group(1))


def test_esp32_firmware_keeps_credentials_out_of_git():
    gitignore = (ROOT / ".gitignore").read_text(encoding="utf-8")
    example = (FIRMWARE / "main" / "secrets.example.h").read_text(encoding="utf-8")

    assert "/firmware/esp32-s3-recorder/main/secrets.h" in gitignore
    assert "YOUR_WIFI_SSID" in example
    assert "YOUR_ONE_TIME_EDGE_DEVICE_KEY" in example
    assert "qswgcjgmekmyimmqkyhk" not in example


def test_esp32_upload_contract_matches_cloud_audio_api():
    source = (FIRMWARE / "main" / "small_step_client.c").read_text(encoding="utf-8")

    assert '"/api/v1/edge/audio-jobs"' in source
    assert '"/api/v1/edge/heartbeat"' in source
    assert '"X-Edge-Api-Key"' in source
    assert '"X-Edge-Upload-Id"' in source
    assert 'name=\\"child_id\\"' in source
    assert 'name=\\"audio\\"; filename=\\"audio.wav\\"' in source
    assert '"Content-Type: audio/wav' in source


def test_esp32_recording_fits_retry_partition_and_server_limit():
    sample_rate = _macro_number("SMALL_STEP_SAMPLE_RATE_HZ")
    seconds = _macro_number("SMALL_STEP_RECORD_SECONDS")
    wav_bytes = 44 + sample_rate * seconds * 2
    partition_source = (FIRMWARE / "partitions.csv").read_text(encoding="utf-8")
    retry_line = next(line for line in partition_source.splitlines() if line.startswith("retry,"))
    retry_bytes = int(retry_line.split(",")[4].strip(), 16)

    assert wav_bytes < retry_bytes
    assert wav_bytes < 25_000_000


def test_esp32_requires_https_and_deduplicated_retry():
    source = (FIRMWARE / "main" / "main.c").read_text(encoding="utf-8")

    assert 'strncmp(SMALL_STEP_API_BASE_URL, "https://"' in source
    assert "generate_upload_id(upload_id)" in source
    assert "save_upload_id(upload_id)" in source
    assert "small_step_upload_wav_file(SMALL_STEP_PENDING_WAV_PATH, upload_id)" in source
    assert "small_step_audio_release(&audio)" in source


def test_esp32_wav_header_is_valid_pcm(tmp_path):
    compiler = shutil.which("cc")
    if compiler is None:
        pytest.skip("A C compiler is required for the portable WAV unit test")
    runner = tmp_path / "wav_header_test.c"
    binary = tmp_path / "wav_header_test"
    output = tmp_path / "header.bin"
    runner.write_text(
        """
#include <stdint.h>
#include <stdio.h>
#include "wav.h"

int main(void) {
    uint8_t header[SMALL_STEP_WAV_HEADER_BYTES];
    small_step_wav_header(header, 960000U, 16000U);
    return fwrite(header, 1U, sizeof(header), stdout) == sizeof(header) ? 0 : 1;
}
""",
        encoding="ascii",
    )
    subprocess.run(
        [
            compiler,
            "-std=c11",
            "-Wall",
            "-Wextra",
            "-Werror",
            "-I",
            str(FIRMWARE / "main"),
            str(runner),
            str(FIRMWARE / "main" / "wav.c"),
            "-o",
            str(binary),
        ],
        check=True,
    )
    with output.open("wb") as stream:
        subprocess.run([str(binary)], check=True, stdout=stream)

    header = output.read_bytes()
    assert len(header) == 44
    assert header[:4] == b"RIFF"
    assert header[8:12] == b"WAVE"
    assert header[12:16] == b"fmt "
    assert struct.unpack_from("<HHIIHH", header, 20) == (1, 1, 16000, 32000, 2, 16)
    assert header[36:40] == b"data"
    assert struct.unpack_from("<I", header, 40)[0] == 960000
