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
                MockClient.assert_called_once()
                call_args = MockClient.call_args
                assert call_args.kwargs['client_options'] == MockOptions.return_value

def test_client_init_without_api_key():
    """Test that TextToSpeechClient is initialized without ClientOptions when API key is None."""
    with patch.object(settings, 'google_api_key', None):
        with patch('generate_gemini_voice.core.texttospeech.TextToSpeechClient') as MockClient:
            get_text_to_speech_client()
            
            MockClient.assert_called_once()
            # client_options shouldn't be in kwargs or should be None/Default
            # In our implementation we call it with no args: TextToSpeechClient()
            assert 'client_options' not in MockClient.call_args.kwargs
