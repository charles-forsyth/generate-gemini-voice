import struct
import sys
from concurrent.futures import ThreadPoolExecutor
from typing import Optional

from google.api_core import exceptions
from google.api_core import retry as api_retry
from google.api_core.client_options import ClientOptions
from google.cloud import texttospeech

from generate_gemini_voice.config import (
    PLACEHOLDER_KEY,
    USER_CONFIG_FILE,
    mask_key,
    settings,
)
from generate_gemini_voice.utils import split_text_into_chunks

# --- Models -----------------------------------------------------------------
# "chirp3" = classic Chirp 3 HD voices (API key works).
# gemini-* = Gemini-TTS: steerable with a natural-language --prompt.
#   These route through Vertex AI, which does NOT accept API keys, so they use
#   gcloud application-default credentials (gcloud auth application-default login).
CHIRP_MODEL = "chirp3"
GEMINI_MODELS = (
    "gemini-2.5-flash-tts",  # GA, fast, cheap: default
    "gemini-2.5-pro-tts",  # GA, highest quality
    "gemini-3.1-flash-tts-preview",  # newest, preview
    "gemini-2.5-flash-lite-preview-tts",
)
DEFAULT_MODEL = "gemini-2.5-flash-tts"
DEFAULT_VOICE = "Zephyr"
MODEL_CHOICES = (CHIRP_MODEL, *GEMINI_MODELS)

# Shared by Chirp 3 HD and Gemini-TTS.
VOICES = (
    "Achernar",
    "Achird",
    "Algenib",
    "Algieba",
    "Alnilam",
    "Aoede",
    "Autonoe",
    "Callirrhoe",
    "Charon",
    "Despina",
    "Enceladus",
    "Erinome",
    "Fenrir",
    "Gacrux",
    "Iapetus",
    "Kore",
    "Laomedeia",
    "Leda",
    "Orus",
    "Pulcherrima",
    "Puck",
    "Rasalgethi",
    "Sadachbia",
    "Sadaltager",
    "Schedar",
    "Sulafat",
    "Umbriel",
    "Vindemiatrix",
    "Zephyr",
    "Zubenelgenubi",
)

# Retry transient failures (rate limits, brief outages) with backoff.
_RETRY = api_retry.Retry(
    predicate=api_retry.if_exception_type(
        exceptions.TooManyRequests,
        exceptions.ServiceUnavailable,
        exceptions.InternalServerError,
        exceptions.DeadlineExceeded,
    ),
    initial=1.0,
    maximum=20.0,
    multiplier=2.0,
    timeout=120.0,
)


def is_gemini(model: str) -> bool:
    return model.startswith("gemini-")


def resolve_voice(voice: str, model: str, language_code: str) -> str:
    """Accept short names (Zephyr) or full Chirp names (en-US-Chirp3-HD-Zephyr)."""
    short = voice.split("-")[-1] if "Chirp3" in voice else voice
    if is_gemini(model):
        return short
    if "Chirp3" in voice:
        return voice
    return f"{language_code}-Chirp3-HD-{short}"


def get_text_to_speech_client(
    model: str = CHIRP_MODEL, project_id: Optional[str] = None
) -> texttospeech.TextToSpeechClient:
    """Build a client. Chirp: API key. Gemini-TTS: application-default credentials."""
    quota_project = project_id or settings.gcloud_project

    if is_gemini(model):
        try:
            return texttospeech.TextToSpeechClient(
                client_options=ClientOptions(quota_project_id=quota_project)
            )
        except Exception as e:  # google.auth.exceptions.DefaultCredentialsError
            raise RuntimeError(
                f"Gemini-TTS model '{model}' needs Google application-default "
                "credentials (API keys are not accepted for these models).\n"
                "Run: gcloud auth application-default login\n"
                "Or use --model chirp3 to use your API key."
            ) from e

    api_key = settings.google_api_key
    if not api_key:
        raise RuntimeError(
            f"GOOGLE_API_KEY not set. Add it to {USER_CONFIG_FILE}\n"
            "(restrict the key to texttospeech.googleapis.com)."
        )
    if PLACEHOLDER_KEY in api_key:
        raise RuntimeError(
            f"Placeholder API Key detected in {USER_CONFIG_FILE}. "
            "Replace it with your real key."
        )
    return texttospeech.TextToSpeechClient(
        client_options=ClientOptions(api_key=api_key)
    )


def _explain(e: Exception, model: str) -> str:
    """Turn common API errors into actionable messages without leaking secrets."""
    msg = str(e)
    if isinstance(e, exceptions.PermissionDenied) and not is_gemini(model):
        return (
            f"Permission denied using API key {mask_key(settings.google_api_key)}. "
            "The key may be deleted, or not allowed for texttospeech.googleapis.com."
        )
    if isinstance(e, exceptions.InvalidArgument) and "API key not valid" in msg:
        return (
            f"API key {mask_key(settings.google_api_key)} is not valid "
            f"(deleted or mistyped). Update {USER_CONFIG_FILE}."
        )
    return msg


def list_voices(model: str = DEFAULT_MODEL, language_code: str = "en-US") -> list[str]:
    """Voice names for the given model."""
    if is_gemini(model):
        return list(VOICES)
    client = get_text_to_speech_client(CHIRP_MODEL)
    try:
        resp = client.list_voices(language_code=language_code, retry=_RETRY)
    except exceptions.GoogleAPICallError as e:
        raise RuntimeError(f"Error fetching voice list: {_explain(e, model)}") from e
    return [v.name for v in resp.voices if "Chirp3" in v.name]


def _synthesize_single_chunk(
    client: texttospeech.TextToSpeechClient,
    text: str,
    voice_params: texttospeech.VoiceSelectionParams,
    audio_config: texttospeech.AudioConfig,
    model: str,
    prompt: Optional[str],
) -> bytes:
    if is_gemini(model) and prompt:
        synthesis_input = texttospeech.SynthesisInput(text=text, prompt=prompt)
    else:
        synthesis_input = texttospeech.SynthesisInput(text=text)
    try:
        response = client.synthesize_speech(
            input=synthesis_input,
            voice=voice_params,
            audio_config=audio_config,
            retry=_RETRY,
        )
        return response.audio_content
    except exceptions.GoogleAPICallError as e:
        snippet = text[:50] + "..." if len(text) > 50 else text
        raise RuntimeError(
            f"Speech synthesis failed for chunk '{snippet}': {_explain(e, model)}"
        ) from e


def generate_speech(
    text: str,
    output_file: str,
    voice_name: str = DEFAULT_VOICE,
    language_code: str = "en-US",
    audio_format: str = "MP3",
    project_id: Optional[str] = None,
    model: str = DEFAULT_MODEL,
    prompt: Optional[str] = None,
) -> None:
    """Synthesize text to a file. Long text is chunked, synthesized in parallel,
    and streamed to disk in order."""
    encodings = {
        "MP3": texttospeech.AudioEncoding.MP3,
        "WAV": texttospeech.AudioEncoding.LINEAR16,
        "OGG": texttospeech.AudioEncoding.OGG_OPUS,
    }
    audio_format = audio_format.upper()
    if audio_format not in encodings:
        raise ValueError(f"Unsupported audio format: {audio_format}")
    if model not in MODEL_CHOICES:
        raise ValueError(f"Unsupported model: {model}. Choose from {MODEL_CHOICES}")

    client = get_text_to_speech_client(model, project_id)
    voice = resolve_voice(voice_name, model, language_code)
    if is_gemini(model):
        voice_params = texttospeech.VoiceSelectionParams(
            language_code=language_code, name=voice, model_name=model
        )
    else:
        voice_params = texttospeech.VoiceSelectionParams(
            language_code=language_code, name=voice
        )
    audio_config = texttospeech.AudioConfig(audio_encoding=encodings[audio_format])

    chunks = split_text_into_chunks(text)
    total = len(chunks)

    with open(output_file, "wb") as out_f:
        data_bytes = 0
        header_written = False
        with ThreadPoolExecutor(max_workers=5) as pool:
            results = pool.map(
                lambda c: _synthesize_single_chunk(
                    client, c, voice_params, audio_config, model, prompt
                ),
                chunks,
            )
            for i, audio in enumerate(results):
                if total > 1:
                    print(
                        f"Processing chunk {i + 1}/{total}...",
                        file=sys.stderr,
                        end="\r",
                    )
                if not audio:
                    continue
                if audio_format == "WAV":
                    if not header_written:
                        if audio[:4] != b"RIFF":
                            raise RuntimeError(
                                "Unexpected WAV data from API (no RIFF header)."
                            )
                        out_f.write(audio)
                        data_bytes += len(audio) - 44
                        header_written = True
                    elif len(audio) > 44:
                        out_f.write(audio[44:])
                        data_bytes += len(audio) - 44
                else:
                    out_f.write(audio)
        if total > 1:
            print(f"\nFinished processing {total} chunks.", file=sys.stderr)

        if audio_format == "WAV" and header_written:
            out_f.seek(4)
            out_f.write(struct.pack("<I", 36 + data_bytes))
            out_f.seek(40)
            out_f.write(struct.pack("<I", data_bytes))
