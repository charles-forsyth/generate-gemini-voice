import pytest
from unittest.mock import patch, MagicMock
from generate_gemini_voice.core import get_text_to_speech_client
from generate_gemini_voice.config import settings


def test_client_init_with_api_key():
    """Test that TextToSpeechClient is initialized with ClientOptions when API key is set."""
    with patch.object(settings, 'google_api_key', 'TEST_API_KEY'):
        with patch('generate_gemini_voice.core.texttospeech.TextToSpeechClient') as MockClient:
            with patch('generate_gemini_voice.core.ClientOptions') as MockOptions:
                get_text_to_speech_client()
                
                MockOptions.assert_called_with(api_key='TEST_API_KEY')
                MockClient.assert_called_once_with(client_options=MockOptions.return_value)

def test_client_init_without_api_key():
    """Test that TextToSpeechClient initialization raises RuntimeError when API key is None."""
    with patch.object(settings, 'google_api_key', None):
        with pytest.raises(RuntimeError, match="GOOGLE_API_KEY not found"):
            get_text_to_speech_client()