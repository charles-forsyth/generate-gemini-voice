import sys
from unittest.mock import patch

import pytest

from generate_gemini_voice.cli import main


def test_cli_list_voices_gemini(capsys):
    with patch.object(sys, "argv", ["generate-voice", "--list-voices"]):
        main()
    out = capsys.readouterr().out
    assert "Zephyr" in out and "Kore" in out


def test_cli_list_voices_chirp(mock_tts_client, capsys):
    with patch.object(
        sys, "argv", ["generate-voice", "--list-voices", "--model", "chirp3"]
    ):
        main()
    mock_tts_client.list_voices.assert_called_once()
    assert "en-US-Chirp3-HD-Zephyr" in capsys.readouterr().out


def test_cli_generate_text(mock_tts_client, mock_pygame, tmp_path):
    output = tmp_path / "cli_test.mp3"
    with patch.object(
        sys,
        "argv",
        [
            "generate-voice",
            "Hello World",
            "--output-file",
            str(output),
            "--no-play",
            "--model",
            "gemini-2.5-flash-tts",
        ],
    ):
        main()
    mock_tts_client.synthesize_speech.assert_called_once()
    assert output.read_bytes() == b"fake_audio_content"


def test_cli_generate_temp_cleans_up(
    mock_tts_client, mock_pygame, tmp_path, monkeypatch
):
    monkeypatch.setattr("tempfile.tempdir", str(tmp_path))
    with patch.object(
        sys,
        "argv",
        [
            "generate-voice",
            "Hello World",
            "--temp",
            "--prompt",
            "Read calmly.",
            "--model",
            "gemini-2.5-flash-tts",
        ],
    ):
        main()
    mock_tts_client.synthesize_speech.assert_called_once()
    mock_pygame.mixer.music.play.assert_called()
    assert not list(tmp_path.glob("genvoice_*"))


def test_cli_sample_voices(mock_tts_client, mock_pygame):
    with patch.object(
        sys, "argv", ["generate-voice", "--sample-voices", "--model", "chirp3"]
    ):
        main()
    mock_tts_client.list_voices.assert_called()
    mock_tts_client.synthesize_speech.assert_called()


def test_cli_no_input(capsys):
    with patch("sys.stdin.isatty", return_value=True):
        with patch.object(sys, "argv", ["generate-voice"]):
            with pytest.raises(SystemExit):
                main()
    assert "no input" in capsys.readouterr().err


def test_cli_invalid_model(capsys):
    with patch.object(sys, "argv", ["generate-voice", "Hi", "--model", "nope"]):
        with pytest.raises(SystemExit):
            main()
    assert "invalid choice" in capsys.readouterr().err
