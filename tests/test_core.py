from unittest.mock import MagicMock, patch

import pytest
from google.api_core import exceptions

from generate_gemini_voice.config import mask_key, settings
from generate_gemini_voice.core import (
    CHIRP_MODEL,
    VOICES,
    generate_speech,
    get_text_to_speech_client,
    list_voices,
    resolve_voice,
)


def test_chirp_client_uses_api_key():
    with patch.object(settings, "google_api_key", "dummy_valid_key_12345"):
        with patch(
            "generate_gemini_voice.core.texttospeech.TextToSpeechClient"
        ) as MockClient:
            with patch("generate_gemini_voice.core.ClientOptions") as MockOpts:
                opts = MagicMock()
                MockOpts.return_value = opts
                client = get_text_to_speech_client(CHIRP_MODEL)
                MockOpts.assert_called_once_with(api_key="dummy_valid_key_12345")
                MockClient.assert_called_once_with(client_options=opts)
                assert client == MockClient.return_value


def test_gemini_client_uses_adc_not_api_key():
    with patch.object(settings, "google_api_key", "should_not_be_used"):
        with patch("generate_gemini_voice.core.texttospeech.TextToSpeechClient"):
            with patch("generate_gemini_voice.core.ClientOptions") as MockOpts:
                get_text_to_speech_client("gemini-2.5-flash-tts", "proj-x")
                MockOpts.assert_called_once_with(quota_project_id="proj-x")


def test_resolve_voice():
    assert resolve_voice("Zephyr", "chirp3", "en-US") == "en-US-Chirp3-HD-Zephyr"
    assert (
        resolve_voice("en-US-Chirp3-HD-Kore", "chirp3", "en-US")
        == "en-US-Chirp3-HD-Kore"
    )
    assert (
        resolve_voice("en-US-Chirp3-HD-Kore", "gemini-2.5-flash-tts", "en-US") == "Kore"
    )
    assert resolve_voice("Puck", "gemini-2.5-pro-tts", "en-US") == "Puck"


def test_mask_key_never_reveals_key():
    assert mask_key("AIzaSyEXAMPLEEXAMPLEEXAMPLEEXAMPLE9A0w") == "...9A0w"
    assert mask_key(None) == "<none>"
    assert mask_key("short") == "<set>"


def test_list_voices_gemini_is_static():
    assert list_voices("gemini-2.5-flash-tts") == list(VOICES)


def test_list_voices_chirp_filters(mock_tts_client):
    voices = list_voices(CHIRP_MODEL)
    assert voices == ["en-US-Chirp3-HD-Zephyr"]
    mock_tts_client.list_voices.assert_called_once()


def test_list_voices_chirp_error(mock_tts_client):
    mock_tts_client.list_voices.side_effect = exceptions.GoogleAPICallError("Error")
    with pytest.raises(RuntimeError, match="Error fetching voice list"):
        list_voices(CHIRP_MODEL)


def test_generate_speech_gemini_sends_model_and_prompt(mock_tts_client, tmp_path):
    out = tmp_path / "test.mp3"
    generate_speech(
        text="Hello",
        output_file=str(out),
        model="gemini-2.5-flash-tts",
        prompt="Say it warmly.",
        voice_name="Kore",
    )
    assert out.read_bytes() == b"fake_audio_content"
    kwargs = mock_tts_client.synthesize_speech.call_args.kwargs
    assert kwargs["voice"].model_name == "gemini-2.5-flash-tts"
    assert kwargs["voice"].name == "Kore"
    assert kwargs["input"].prompt == "Say it warmly."
    assert "retry" in kwargs


def test_generate_speech_chirp_no_model_name(mock_tts_client, tmp_path):
    out = tmp_path / "test.mp3"
    generate_speech(
        text="Hello", output_file=str(out), model=CHIRP_MODEL, prompt="ignored"
    )
    kwargs = mock_tts_client.synthesize_speech.call_args.kwargs
    assert kwargs["voice"].model_name == ""
    assert kwargs["voice"].name == "en-US-Chirp3-HD-Zephyr"
    assert kwargs["input"].prompt == ""


def test_generate_speech_invalid_format():
    with pytest.raises(ValueError, match="Unsupported audio format"):
        generate_speech(text="Hi", output_file="out.mp3", audio_format="INVALID")


def test_generate_speech_invalid_model():
    with pytest.raises(ValueError, match="Unsupported model"):
        generate_speech(text="Hi", output_file="out.mp3", model="nope")


def test_generate_speech_api_error(mock_tts_client, tmp_path):
    mock_tts_client.synthesize_speech.side_effect = exceptions.GoogleAPICallError(
        "Error"
    )
    with pytest.raises(RuntimeError, match="Speech synthesis failed"):
        generate_speech(
            text="Hi",
            output_file=str(tmp_path / "out.mp3"),
            model="gemini-2.5-flash-tts",
        )
