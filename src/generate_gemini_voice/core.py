from typing import Optional
from google.cloud import texttospeech
from google.api_core import exceptions
from google.api_core.client_options import ClientOptions
import sys
from generate_gemini_voice.config import settings, USER_CONFIG_FILE

def get_text_to_speech_client() -> texttospeech.TextToSpeechClient:
    """Returns an authenticated TextToSpeechClient using an API key. Raises RuntimeError if API key is not set."""
    api_key = settings.google_api_key
    
    if api_key and "replace_with_your_api_key" in api_key:
        raise RuntimeError(
            f"Placeholder API Key detected in {USER_CONFIG_FILE}.\n"
            "Please edit this file and replace 'replace_with_your_api_key' with your actual Google Cloud API Key."
        )

    if api_key:
        print("Authenticating with GOOGLE_API_KEY.", file=sys.stderr)
        options = ClientOptions(api_key=api_key)
        return texttospeech.TextToSpeechClient(client_options=options)
    else:
        raise RuntimeError(
            "GOOGLE_API_KEY not found in environment or .env file.\n"
            "Please set GOOGLE_API_KEY to your Google Cloud API Key."
        )

def list_chirp_voices(language_code: str = "en-US") -> list[texttospeech.Voice]:
    """Returns a list of available 'Chirp3' voices for the given language."""
    client = get_text_to_speech_client()
    try:
        voices = client.list_voices(language_code=language_code)
        return [v for v in voices.voices if "Chirp3" in v.name]
    except exceptions.GoogleAPICallError as e:
        raise RuntimeError(f"Error fetching voice list: {e}") from e

def generate_speech(
    text: str,
    output_file: str,
    voice_name: str = "en-US-Chirp3-HD-Zephyr",
    language_code: str = "en-US",
    audio_format: str = "MP3",
    project_id: Optional[str] = None
) -> None:
    """Generates speech from text using Google Cloud Text-to-Speech."""
    
    # Map format string to AudioEncoding
    audio_encoding_map = {
        "MP3": texttospeech.AudioEncoding.MP3,
        "WAV": texttospeech.AudioEncoding.LINEAR16,
        "OGG": texttospeech.AudioEncoding.OGG_OPUS,
    }
    
    if audio_format not in audio_encoding_map:
        raise ValueError(f"Unsupported audio format: {audio_format}")

    audio_encoding = audio_encoding_map[audio_format]
    actual_project_id = project_id or settings.gcloud_project
    
    client = get_text_to_speech_client()
    synthesis_input = texttospeech.SynthesisInput(text=text)
    voice_params = texttospeech.VoiceSelectionParams(
        language_code=language_code, 
        name=voice_name
    )
    audio_config = texttospeech.AudioConfig(audio_encoding=audio_encoding)

    try:
        # When using an API key, the 'parent' argument is not expected in synthesize_speech.
        # Project ID is implicitly handled by the API key itself for billing/quota.
        response = client.synthesize_speech(
            request={
                "input": synthesis_input,
                "voice": voice_params,
                "audio_config": audio_config,
            }
        )

    except exceptions.GoogleAPICallError as e:
        raise RuntimeError(f"Error during speech synthesis: {e}") from e

    with open(output_file, "wb") as out:
        out.write(response.audio_content)
