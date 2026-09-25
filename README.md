# Generate Gemini Voice

A CLI for generating speech from text with Google's TTS models. It defaults to
**Gemini 3.8 Flash TTS** (released Sep 2026, directable with a plain-language
`--prompt`), with Gemini 2.5 TTS and classic **Chirp 3 HD** voices as fallbacks.

## Features

- **Gemini 3.8 TTS by default** (`gemini-3.8-flash-tts`), plus
  `gemini-3.8-flash-lite-tts`, and the GA Cloud TTS models `gemini-2.5-flash-tts`
  and `gemini-2.5-pro-tts`. Steer delivery with `--prompt`,
  e.g. `--prompt "Read like a calm morning briefing."`
- **Chirp 3 HD** voices via `--model chirp3`.
- **Flexible input:** text argument, `--input-file`, or stdin.
- **MP3, WAV, OGG** output. Long text is chunked, synthesized in parallel, and
  streamed to disk in order.
- **`--temp`** plays from a temporary file and deletes it afterward.
- **Automatic retry** with backoff on rate limits and transient errors.

## Installation

```bash
uv tool install git+https://github.com/charles-forsyth/generate-gemini-voice.git
# upgrade later
uv tool upgrade generate-gemini-voice
```

Requires Python 3.9+ and a Google Cloud project with the Text-to-Speech API
enabled.

## Authentication

The two model families authenticate differently:

| Model | Auth | Setup |
| :--- | :--- | :--- |
| `gemini-3.8-*` (default) | Gemini API key | `GEMINI_API_KEY`, restricted to `generativelanguage.googleapis.com` |
| `gemini-2.5-*-tts` | Google application-default credentials | `gcloud auth application-default login` |
| `chirp3` | Cloud TTS API key | `GOOGLE_API_KEY`, restricted to `texttospeech.googleapis.com` |

Gemini 3.8 TTS is only on the Gemini API today (not yet on Cloud TTS/Vertex).
Output from it is converted to MP3/OGG with `ffmpeg`; WAV needs nothing extra.
Gemini 2.5 TTS runs through Cloud TTS, which bills `GCLOUD_PROJECT`.

### Config file

The tool reads **only** `~/.config/generate-gemini-voice/.env`. It deliberately
ignores `./.env` and `~/.env`, which often hold unrelated keys for other tools.
The file is created on first run with owner-only (600) permissions, and
permissions are tightened automatically if they are ever looser.

```env
GEMINI_API_KEY=your-gemini-key     # default 3.8 models
GOOGLE_API_KEY=your-tts-key        # only needed for --model chirp3
GCLOUD_PROJECT=your-project-id
PYGAME_HIDE_SUPPORT_PROMPT=1
```

A real environment variable still overrides the file for a single run.

**Key hygiene:** use one key per purpose, each restricted to its single API.
Error messages show only the last 4 characters of a key.

## Usage

```bash
# Quick preview, played and deleted
generate-voice "Hello, world." --temp

# Direct the delivery (Gemini models)
generate-voice --input-file notes.txt --temp --prompt "Read slowly and warmly."

# Pick a voice and save
generate-voice "Big news today!" --voice Puck --output-file news.mp3

# Highest quality model
generate-voice "Cheaper read." --model gemini-3.8-flash-lite-tts --temp

# Classic Chirp 3 HD with an API key
generate-voice "Classic voice." --model chirp3 --temp

# Pipe text in
echo "System update complete." | generate-voice --temp

# Voices
generate-voice --list-voices
generate-voice --sample-voices
```

Voices (shared by both families): Achernar, Achird, Algenib, Algieba, Alnilam,
Aoede, Autonoe, Callirrhoe, Charon, Despina, Enceladus, Erinome, Fenrir, Gacrux,
Iapetus, Kore, Laomedeia, Leda, Orus, Pulcherrima, Puck, Rasalgethi, Sadachbia,
Sadaltager, Schedar, Sulafat, Umbriel, Vindemiatrix, Zephyr, Zubenelgenubi.
Full Chirp names such as `en-US-Chirp3-HD-Zephyr` also work.

## Options

| Option | Description |
| :--- | :--- |
| `text` | Text to speak (positional). |
| `--input-file FILE` | Read text from a file. |
| `--output-file FILE` | Save audio here (default: name from text + timestamp). |
| `--audio-format` | `MP3` (default), `WAV`, `OGG`. |
| `--temp` | Play from a temp file, then delete it. |
| `--no-play` | Save without playing. |
| `--model` | `gemini-3.8-flash-tts` (default), `gemini-3.8-flash-lite-tts`, `gemini-2.5-flash-tts`, `gemini-2.5-pro-tts`, `chirp3`. |
| `--voice NAME` | Voice name (default `Zephyr`). `--voice-name` still works. |
| `--prompt TEXT` | Style direction for Gemini models. Ignored for `chirp3`. |
| `--language-code` | Default `en-US`. |
| `--list-voices` | List voices for the chosen model. |
| `--sample-voices` | Play a short sample of each voice. |
| `--project-id` | Project to bill for Gemini-TTS. |

## Development

```bash
uv sync
uv run pytest
uv run ruff check src
```
