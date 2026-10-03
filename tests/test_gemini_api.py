import wave
from unittest.mock import MagicMock, patch

import pytest

from generate_gemini_voice import core
from generate_gemini_voice.config import settings


def _fake_client(pcm=b"\x01\x00" * 100):
    client = MagicMock()
    part = MagicMock()
    part.inline_data.data = pcm
    client.models.generate_content.return_value.candidates = [
        MagicMock(content=MagicMock(parts=[part]))
    ]
    return client


def test_default_model_is_gemini_38():
    assert core.DEFAULT_MODEL == "gemini-3.8-flash-tts"
    assert core.is_gemini_api(core.DEFAULT_MODEL)
    assert "gemini-3.1-flash-tts-preview" not in core.MODEL_CHOICES


def test_missing_gemini_key_is_clear(monkeypatch):
    monkeypatch.setattr(settings, "gemini_api_key", None)
    with pytest.raises(RuntimeError, match="GEMINI_API_KEY not set"):
        core._gemini_api_key()


def test_gemini_api_writes_wav_and_passes_prompt(monkeypatch, tmp_path):
    monkeypatch.setattr(settings, "gemini_api_key", "AIzaTESTKEY0000000000")
    client = _fake_client()
    out = tmp_path / "o.wav"
    with patch("google.genai.Client", return_value=client):
        core.generate_speech(
            "Hello", str(out), audio_format="WAV", prompt="Read warmly."
        )
    kwargs = client.models.generate_content.call_args.kwargs
    assert kwargs["model"] == "gemini-3.8-flash-tts"
    assert kwargs["contents"].startswith("Read warmly.")
    with wave.open(str(out)) as w:
        assert w.getframerate() == 24000 and w.getnframes() == 100


def test_gemini_api_strips_wav_header(monkeypatch):
    blob = (
        b"RIFF"
        + (40).to_bytes(4, "little")
        + b"WAVEfmt "
        + (16).to_bytes(4, "little")
        + b"\x00" * 16
        + b"data"
        + (4).to_bytes(4, "little")
        + b"PCM!"
    )
    client = _fake_client(blob)
    data = core._gemini_api_chunk(client, "x", "gemini-3.8-flash-tts", "Zephyr", None)
    assert data == b"PCM!"


def test_wav_trailing_chunks_are_not_audio():
    """Gemini appends a C2PA manifest after the data chunk; it must not be played."""
    pcm = b"\x10\x00" * 50
    blob = (
        b"RIFF"
        + (0).to_bytes(4, "little")
        + b"WAVEfmt "
        + (16).to_bytes(4, "little")
        + b"\x00" * 16
        + b"LIST"
        + (3).to_bytes(4, "little")
        + b"abc\x00"  # odd size + pad byte
        + b"data"
        + len(pcm).to_bytes(4, "little")
        + pcm
        + b"C2PA"
        + (25).to_bytes(4, "little")
        + b"Created by Google Gen AI"
    )
    assert core._wav_pcm(blob) == pcm
