from typing import Optional
from concurrent.futures import ThreadPoolExecutor
from google.cloud import texttospeech
from google.api_core import exceptions
from google.api_core.client_options import ClientOptions
import sys
import struct
from generate_gemini_voice.config import settings, USER_CONFIG_FILE
from generate_gemini_voice.utils import split_text_into_chunks

# Define the expected valid API key for strict checking.
# This is a temporary measure for debugging.
# EXPECTED_API_KEY removed for security and usability.

def get_text_to_speech_client() -> texttospeech.TextToSpeechClient:
    """Returns an authenticated TextToSpeechClient using an API key. Raises RuntimeError if API key is not set or is incorrect."""
    api_key = settings.google_api_key
    
    if not api_key:
        raise RuntimeError(
            "GOOGLE_API_KEY not found in environment or .env file.\n"
            "Please set GOOGLE_API_KEY to your Google Cloud API Key."
        )

    if "replace_with_your_api_key" in api_key:
        raise RuntimeError(
            f"Placeholder API Key detected in {USER_CONFIG_FILE} or other .env file.\n"
            "Please edit this file and replace 'replace_with_your_api_key' with your actual Google Cloud API Key."
        )

    options = ClientOptions(api_key=api_key)
    return texttospeech.TextToSpeechClient(client_options=options)

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
    """Generates speech from text using Google Cloud Text-to-Speech. Handles long text by chunking and streaming writes."""
    
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
    total_chunks = len(chunks)
    
    # 2. Process chunks in parallel and stream to file
    with open(output_file, "wb") as out_f:
        # For WAV, we might need to patch the header later.
        # We'll keep track of total data bytes written.
        total_data_bytes = 0
        wav_header_placeholder_written = False
        
        # max_workers=5 as requested
        with ThreadPoolExecutor(max_workers=5) as executor:
            # map guarantees results are yielded in the same order as inputs
            futures = executor.map(
                lambda chunk: _synthesize_single_chunk(chunk, voice_params, audio_config, client),
                chunks
            )
            
            for i, audio_content in enumerate(futures):
                # Progress logging
                if total_chunks > 1:
                    print(f"Processing chunk {i+1}/{total_chunks}...", file=sys.stderr, end='\r')

                if not audio_content:
                    continue

                if audio_format.upper() == "WAV":
                    # WAV logic:
                    # First chunk: Write header + data.
                    # Subsequent chunks: Strip 44-byte header, write data.
                    if not wav_header_placeholder_written:
                        # This is the first chunk. 
                        # Write the whole thing (including header).
                        out_f.write(audio_content)
                        total_data_bytes += len(audio_content) - 44 # exclude header from data count
                        wav_header_placeholder_written = True
                    else:
                        # Strip header (44 bytes)
                        if len(audio_content) >= 44:
                            data_part = audio_content[44:]
                            out_f.write(data_part)
                            total_data_bytes += len(data_part)
                else:
                    # MP3/OGG: Just append
                    out_f.write(audio_content)
            
            if total_chunks > 1:
                print(f"\nFinished processing {total_chunks} chunks.", file=sys.stderr)

        # 3. Patch WAV header if needed
        if audio_format.upper() == "WAV" and wav_header_placeholder_written:
            # We need to update ChunkSize and Subchunk2Size
            # ChunkSize (offset 4) = 36 + total_data_bytes
            # Subchunk2Size (offset 40) = total_data_bytes
            
            total_file_len = 36 + total_data_bytes
            
            out_f.seek(4)
            out_f.write(struct.pack('<I', total_file_len))
            
            out_f.seek(40)
            out_f.write(struct.pack('<I', total_data_bytes))