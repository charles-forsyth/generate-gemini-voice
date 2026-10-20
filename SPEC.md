# generate-gemini-voice specification

Version 0.3.2 (2026-10-20; code 0.3.2). Owner: Chuck Forsyth.
Repository: `charles-forsyth/generate-gemini-voice` (local checkout `~/Projects/Gen-Voice-IVXX`). License: MIT.

## 1. Purpose and scope

`generate-gemini-voice` (executable `generate-voice`) is a standalone Python CLI for single-speaker speech synthesis across Google's two text-to-speech stacks:

1. **Gemini Developer API native audio (`gemini-3.8-flash-tts`, `gemini-3.8-flash-lite-tts`)** — directable via natural-language `--prompt` instructions, authenticated with a dedicated `GEMINI_API_KEY` restricted to `generativelanguage.googleapis.com`.
2. **Google Cloud Text-to-Speech API (`gemini-2.5-flash-tts`, `gemini-2.5-pro-tts`, `chirp3`)** — GA Cloud TTS models authenticated via Application Default Credentials (for `gemini-2.5-*`) or a Cloud TTS `GOOGLE_API_KEY` restricted to `texttospeech.googleapis.com` (for `chirp3`).

It handles arbitrary-length input by splitting text along sentence and UTF-8 byte boundaries, synthesizing chunks concurrently while preserving order, stripping trailing C2PA provenance manifests from raw Gemini WAV responses so they never play as static, and encoding to MP3, WAV, or OGG.

## 2. Design decisions

| # | Decision | Rationale |
|---|---|---|
| D1 | Isolated per-tool config (`~/.config/generate-gemini-voice/.env`, mode `0600`) | Prevents accidental cross-tool credential leakage from `./.env` or `~/.env`. Enforced at startup by `ensure_config_exists()`. |
| D2 | Three distinct auth paths matched to Google's backend rules | `gemini-3.8-*` runs on the Gemini Developer API (`GEMINI_API_KEY`); `gemini-2.5-*-tts` runs on Cloud TTS with ADC + `quota_project_id`; `chirp3` runs on Cloud TTS with `GOOGLE_API_KEY`. |
| D3 | Strip non-PCM RIFF chunks (`_wav_pcm`) on Gemini 3.8 responses | Gemini 3.8 TTS sometimes returns a RIFF/WAVE container with a trailing C2PA manifest (`Created by Google Generative AI`) after the `data` chunk. Slicing only the `data` chunk payload prevents a burst of full-scale static at the end of clips. |
| D4 | Infer `--audio-format` from `--output-file` extension when omitted | Passing `--output-file out.wav` without `--audio-format WAV` previously defaulted to `MP3`, causing `ffmpeg -c:a libmp3lame out.wav` to mux MP3 inside a RIFF WAVE container (`wFormatTag 0x0055`) that macOS CoreAudio (`afplay`) rejects. |
| D5 | Never echo full API keys in error messages | `mask_key()` redacts keys to `...<last4>` before raising `RuntimeError`. |
| D6 | Strict UTF-8 byte-budget chunking (`limit=3500` bytes) | Cloud TTS enforces byte limits (not character limits) per request. `split_text_into_chunks()` splits by sentence first, then word, then UTF-8 codepoint boundary so multibyte characters are never cleaved mid-sequence. |

## 3. Architecture

```text
generate-voice CLI (src/generate_gemini_voice/cli.py)
  |-- ensure_config_exists() & Settings (src/generate_gemini_voice/config.py)
  |     `-- ~/.config/generate-gemini-voice/.env (0600 enforced)
  |-- Input & format resolution (cli.py)
  |     |-- positional text | --input-file | stdin
  |     `-- _resolve_audio_format(--audio-format, --output-file) -> MP3 | WAV | OGG
  |-- Synthesis engine (src/generate_gemini_voice/core.py)
  |     |-- split_text_into_chunks() (src/generate_gemini_voice/utils.py, <=3500 UTF-8 bytes)
  |     |-- Path A: is_gemini_api(model) -> _generate_gemini_api()
  |     |     |-- google.genai.Client(api_key=GEMINI_API_KEY)
  |     |     |-- ThreadPoolExecutor(max_workers=4) -> _gemini_api_chunk()
  |     |     |-- _wav_pcm() strips RIFF header & trailing C2PA chunks -> 24 kHz mono s16le PCM
  |     |     `-- _write_pcm(): wave.open() for WAV, or ffmpeg (libmp3lame / libopus) for MP3/OGG
  |     `-- Path B: Cloud TTS -> get_text_to_speech_client()
  |           |-- ADC (gemini-2.5-*-tts) or ClientOptions(api_key=GOOGLE_API_KEY) (chirp3)
  |           |-- ThreadPoolExecutor(max_workers=4) -> _synthesize_single_chunk()
  |           `-- Stream concatenation (MP3/OGG raw concat; WAV 44-byte RIFF header size patching)
  `-- Playback (src/generate_gemini_voice/utils.py)
        `-- play_audio() via pygame.mixer (unless --no-play)
```

### Module map

| File | Responsibility |
|---|---|
| `src/generate_gemini_voice/cli.py` | Argument parser (`build_parser`), input reader (`read_input`), format resolver (`_resolve_audio_format`), voice listing/sampling, `--temp` lifecycle, exit handling. |
| `src/generate_gemini_voice/config.py` | `USER_CONFIG_FILE` (`~/.config/generate-gemini-voice/.env`), `ensure_config_exists()` (creates template and tightens permissions to `0600`), `Settings` (`pydantic-settings`), `mask_key()`. |
| `src/generate_gemini_voice/core.py` | Model/voice constants, `_wav_pcm()`, `_gemini_api_chunk()`, `_write_pcm()`, `_generate_gemini_api()`, `get_text_to_speech_client()`, `list_voices()`, `_synthesize_single_chunk()`, `generate_speech()`. |
| `src/generate_gemini_voice/utils.py` | `split_text_into_chunks()`, `create_filename()`, `play_audio()`. |

## 4. Models, voices, and audio formats

### Supported models (`MODEL_CHOICES`)

| Model ID | Backend | Auth required | `--prompt` style direction | Notes |
|---|---|---|---|---|
| `gemini-3.8-flash-tts` | Gemini Developer API | `GEMINI_API_KEY` | Supported | Default (`DEFAULT_MODEL`). Highest quality, 24 kHz 16-bit mono PCM. |
| `gemini-3.8-flash-lite-tts` | Gemini Developer API | `GEMINI_API_KEY` | Supported | Faster, lower-cost 3.8 model. |
| `gemini-2.5-flash-tts` | Cloud Text-to-Speech API | Google ADC + `GCLOUD_PROJECT` | Supported | GA Cloud TTS fallback. |
| `gemini-2.5-pro-tts` | Cloud Text-to-Speech API | Google ADC + `GCLOUD_PROJECT` | Supported | Higher-tier GA Cloud TTS fallback. |
| `chirp3` | Cloud Text-to-Speech API | `GOOGLE_API_KEY` | Ignored (prints note to stderr) | Resolves short voice names to `<lang>-Chirp3-HD-<Voice>`. |

### Voices (`VOICES`, 30 prebuilt voices)

`Achernar`, `Achird`, `Algenib`, `Algieba`, `Alnilam`, `Aoede`, `Autonoe`, `Callirrhoe`, `Charon`, `Despina`, `Enceladus`, `Erinome`, `Fenrir`, `Gacrux`, `Iapetus`, `Kore`, `Laomedeia`, `Leda`, `Orus`, `Pulcherrima`, `Puck`, `Rasalgethi`, `Sadachbia`, `Sadaltager`, `Schedar`, `Sulafat`, `Umbriel`, `Vindemiatrix`, `Zephyr` (default), `Zubenelgenubi`.

`resolve_voice(voice, model, language_code)` accepts either a short name (`Charon`) or a full Chirp 3 HD identifier (`en-US-Chirp3-HD-Charon`) and normalizes it for the active backend.

### Output formats

| Format | Gemini 3.8 path (`_write_pcm`) | Cloud TTS path (`generate_speech`) |
|---|---|---|
| `WAV` | Python `wave` module (`1 ch`, `2 bytes/sample`, `24000 Hz`, `pcm_s16le`). No external binary required. | `AudioEncoding.LINEAR16`; first chunk writes 44-byte RIFF header + frames, subsequent chunks strip their 44-byte headers, final file patches `ChunkSize` (offset 4) and `Subchunk2Size` (offset 40). |
| `MP3` | `ffmpeg -f s16le -ar 24000 -ac 1 -i pipe:0 -c:a libmp3lame -q:a 2 <out>` | `AudioEncoding.MP3`; chunks concatenated sequentially. |
| `OGG` | `ffmpeg -f s16le -ar 24000 -ac 1 -i pipe:0 -c:a libopus -b:a 48k <out>` | `AudioEncoding.OGG_OPUS`; chunks concatenated sequentially. |

## 5. Configuration and security

Configuration is loaded exclusively from `~/.config/generate-gemini-voice/.env` (plus process environment overrides):

| Variable | Field | Default | Purpose |
|---|---|---|---|
| `GEMINI_API_KEY` | `settings.gemini_api_key` | `""` | Gemini Developer API key for `gemini-3.8-*` models (restrict to `generativelanguage.googleapis.com`). |
| `GOOGLE_API_KEY` | `settings.google_api_key` | `""` | Cloud TTS API key for `chirp3` (restrict to `texttospeech.googleapis.com`). |
| `GCLOUD_PROJECT` | `settings.gcloud_project` | `"ucr-research-computing"` | Billing/quota project for Cloud TTS (`gemini-2.5-*-tts`). |
| `PYGAME_HIDE_SUPPORT_PROMPT` | environment | `"1"` | Suppresses pygame startup banner on import. |

Security invariants:
- `Settings._env_files()` returns `(USER_CONFIG_FILE,)` when the file exists and `()` otherwise, ignoring `./.env` and `~/.env`.
- `ensure_config_exists()` checks `os.lstat(USER_CONFIG_FILE).st_mode` on every invocation and resets mode to `0600` if group/other bits (`0077`) are set.
- `mask_key()` replaces all but the last 4 characters of any key with `...` in exception text.

## 6. CLI interface

```text
generate-voice [text]
               [--input-file FILE]
               [--output-file FILE]
               [--audio-format {MP3,WAV,OGG}]
               [--temp]
               [--no-play]
               [--model {gemini-3.8-flash-tts,gemini-3.8-flash-lite-tts,gemini-2.5-flash-tts,gemini-2.5-pro-tts,chirp3}]
               [--voice NAME | --voice-name NAME]
               [--prompt TEXT]
               [--language-code CODE]
               [--list-voices]
               [--sample-voices]
               [--project-id ID]
```

Mutual exclusions and validation rules:
- Providing both positional `text` and `--input-file` exits with code `2` (`use either a text argument or --input-file, not both`).
- Providing no `text`, no `--input-file`, and a TTY stdin exits with code `2` (`no input: give text, --input-file, or pipe text in`).
- Combining `--temp` and `--no-play` exits with code `2` (`--temp cannot be used with --no-play`).
- When `--output-file` is omitted and `--temp` is false, `create_filename(text, audio_format)` generates `<first_five_words_slug>_<YYYYMMDD_HHMMSS>.<ext>`.

## 7. Retry and error handling

- **Gemini Developer API (`_gemini_api_chunk`)**: Retries up to 6 attempts with exponential backoff (`1s, 2s, 4s, 8s, 16s, 20s`) on HTTP `429`, `500`, `503`, and `504`. Auth errors (`400/401/403` mentioning `key`) raise a `RuntimeError` with the masked key and API restriction hint.
- **Cloud TTS (`_RETRY`)**: Uses `google.api_core.retry.Retry` (`initial=1.0`, `maximum=20.0`, `multiplier=2.0`, `timeout=120.0`) on `TooManyRequests`, `ServiceUnavailable`, `InternalServerError`, and `DeadlineExceeded`.

## 8. Requirements traceability

| ID | Requirement | Verified by |
|---|---|---|
| REQ-AUTH-1 | Settings ignore `./.env` and `~/.env`, reading only `~/.config/generate-gemini-voice/.env` and env vars. | `tests/test_auth.py::test_settings_ignore_home_and_cwd_env` |
| REQ-AUTH-2 | Placeholder or missing API keys raise `RuntimeError` before network calls. | `tests/test_auth.py::test_client_init_with_placeholder_key`, `test_client_init_without_api_key` |
| REQ-AUTH-3 | Error messages never include the full API key string. | `tests/test_auth.py::test_error_messages_never_contain_full_key`, `tests/test_core.py::test_mask_key_never_reveals_key` |
| REQ-AUTH-4 | `chirp3` uses `GOOGLE_API_KEY`; `gemini-2.5-*` uses ADC with `quota_project_id`; `gemini-3.8-*` uses `GEMINI_API_KEY`. | `tests/test_core.py::test_chirp_client_uses_api_key`, `test_gemini_client_uses_adc_not_api_key`, `tests/test_gemini_api.py::test_missing_gemini_key_is_clear` |
| REQ-AUDIO-1 | Trailing C2PA/non-PCM chunks in Gemini 3.8 RIFF responses are stripped so only `data` chunk samples remain. | `tests/test_gemini_api.py::test_wav_trailing_chunks_are_not_audio`, `test_gemini_api_strips_wav_header` |
| REQ-AUDIO-2 | `--audio-format` is inferred from `--output-file` extension (`.wav`, `.ogg`, `.mp3`) when not explicitly passed. | `tests/test_cli.py::test_cli_infers_audio_format_from_output_file_extension` |
| REQ-CHUNK-1 | Long text splits cleanly on sentence, word, and UTF-8 multibyte boundaries within byte limits. | `tests/test_chunking.py::test_split_text_sentences`, `test_split_text_multibyte`, `test_split_text_strict_bytes` |
| REQ-CHUNK-2 | Multi-chunk WAV streaming patches the 44-byte RIFF header sizes accurately. | `tests/test_chunking.py::test_generate_speech_streaming_wav` |
| REQ-CLI-1 | `--temp` plays audio from a temporary file and unlinks it even on error. | `tests/test_cli.py::test_cli_generate_temp_cleans_up` |

## 9. Known gaps and backlog

- **K1 (Confirmed):** Gemini Developer API TTS silently truncates single chunks longer than ~600 words (~3 min of audio) without returning an HTTP error. `split_text_into_chunks()` defaults to `3500` bytes (~550 words), which stays near the ceiling; lowering the default chunk size for `gemini-3.8-*` models to ~2000 bytes (~300 words) would add margin.
- **K2 (Confirmed):** Playback relies on `pygame.mixer`, which requires SDL2 (`sdl2-compat`) wheels and currently pins `uv tool install` to Python 3.12 on macOS when Python 3.14 lacks prebuilt `pygame` wheels.
