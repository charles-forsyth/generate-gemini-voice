import pytest
from unittest.mock import patch, MagicMock
from generate_gemini_voice.core import get_text_to_speech_client, EXPECTED_API_KEY
from generate_gemini_voice.config import settings


def test_client_init_with_expected_api_key():
    """Test that TextToSpeechClient is initialized with ClientOptions when the EXPECTED API key is set."""
    with patch.object(settings, 'google_api_key', EXPECTED_API_KEY):
        with patch('generate_gemini_voice.core.texttospeech.TextToSpeechClient') as MockClient:
            with patch('generate_gemini_voice.core.ClientOptions') as MockClientOptions:
                # Configure the return value of MockClientOptions to have an api_key attribute
                mock_client_options_instance = MagicMock()
                mock_client_options_instance.api_key = EXPECTED_API_KEY
                MockClientOptions.return_value = mock_client_options_instance

                client = get_text_to_speech_client()
                MockClient.assert_called_once_with(client_options=mock_client_options_instance)
                assert client == MockClient.return_value

def test_client_init_with_placeholder_key():
    """Test that TextToSpeechClient raises RuntimeError when API key is the placeholder."""
    with patch.object(settings, 'google_api_key', 'replace_with_your_api_key'):
        with pytest.raises(RuntimeError, match="Placeholder API Key detected"):
            get_text_to_speech_client()

def test_client_init_with_unexpected_api_key():
    """Test that TextToSpeechClient raises RuntimeError when API key is set but not the EXPECTED one."""
    with patch.object(settings, 'google_api_key', 'UNEXPECTED_API_KEY'):
        with pytest.raises(RuntimeError, match="An unexpected GOOGLE_API_KEY was loaded"):
            get_text_to_speech_client()

def test_client_init_without_api_key():
    """Test that TextToSpeechClient initialization raises RuntimeError when API key is None."""
    with patch.object(settings, 'google_api_key', None):
        with pytest.raises(RuntimeError, match="GOOGLE_API_KEY not found"):
            get_text_to_speech_client()
