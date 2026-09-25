from unittest.mock import MagicMock, patch

import pytest

from generate_gemini_voice.config import settings
from generate_gemini_voice.core import CHIRP_MODEL, get_text_to_speech_client


def test_client_init_with_valid_api_key():
    with patch.object(settings, "google_api_key", "some_valid_api_key"):
        with patch(
            "generate_gemini_voice.core.texttospeech.TextToSpeechClient"
        ) as MockClient:
            with patch("generate_gemini_voice.core.ClientOptions") as MockOpts:
                opts = MagicMock()
                MockOpts.return_value = opts
                client = get_text_to_speech_client(CHIRP_MODEL)
                MockClient.assert_called_once_with(client_options=opts)
                assert client == MockClient.return_value


def test_client_init_with_placeholder_key():
    with patch.object(settings, "google_api_key", "replace_with_your_api_key"):
        with pytest.raises(RuntimeError, match="Placeholder API Key detected"):
            get_text_to_speech_client(CHIRP_MODEL)


def test_client_init_without_api_key():
    with patch.object(settings, "google_api_key", None):
        with pytest.raises(RuntimeError, match="GOOGLE_API_KEY not set"):
            get_text_to_speech_client(CHIRP_MODEL)


def test_error_messages_never_contain_full_key():
    from google.api_core import exceptions

    from generate_gemini_voice.core import _explain

    key = "AIzaSyEXAMPLEEXAMPLEEXAMPLEEXAMPLE9A0w"
    with patch.object(settings, "google_api_key", key):
        msg = _explain(exceptions.PermissionDenied("denied"), CHIRP_MODEL)
        assert key not in msg and "...9A0w" in msg


def test_settings_ignore_home_and_cwd_env():
    from generate_gemini_voice.config import USER_CONFIG_FILE, Settings

    assert Settings.model_config["env_file"] == str(USER_CONFIG_FILE)
