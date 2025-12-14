import pytest
from generate_gemini_voice.core import list_chirp_voices, generate_speech
from google.cloud import texttospeech
from google.api_core import exceptions

def test_list_chirp_voices(mock_tts_client):
    """Test listing voices filters for Chirp3."""
    voices = list_chirp_voices()
    assert len(voices) == 1
    assert voices[0].name == "en-US-Chirp3-HD-Zephyr"
    mock_tts_client.list_voices.assert_called_once_with(language_code="en-US")

def test_list_chirp_voices_error(mock_tts_client):
    """Test error handling when listing voices fails."""
    mock_tts_client.list_voices.side_effect = exceptions.GoogleAPICallError("Error")
    with pytest.raises(RuntimeError, match="Error fetching voice list"):
        list_chirp_voices()

def test_generate_speech_success(mock_tts_client, tmp_path):
    """Test successful speech generation."""
    output_file = tmp_path / "test.mp3"
    generate_speech(
        text="Hello",
        output_file=str(output_file),
        project_id="test-project"
    )
    
    assert output_file.exists()
    assert output_file.read_bytes() == b"fake_audio_content"
    mock_tts_client.synthesize_speech.assert_called_once()

def test_generate_speech_invalid_format():
    """Test error for invalid audio format."""
    with pytest.raises(ValueError, match="Unsupported audio format"):
        generate_speech(text="Hi", output_file="out.mp3", audio_format="INVALID")

def test_generate_speech_api_error(mock_tts_client, tmp_path):
    """Test error handling during synthesis."""
    mock_tts_client.synthesize_speech.side_effect = exceptions.GoogleAPICallError("Error")
    with pytest.raises(RuntimeError, match="Error during speech synthesis"):
        generate_speech(text="Hi", output_file=str(tmp_path / "out.mp3"))
