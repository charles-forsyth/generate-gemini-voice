# Generate Gemini Voice

## Project Overview
`generate-gemini-voice` is a modern, professional CLI tool designed to generate high-quality speech from text using Google Cloud's advanced "Chirp" models. It is built with a focus on reproducibility, security, and developer experience.

**Key Features:**
*   **High-Quality Audio:** leverages Google Cloud's "Chirp" models for realistic voice generation.
*   **Secure Configuration:** Uses `.env` files and environment variables for managing credentials.
*   **Flexible Input/Output:** Supports text input via CLI args, files, or piping; outputs to MP3, WAV, or OGG.
*   **Instant Playback:** Includes a `--temp` mode for generating and playing audio immediately without file clutter.

## Building and Running

This project uses `uv` for dependency management and workflow automation.

### Installation
To install the tool globally (recommended for usage):
```bash
uv tool install .
```

To install dependencies for development:
```bash
uv sync
```

### Running the CLI
If installed globally:
```bash
generate-voice "Hello world" --temp
```

For development (without installing):
```bash
uv run generate-voice "Hello from dev" --temp
```

### Testing
Run the test suite with coverage:
```bash
uv run pytest
```

### Linting
Check code quality with `ruff`:
```bash
uv run ruff check src
```

## Development Conventions

*   **Configuration:** The application strictly requires a `GOOGLE_API_KEY` set in a `.env` file or environment variable.
    *   *Note:* The `src/generate_gemini_voice/core.py` file currently contains logic that enforces a specific `EXPECTED_API_KEY` for debugging purposes. This may need to be modified for broader usage.
*   **Architecture:**
    *   `src/generate_gemini_voice/cli.py`: Handles command-line argument parsing and user interaction flows (listing voices, sampling, generating).
    *   `src/generate_gemini_voice/core.py`: Contains the core logic for interacting with the Google Cloud Text-to-Speech API.
    *   `src/generate_gemini_voice/config.py`: Manages configuration loading using `pydantic-settings`.
*   **Typing:** The codebase utilizes Python type hints throughout.
*   **Package Management:** `pyproject.toml` is the source of truth for dependencies and build configuration.
