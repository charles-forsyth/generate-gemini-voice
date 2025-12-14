import argparse
import sys
import os
import tempfile
from typing import Optional

from generate_gemini_voice.core import list_chirp_voices, generate_speech
from generate_gemini_voice.utils import create_filename, play_audio
from generate_gemini_voice.config import settings
from google.cloud import texttospeech

def list_voices_table(voice_list: list[texttospeech.Voice]):
    """Prints the available voices in a formatted table."""
    if not voice_list:
        print("No 'en-US' 'Chirp3' voices could be fetched.", file=sys.stderr)
        return

    max_name_len = max(len(v.name) for v in voice_list) if voice_list else 20

    print("Available 'en-US' 'Chirp3' Voices:")
    print(f"{ 'Name':<{max_name_len}}  {'Gender':<6}")
    print(f"{ '=' * max_name_len}  {'=' * 6}")

    for voice in voice_list:
        ssml_gender = texttospeech.SsmlVoiceGender(voice.ssml_gender).name
        print(f"{voice.name:<{max_name_len}}  {ssml_gender:<6}")

def main():
    """Parses command-line arguments and calls the voice generation function."""
    parser = argparse.ArgumentParser(
        description=(
            "Generate speech from text using Google Cloud Text-to-Speech. "
            "Accepts piped input."
        ),
        formatter_class=argparse.RawTextHelpFormatter
    )

    # --- Input Arguments ---
    input_group = parser.add_argument_group('Input Options (provide one)')
    input_group.add_argument(
        "text", nargs="?", type=str, default=None,
        help=(
            "The text to synthesize. Can be omitted if using --input-file "
            "or piping data."
        )
    )
    input_group.add_argument(
        "--input-file", type=str,
        help="Path to a text file to synthesize."
    )

    # --- Output Arguments ---
    output_group = parser.add_argument_group('Output Options')
    output_group.add_argument(
        "--output-file", type=str, default=None,
        help=(
            "The name of the output audio file. If not specified, a name "
            "is generated. Ignored if --temp is used."
        )
    )
    output_group.add_argument(
        "--audio-format", type=str, default="MP3",
        choices=["MP3", "WAV", "OGG"],
        help=(
            "The format of the output audio file. WAV is uncompressed, "
            "OGG uses the Ogg Opus codec."
        )
    )
    output_group.add_argument(
        "--temp", action="store_true",
        help="Use a temporary file for audio playback, which is deleted after playing."
    )
    output_group.add_argument(
        "--no-play", action="store_true",
        help="Do not play the generated audio."
    )

    # --- Voice Configuration ---
    voice_group = parser.add_argument_group('Voice Configuration')
    voice_group.add_argument(
        "--language-code", type=str, default="en-US",
        help="The language code for the voice."
    )
    voice_group.add_argument(
        "--voice-name", type=str, default="en-US-Chirp3-HD-Zephyr",
        help=(
            "The name of the voice to use. Use --list-voices to see "
            "available options."
        )
    )
    voice_group.add_argument(
        "--list-voices", action="store_true",
        help="List available 'en-US-Chirp3' voices and exit."
    )

    # --- Project Configuration ---
    project_group = parser.add_argument_group('Project Configuration')
    project_group.add_argument(
        "--project-id", type=str, default=settings.gcloud_project,
        help=(
            "Your Google Cloud project ID. Defaults to GCLOUD_PROJECT env var "
            "or 'ucr-research-computing'."
        )
    )

    args = parser.parse_args()

    # --- Logic ---
    try:
        if args.list_voices:
            try:
                valid_voices = list_chirp_voices()
                list_voices_table(valid_voices)
            except RuntimeError as e:
                print(f"Error: {e}", file=sys.stderr)
                sys.exit(1)
            return

        text_to_synthesize = ""
        # Check for input in order of precedence: --input-file, 
        # then text argument, then piped data.
        if args.input_file:
            if args.text:
                parser.error("argument --input-file: not allowed with a "
                             "text argument.")
            with open(args.input_file, 'r') as f:
                text_to_synthesize = f.read()
        elif args.text:
            text_to_synthesize = args.text
        elif not sys.stdin.isatty():
            print("Reading from pipe (stdin)...", file=sys.stderr)
            text_to_synthesize = sys.stdin.read().strip()

        if not text_to_synthesize:
            parser.error(
                "No input provided. Provide text as an argument, use "
                "--input-file, or pipe data to the script."
            )

        if args.temp and args.no_play:
            parser.error("--temp cannot be used with --no-play.")

        # Validate voice name if not listing voices
        try:
            all_chirp_voices = list_chirp_voices(args.language_code)
            valid_voice_names = [v.name for v in all_chirp_voices]
        except RuntimeError as e:
            print(f"Error: {e}", file=sys.stderr)
            sys.exit(1)

        if args.voice_name not in valid_voice_names:
            parser.error(
                f"Invalid voice name: '{args.voice_name}'.\nUse "
                f"--list-voices to see available options."
            )

        common_generate_args = {
            "text": text_to_synthesize,
            "language_code": args.language_code,
            "voice_name": args.voice_name,
            "audio_format": args.audio_format,
            "project_id": args.project_id,
        }

        if args.temp:
            if args.output_file:
                print("Warning: --output-file is ignored when --temp is used.",
                      file=sys.stderr)
            
            suffix = f".{args.audio_format.lower()}"
            with tempfile.NamedTemporaryFile(suffix=suffix, delete=True) \
                    as temp_audio_file:
                temp_filename = temp_audio_file.name
                try:
                    generate_speech(**common_generate_args, output_file=temp_filename)
                    print("Playing temporary audio file...", file=sys.stderr)
                    play_audio(temp_filename)
                    print("Temporary file will be deleted.", file=sys.stderr)
                except RuntimeError as e:
                    print(f"Error: {e}", file=sys.stderr)
                    sys.exit(1)
        else:
            output_filename = (
                args.output_file or 
                create_filename(text_to_synthesize, args.audio_format)
            )
            try:
                generate_speech(**common_generate_args, output_file=output_filename)
                if not args.no_play:
                    play_audio(output_filename)
            except RuntimeError as e:
                print(f"Error: {e}", file=sys.stderr)
                sys.exit(1)

    except KeyboardInterrupt:
        print("\nOperation cancelled by user. Exiting.", file=sys.stderr)
        sys.exit(0)