import tomllib
from pathlib import Path


def test_speaker_diarization_extra_supports_legacy_embedding_checkpoints():
    project = tomllib.loads(Path("pyproject.toml").read_text())
    dependencies = project["project"]["optional-dependencies"]["speaker-diarization"]

    assert any(dependency.startswith("omegaconf") for dependency in dependencies)
