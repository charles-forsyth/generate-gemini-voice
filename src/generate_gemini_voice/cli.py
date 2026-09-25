import argparse
import os
import sys
import tempfile
import warnings

# google-auth warns on every run that grpcio < 1.83 lacks post-quantum TLS.
# grpcio 1.83 needs Python > 3.9 (our floor); enforcement starts April 2027.
warnings.filterwarnings("ignore", message=".*Post-Quantum.*", category=FutureWarning)

from generate_gemini_voice.config import ensure_config_exists, settings  # noqa: E402
from generate_gemini_voice.core import (  # noqa: E402
    CHIRP_MODEL,
    DEFAULT_MODEL,
    DEFAULT_VOICE,
    MODEL_CHOICES,
    generate_speech,
    list_voices,
)
from generate_gemini_voice.utils import create_filename, play_audio  # noqa: E402

EPILOG = """
MODELS:
  gemini-3.8-flash-tts       Default. Newest (Sep 2026), best quality, --prompt direction.
  gemini-3.8-flash-lite-tts  Cheaper and faster 3.8 model.
  gemini-2.5-flash-tts       GA on Cloud TTS (fallback).
  gemini-2.5-pro-tts         GA on Cloud TTS, higher quality (fallback).
  chirp3                     Classic Chirp 3 HD voices.

  3.8 models need GEMINI_API_KEY (restricted to generativelanguage.googleapis.com).
  2.5 models need: gcloud auth application-default login
  chirp3 needs GOOGLE_API_KEY (restricted to texttospeech.googleapis.com).
  Keys live in ~/.config/generate-gemini-voice/.env

EXAMPLES:
  generate-voice "Hello, world." --temp
  generate-voice --input-file notes.txt --temp --prompt "Read like a calm briefing."
  generate-voice "Big news!" --voice Puck --prompt "Say this excitedly."
  generate-voice "Save this." --output-file out.mp3
  generate-voice "Classic voice." --model chirp3 --temp
  echo "System update complete." | generate-voice --temp
  generate-voice --list-voices
  generate-voice --sample-voices
"""


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        description="Generate speech with Google Cloud Text-to-Speech (Gemini-TTS or Chirp 3 HD).",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=EPILOG,
    )
    i = p.add_argument_group("Input (provide one)")
    i.add_argument(
        "text",
        nargs="?",
        default=None,
        help="Text to speak. Or use --input-file or pipe stdin.",
    )
    i.add_argument("--input-file", metavar="FILE", help="Read text from a file.")

    o = p.add_argument_group("Output")
    o.add_argument(
        "--output-file",
        metavar="FILE",
        help="Save to this file (default: name from text + timestamp).",
    )
    o.add_argument(
        "--audio-format", default="MP3", choices=["MP3", "WAV", "OGG"], type=str.upper
    )
    o.add_argument(
        "--temp",
        action="store_true",
        help="Play from a temporary file, then delete it.",
    )
    o.add_argument(
        "--no-play", action="store_true", help="Do not play after generating."
    )

    v = p.add_argument_group("Voice")
    v.add_argument(
        "--model",
        default=DEFAULT_MODEL,
        choices=MODEL_CHOICES,
        help=f"Default: {DEFAULT_MODEL}",
    )
    v.add_argument(
        "--voice",
        "--voice-name",
        dest="voice",
        default=DEFAULT_VOICE,
        metavar="NAME",
        help=f"Voice name, e.g. Zephyr, Kore, Charon, Puck (default: {DEFAULT_VOICE}).",
    )
    v.add_argument(
        "--prompt",
        metavar="TEXT",
        help="Style direction for Gemini models, e.g. 'Read slowly and warmly.' Ignored for chirp3.",
    )
    v.add_argument("--language-code", default="en-US", metavar="CODE")
    v.add_argument(
        "--list-voices",
        action="store_true",
        help="List voices for the chosen model and exit.",
    )
    v.add_argument(
        "--sample-voices",
        action="store_true",
        help="Play a short sample of each voice.",
    )

    g = p.add_argument_group("Project")
    g.add_argument(
        "--project-id",
        default=settings.gcloud_project,
        metavar="ID",
        help="Project billed for Gemini-TTS (default: GCLOUD_PROJECT or ucr-research-computing).",
    )
    return p


def read_input(args, parser) -> str:
    if args.input_file:
        if args.text:
            parser.error("use either a text argument or --input-file, not both.")
        with open(args.input_file, encoding="utf-8") as f:
            return f.read().strip()
    if args.text:
        return args.text
    if not sys.stdin.isatty():
        return sys.stdin.read().strip()
    return ""


def _temp_path(audio_format: str) -> str:
    fd, path = tempfile.mkstemp(suffix=f".{audio_format.lower()}", prefix="genvoice_")
    os.close(fd)
    return path


def main() -> None:
    ensure_config_exists()
    parser = build_parser()
    args = parser.parse_args()

    if args.prompt and args.model == CHIRP_MODEL:
        print("Note: --prompt is ignored for chirp3.", file=sys.stderr)

    try:
        if args.list_voices:
            for name in list_voices(args.model, args.language_code):
                print(name)
            return

        if args.sample_voices:
            voices = list_voices(args.model, args.language_code)
            print(
                f"Sampling {len(voices)} voices ({args.model}). Ctrl+C to stop.",
                file=sys.stderr,
            )
            for name in voices:
                short = name.split("-")[-1]
                print(f"  {short}", file=sys.stderr)
                path = _temp_path(args.audio_format)
                try:
                    generate_speech(
                        text=f"Hello, I am {short}.",
                        output_file=path,
                        voice_name=name,
                        language_code=args.language_code,
                        audio_format=args.audio_format,
                        project_id=args.project_id,
                        model=args.model,
                        prompt=args.prompt,
                    )
                    if not args.no_play:
                        play_audio(path)
                except RuntimeError as e:
                    print(f"    skipped: {e}", file=sys.stderr)
                finally:
                    os.unlink(path)
            return

        text = read_input(args, parser)
        if not text:
            parser.error("no input: give text, --input-file, or pipe text in.")
        if args.temp and args.no_play:
            parser.error("--temp cannot be used with --no-play.")

        common = dict(
            text=text,
            voice_name=args.voice,
            language_code=args.language_code,
            audio_format=args.audio_format,
            project_id=args.project_id,
            model=args.model,
            prompt=args.prompt,
        )

        if args.temp:
            if args.output_file:
                print("Warning: --output-file is ignored with --temp.", file=sys.stderr)
            path = _temp_path(args.audio_format)
            try:
                generate_speech(**common, output_file=path)
                play_audio(path)
            finally:
                os.unlink(path)
        else:
            out = args.output_file or create_filename(text, args.audio_format)
            generate_speech(**common, output_file=out)
            print(f"Saved: {out}", file=sys.stderr)
            if not args.no_play:
                play_audio(out)

    except RuntimeError as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)
    except KeyboardInterrupt:
        print("\nCancelled.", file=sys.stderr)
        sys.exit(130)


if __name__ == "__main__":
    main()
