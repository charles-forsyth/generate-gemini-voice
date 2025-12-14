from typing import Optional
from google.cloud import texttospeech
from google.api_core import exceptions
from google.api_core.client_options import ClientOptions
import google.auth.exceptions
from generate_gemini_voice.config import settings

def get_text_to_speech_client() -> texttospeech.TextToSpeechClient:
    """Returns an authenticated TextToSpeechClient."""
    try:
        if settings.google_api_key:
            options = ClientOptions(api_key=settings.google_api_key)
            return texttospeech.TextToSpeechClient(client_options=options)
        
        return texttospeech.TextToSpeechClient()
    except google.auth.exceptions.DefaultCredentialsError as e:
        raise RuntimeError(
            "Google Cloud Credentials not found.\n"
            "Please run 'gcloud auth application-default login', "
            "set the GOOGLE_APPLICATION_CREDENTIALS environment variable, "
            "or set GOOGLE_API_KEY in your .env file."
        ) from e

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
        # Note: 'parent' is often required for quota/billing attribution 
        # with newer models or specific quotas.
        # If API key is used, project ID might be inferred from the key, 
        # but passing parent explicitly is safer if project_id is known.
        request_kwargs = {
            "input": synthesis_input,
            "voice": voice_params,
            "audio_config": audio_config,
        }
        
        # Only add parent if project_id is available. 
        # API keys are tied to a project, so explicit parent might be redundant 
        # but good practice.
        if actual_project_id:
             request_kwargs["parent"] = f"projects/{actual_project_id}"

        response = client.synthesize_speech(request=request_kwargs)
    except exceptions.GoogleAPICallError as e:
        raise RuntimeError(f"Error during speech synthesis: {e}") from e

    with open(output_file, "wb") as out:
        out.write(response.audio_content)