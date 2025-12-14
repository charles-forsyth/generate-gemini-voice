# generate-gemini-voice

A modern CLI tool for generating voice using Google Cloud Text-to-Speech, built with a focus on reproducibility, secure configuration, and code quality.

## Installation

```bash
uv pip install -e .
```

## Usage

```bash
generate-voice "Hello, world!"
```

## Configuration

Create a `.env` file in the project root or in your home directory to set environment variables. For example:

```
GCLOUD_PROJECT=your-gcp-project-id
GOOGLE_APPLICATION_CREDENTIALS=/path/to/your/keyfile.json
```

## Development

For development, install `uv` and then run:

```bash
uv sync
```

## Testing

```bash
uv run pytest
```
