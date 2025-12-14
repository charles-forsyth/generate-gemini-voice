from typing import Optional
from concurrent.futures import ThreadPoolExecutor
from google.cloud import texttospeech
from google.api_core import exceptions
from google.api_core.client_options import ClientOptions
import sys
from generate_gemini_voice.config import settings, USER_CONFIG_FILE
from generate_gemini_voice.utils import split_text_into_chunks, combine_audio_data

# Define the expected valid API key for strict checking.
# This is a temporary measure for debugging.
EXPECTED_API_KEY = "AIzaSyCTSY0AKGrDHmzSyuV_9MyTBpMGKOKQl2M"

def get_text_to_speech_client() -> texttospeech.TextToSpeechClient:
    """Returns an authenticated TextToSpeechClient using an API key. Raises RuntimeError if API key is not set or is incorrect."""
    api_key = settings.google_api_key
    
    if not api_key:
        raise RuntimeError(
            "GOOGLE_API_KEY not found in environment or .env file.\n"
            "Please set GOOGLE_API_KEY to your Google Cloud API Key."
        )

    if api_key == EXPECTED_API_KEY:
        options = ClientOptions(api_key=api_key)
        return texttospeech.TextToSpeechClient(client_options=options)
    elif "replace_with_your_api_key" in api_key:
        raise RuntimeError(
            f"Placeholder API Key detected in {USER_CONFIG_FILE} or other .env file.\n"
            "Please edit this file and replace 'replace_with_your_api_key' with your actual Google Cloud API Key (the one starting with AIzaSyCTSY0AKGrDHmzSyuV_9MyTBpMGKOKQl2M)."
        )
    else:
        raise RuntimeError(
            f"An unexpected GOOGLE_API_KEY was loaded: '{api_key}'.\n"
            f"Please ensure your GOOGLE_API_KEY is set to '{EXPECTED_API_KEY}' "
            f"in {USER_CONFIG_FILE} or another .env file taking precedence.\n"
            "Also, check your shell environment for any conflicting GOOGLE_API_KEY exports."
        )

def list_chirp_voices(language_code: str = "en-US") -> list[texttospeech.Voice]:
    """Returns a list of available 'Chirp3' voices for the given language."""
    client = get_text_to_speech_client()
    try:
        voices = client.list_voices(language_code=language_code)
        return [v for v in voices.voices if "Chirp3" in v.name]
    except exceptions.GoogleAPICallError as e:
        raise RuntimeError(f"Error fetching voice list: {e}") from e

def _synthesize_single_chunk(
    text: str,
    voice_params: texttospeech.VoiceSelectionParams,
    audio_config: texttospeech.AudioConfig,
    client: Optional[texttospeech.TextToSpeechClient] = None
) -> bytes:
    """
    Helper to synthesize a single chunk of text.
    Client is optional to allow thread-local client creation if needed, 
    but gRPC clients are generally thread-safe.
    """
    if client is None:
        client = get_text_to_speech_client()
        
    synthesis_input = texttospeech.SynthesisInput(text=text)
    try:
        response = client.synthesize_speech(
            request={
                "input": synthesis_input,
                "voice": voice_params,
                "audio_config": audio_config,
            }
        )
        return response.audio_content
    except exceptions.GoogleAPICallError as e:
        # Include text snippet in error for context
        snippet = text[:50] + "..." if len(text) > 50 else text
        raise RuntimeError(f"Error during speech synthesis for chunk '{snippet}': {e}") from e

def generate_speech(
    text: str,
    output_file: str,
    voice_name: str = "en-US-Chirp3-HD-Zephyr",
    language_code: str = "en-US",
    audio_format: str = "MP3",
    project_id: Optional[str] = None
) -> None:
    """Generates speech from text using Google Cloud Text-to-Speech. Handles long text by chunking and parallel execution."""
    
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
    
    # We create one client instance to share. 
    # Google Cloud clients are thread-safe.
    client = get_text_to_speech_client()
    
    voice_params = texttospeech.VoiceSelectionParams(
        language_code=language_code, 
        name=voice_name
    )
    audio_config = texttospeech.AudioConfig(audio_encoding=audio_encoding)

    # 1. Split text
    chunks = split_text_into_chunks(text)
    audio_data_list = []

    # 2. Process chunks in parallel
    # max_workers=5 as requested
    with ThreadPoolExecutor(max_workers=5) as executor:
        # map guarantees results are yielded in the same order as inputs
        # We use a lambda or partial to pass constant args
        futures = executor.map(
            lambda chunk: _synthesize_single_chunk(chunk, voice_params, audio_config, client),
            chunks
        )
        
        # This iterates over results as they complete (preserving order), 
        # raising any exceptions encountered.
        for result in futures:
            audio_data_list.append(result)

    # 3. Combine audio
    final_audio = combine_audio_data(audio_data_list, audio_format)

    # 4. Write to file
    with open(output_file, "wb") as out:
        out.write(final_audio)