import pytest
from generate_gemini_voice.core import list_chirp_voices, generate_speech, get_text_to_speech_client
from generate_gemini_voice.config import settings
from google.cloud import texttospeech
from google.api_core import exceptions
from unittest.mock import MagicMock, patch

def test_get_text_to_speech_client_api_key_set():
    """Test that TextToSpeechClient is initialized with ClientOptions when ANY valid-looking API key is set."""
    dummy_key = "dummy_valid_key_12345"
    with patch.object(settings, 'google_api_key', dummy_key):
        with patch('generate_gemini_voice.core.texttospeech.TextToSpeechClient') as MockClient:
            with patch('generate_gemini_voice.core.ClientOptions') as MockClientOptions:
                # Configure the return value of MockClientOptions to have an api_key attribute
                mock_client_options_instance = MagicMock()
                mock_client_options_instance.api_key = dummy_key
                MockClientOptions.return_value = mock_client_options_instance

                client = get_text_to_speech_client()
                MockClient.assert_called_once_with(client_options=mock_client_options_instance)
                assert client == MockClient.return_value

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
    
    # Verify synthesize_speech was called correctly without parent as a direct arg
    mock_tts_client.synthesize_speech.assert_called_once()
    call_args, call_kwargs = mock_tts_client.synthesize_speech.call_args
    
    assert "request" in call_kwargs
    # The request is now a dict when passed to the mock, check its contents
    request_dict = call_kwargs["request"]
    assert "input" in request_dict
    assert "voice" in request_dict
    assert "audio_config" in request_dict

    # No parent argument should be passed directly
    assert "parent" not in call_kwargs

def test_generate_speech_invalid_format():
    """Test error for invalid audio format."""
    with pytest.raises(ValueError, match="Unsupported audio format"):
        generate_speech(text="Hi", output_file="out.mp3", audio_format="INVALID")

def test_generate_speech_api_error(mock_tts_client, tmp_path):
    """Test error handling during synthesis."""
    mock_tts_client.synthesize_speech.side_effect = exceptions.GoogleAPICallError("Error")
    with pytest.raises(RuntimeError, match="Error during speech synthesis"):
        generate_speech(text="Hi", output_file=str(tmp_path / "out.mp3"))