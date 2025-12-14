import pytest
from unittest.mock import MagicMock
import sys
from google.cloud import texttospeech

@pytest.fixture
def mock_tts_client(monkeypatch):
    """Mocks the Google Cloud TextToSpeechClient."""
    mock_client = MagicMock()
    
    # Mock list_voices
    mock_voices_response = MagicMock()
    voice = MagicMock(spec=texttospeech.Voice)
    voice.name = "en-US-Chirp3-HD-Zephyr"
    voice.ssml_gender = texttospeech.SsmlVoiceGender.MALE
    mock_voices_response.voices = [voice]
    mock_client.list_voices.return_value = mock_voices_response
    
    # Mock synthesize_speech
    mock_synthesize_response = MagicMock()
    mock_synthesize_response.audio_content = b"fake_audio_content"
    mock_client.synthesize_speech.return_value = mock_synthesize_response

    # Patch the core module where the client is instantiated
    monkeypatch.setattr(
        "generate_gemini_voice.core.get_text_to_speech_client",
        lambda: mock_client
    )
    return mock_client

@pytest.fixture
def mock_pygame(monkeypatch):
    """Mocks pygame to prevent audio playback during tests."""
    mock_pygame_mod = MagicMock()
    mock_mixer = MagicMock()
    mock_music = MagicMock()
    
    mock_pygame_mod.mixer = mock_mixer
    mock_pygame_mod.mixer.music = mock_music
    mock_music.get_busy.side_effect = [True, False] # Play once then stop
    
    monkeypatch.setattr("generate_gemini_voice.utils.pygame", mock_pygame_mod)
    return mock_pygame_mod
