# Generate Gemini Voice

A modern, professional CLI tool for generating high-quality speech from text using Google Cloud's advanced "Chirp" models. Built with a focus on reproducibility, security, and developer experience.

## Features

- **Google Cloud Chirp Models:** Access the latest high-definition, realistic voice models.
- **Secure Configuration:** Safely manages credentials and project IDs via `.env` files and environment variables.
- **Modern Python:** Built with `pydantic`, `uv`, and adhering to strict type-checking and linting standards.
- **Flexible Input:** Accepts text input via command-line arguments, files (`--input-file`), or standard input (piping).
- **Multiple Formats:** Supports MP3, WAV (uncompressed), and OGG (Opus) output formats.
- **Instant Playback:** Optional `--temp` mode for generating and playing audio without cluttering your filesystem.

## Installation

### Prerequisites

- **Python 3.9+**
- **uv** (Recommended for fast, reliable package management)
- **Google Cloud Account** with Text-to-Speech API enabled.

### Installing with `uv` (Recommended)

To install globally as a tool:

```bash
uv tool install git+https://github.com/charles-forsyth/generate-gemini-voice.git
```

To upgrade later:

```bash
uv tool upgrade generate-gemini-voice
```

### Installing from Source

```bash
git clone https://github.com/charles-forsyth/generate-gemini-voice.git
cd generate-gemini-voice
uv pip install -e .
```

## Configuration

The tool requires authentication and a Google Cloud Project ID. You can configure these using environment variables or a `.env` file in your home directory (`~/.env`) or the project root.

**Example `.env` file:**

```env
# Required
GCLOUD_PROJECT=your-google-cloud-project-id
GOOGLE_APPLICATION_CREDENTIALS=/path/to/your/service-account-key.json

# Optional
PYGAME_HIDE_SUPPORT_PROMPT=1
```

*Note: If you have the Google Cloud SDK installed, you can often skip `GOOGLE_APPLICATION_CREDENTIALS` by running `gcloud auth application-default login`.*

## Usage

The command `generate-voice` is your entry point.

### Basic Usage

Generate and play a simple sentence:

```bash
generate-voice "Hello, world! This is a test." --temp
```

### Advanced Examples

**1. Save to a specific file (MP3):**

```bash
generate-voice "This is a permanent recording." --output-file recording.mp3
```

**2. Use a specific voice model:**

First, list available voices:
```bash
generate-voice --list-voices
```

Then use one:
```bash
generate-voice "I have a specific voice." --voice-name en-US-Chirp3-HD-Zephyr
```

**3. Sample all voices:**

To hear a quick introduction from every available "Chirp" voice:
```bash
generate-voice --sample-voices
```

**4. Read from a text file:**

```bash
generate-voice --input-file script.txt --output-file output.wav --audio-format WAV
```

**4. Pipe text from another command:**

```bash
echo "Piped input is supported." | generate-voice --temp
```

**5. Convert a web page summary (example workflow):**

```bash
# Assuming you have a tool to extract text
extract-text https://example.com | generate-voice --temp
```

## Command Line Options

| Option | Description |
| :--- | :--- |
| `text` | The text to synthesize (positional argument). |
| `--input-file` | Path to a text file to read input from. |
| `--output-file` | Path to save the generated audio file. |
| `--audio-format` | Output format: `MP3` (default), `WAV`, `OGG`. |
| `--temp` | Generate to a temporary file, play it, then delete it. |
| `--no-play` | Generate the file but do not auto-play it. |
| `--voice-name` | Specific voice to use (default: `en-US-Chirp3-HD-Zephyr`). |
| `--list-voices` | Display a table of available Chirp voices. |
| `--sample-voices` | Iterate through and play a short sample of each available voice. |
| `--language-code` | Language code (default: `en-US`). |
| `--project-id` | Google Cloud Project ID (overrides env var). |

## Development

This project uses `uv` for dependency management and `ruff` for linting.

1.  **Sync dependencies:** `uv sync`
2.  **Run tests:** `uv run pytest`
3.  **Lint code:** `uv run ruff check src`