import shutil
import struct
import subprocess
import sys
import time
import wave
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
# Three backends:
#   Gemini API  (GEMINI_API_KEY): gemini-3.8-* TTS. Newest, stable (Sep 2026).
#   Cloud TTS + ADC:              gemini-2.5-*-tts. GA on Cloud TTS; fallback.
#   Cloud TTS + API key:          chirp3 (classic Chirp 3 HD voices).
# Dropped: gemini-3.1-flash-tts-preview (Google marks it legacy) and
# gemini-2.5-flash-lite-preview-tts (never went GA).
CHIRP_MODEL = "chirp3"
GEMINI_API_MODELS = (
    "gemini-3.8-flash-tts",  # default: best quality, voice direction
    "gemini-3.8-flash-lite-tts",  # cheaper, faster
)
CLOUD_GEMINI_MODELS = (
    "gemini-2.5-flash-tts",  # GA on Cloud TTS
    "gemini-2.5-pro-tts",  # GA on Cloud TTS
)
GEMINI_MODELS = (*GEMINI_API_MODELS, *CLOUD_GEMINI_MODELS)
DEFAULT_MODEL = "gemini-3.8-flash-tts"
DEFAULT_VOICE = "Zephyr"
MODEL_CHOICES = (*GEMINI_MODELS, CHIRP_MODEL)
# Gemini API returns raw 16-bit mono PCM at 24 kHz.
PCM_RATE = 24000

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


def is_gemini_api(model: str) -> bool:
    return model in GEMINI_API_MODELS


def _gemini_api_key() -> str:
    key = settings.gemini_api_key
    if not key or PLACEHOLDER_KEY in key:
        raise RuntimeError(
            f"GEMINI_API_KEY not set in {USER_CONFIG_FILE}.\n"
            "Create a key restricted to generativelanguage.googleapis.com, or use\n"
            "--model gemini-2.5-flash-tts (Cloud TTS) or --model chirp3."
        )
    return key


def _wav_pcm(data: bytes) -> bytes:
    """PCM samples of a RIFF/WAVE blob: the `data` chunk only.

    Gemini 3.8 TTS returns WAV with extra chunks after the audio (a C2PA
    provenance manifest, "Created by Google Generative AI"). Slicing off a
    fixed 44-byte header kept those bytes and played them as a burst of static
    at the end of every clip.
    """
    pos = 12  # after "RIFF" <size> "WAVE"
    while pos + 8 <= len(data):
        cid = data[pos : pos + 4]
        size = int.from_bytes(data[pos + 4 : pos + 8], "little")
        body = pos + 8
        if cid == b"data":
            end = min(body + size, len(data))
            return data[body : end - ((end - body) % 2)]  # whole 16-bit samples
        pos = body + size + (size & 1)  # chunks are word-aligned
    return data[44:]  # malformed: fall back to the old behaviour


def _gemini_api_chunk(client, text: str, model: str, voice: str, prompt) -> bytes:
    """One Gemini API TTS call. Returns raw 16-bit PCM (24 kHz mono)."""
    from google.genai import errors as genai_errors
    from google.genai import types

    contents = f"{prompt.strip()}\n\n{text}" if prompt else text
    config = types.GenerateContentConfig(
        response_modalities=["AUDIO"],
        automatic_function_calling=types.AutomaticFunctionCallingConfig(disable=True),
        speech_config=types.SpeechConfig(
            voice_config=types.VoiceConfig(
                prebuilt_voice_config=types.PrebuiltVoiceConfig(voice_name=voice)
            )
        ),
    )
    delay = 1.0
    for attempt in range(6):
        try:
            resp = client.models.generate_content(
                model=model, contents=contents, config=config
            )
            data = resp.candidates[0].content.parts[0].inline_data.data
            if data[:4] == b"RIFF":  # some responses arrive as WAV
                data = _wav_pcm(data)
            return data
        except genai_errors.APIError as e:
            code = getattr(e, "code", 0) or 0
            if code in (429, 500, 503, 504) and attempt < 5:
                time.sleep(delay)
                delay = min(delay * 2, 20)
                continue
            snippet = text[:50] + "..." if len(text) > 50 else text
            if code in (400, 401, 403) and "key" in str(e).lower():
                raise RuntimeError(
                    f"Gemini API rejected key {mask_key(settings.gemini_api_key)} "
                    "(deleted, or not allowed for generativelanguage.googleapis.com)."
                ) from e
            raise RuntimeError(
                f"Speech synthesis failed for chunk '{snippet}': {e}"
            ) from e
    raise RuntimeError("Speech synthesis failed after retries.")


def _write_pcm(pcm: bytes, output_file: str, audio_format: str) -> None:
    """Write PCM as WAV, or encode to MP3/OGG with ffmpeg."""
    if audio_format == "WAV":
        with wave.open(output_file, "wb") as w:
            w.setnchannels(1)
            w.setsampwidth(2)
            w.setframerate(PCM_RATE)
            w.writeframes(pcm)
        return
    if not shutil.which("ffmpeg"):
        raise RuntimeError(
            f"ffmpeg is needed to write {audio_format} from Gemini 3.8 models. "
            "Install ffmpeg or use --audio-format WAV."
        )
    codec = (
        ["-c:a", "libmp3lame", "-q:a", "2"]
        if audio_format == "MP3"
        else ["-c:a", "libopus", "-b:a", "48k"]
    )
    subprocess.run(
        [
            "ffmpeg",
            "-loglevel",
            "error",
            "-y",
            "-f",
            "s16le",
            "-ar",
            str(PCM_RATE),
            "-ac",
            "1",
            "-i",
            "pipe:0",
            *codec,
            output_file,
        ],
        input=pcm,
        check=True,
    )


def _generate_gemini_api(text, output_file, voice, model, prompt, audio_format):
    from google import genai

    client = genai.Client(api_key=_gemini_api_key())
    chunks = split_text_into_chunks(text)
    total = len(chunks)
    with ThreadPoolExecutor(max_workers=4) as pool:
        parts = []
        for i, pcm in enumerate(
            pool.map(
                lambda c: _gemini_api_chunk(client, c, model, voice, prompt), chunks
            )
        ):
            if total > 1:
                print(f"Processing chunk {i + 1}/{total}...", file=sys.stderr, end="\r")
            parts.append(pcm)
    if total > 1:
        print(f"\nFinished processing {total} chunks.", file=sys.stderr)
    _write_pcm(b"".join(parts), output_file, audio_format)


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

    if is_gemini_api(model):
        voice = resolve_voice(voice_name, model, language_code)
        _generate_gemini_api(text, output_file, voice, model, prompt, audio_format)
        return

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
