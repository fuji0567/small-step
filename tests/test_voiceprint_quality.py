from app.models import VoiceprintQualityIssue
from app.speaker_diarization import SpeakerDiarizationResult, SpeakerSegment
from app.voiceprint_quality import evaluate_voiceprint_sample


SAMPLE_RATE = 100


def diarization(*segments: tuple[float, float, str]) -> SpeakerDiarizationResult:
    labels = {label for _start, _end, label in segments}
    return SpeakerDiarizationResult(
        speaker_count=len(labels),
        segments=[
            SpeakerSegment(
                start_seconds=start,
                end_seconds=end,
                speaker_label=label,
            )
            for start, end, label in segments
        ],
    )


def sample_with_levels(*, speech_level: int, noise_level: int) -> list[int]:
    return [noise_level] * 50 + [speech_level] * 900 + [noise_level] * 50


def test_quality_accepts_one_clear_speaker_for_nine_seconds():
    result = evaluate_voiceprint_sample(
        sample_with_levels(speech_level=10_000, noise_level=100),
        sample_rate=SAMPLE_RATE,
        diarization=diarization((0.5, 9.5, "speaker_01")),
    )

    assert result.issue is None
    assert result.speaker_count == 1
    assert result.speech_seconds == 9.0


def test_quality_rejects_short_speech_and_multiple_speakers():
    samples = sample_with_levels(speech_level=10_000, noise_level=100)

    short = evaluate_voiceprint_sample(
        samples,
        sample_rate=SAMPLE_RATE,
        diarization=diarization((0.5, 3.5, "speaker_01")),
    )
    multiple = evaluate_voiceprint_sample(
        samples,
        sample_rate=SAMPLE_RATE,
        diarization=diarization(
            (0.5, 5.0, "speaker_01"),
            (5.0, 9.5, "speaker_02"),
        ),
    )

    assert short.issue == VoiceprintQualityIssue.too_short
    assert multiple.issue == VoiceprintQualityIssue.multiple_speakers


def test_quality_rejects_audio_longer_than_recording_window():
    result = evaluate_voiceprint_sample(
        [10_000] * 1_700,
        sample_rate=SAMPLE_RATE,
        diarization=diarization((0.0, 17.0, "speaker_01")),
    )

    assert result.issue == VoiceprintQualityIssue.too_long


def test_quality_rejects_clipping_quiet_audio_and_noise():
    one_speaker = diarization((0.5, 9.5, "speaker_01"))

    clipped = evaluate_voiceprint_sample(
        sample_with_levels(speech_level=32_767, noise_level=100),
        sample_rate=SAMPLE_RATE,
        diarization=one_speaker,
    )
    quiet = evaluate_voiceprint_sample(
        sample_with_levels(speech_level=200, noise_level=10),
        sample_rate=SAMPLE_RATE,
        diarization=one_speaker,
    )
    noisy = evaluate_voiceprint_sample(
        sample_with_levels(speech_level=8_000, noise_level=5_000),
        sample_rate=SAMPLE_RATE,
        diarization=one_speaker,
    )

    assert clipped.issue == VoiceprintQualityIssue.clipping
    assert quiet.issue == VoiceprintQualityIssue.too_quiet
    assert noisy.issue == VoiceprintQualityIssue.too_noisy
