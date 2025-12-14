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
    epilog_examples = """
EXAMPLES:

  1. Generate and play a simple sentence (Preview mode):
     generate-voice "Hello, world! This is a test." --temp

  2. Save speech to a specific MP3 file:
     generate-voice "This is a permanent recording." --output-file recording.mp3

  3. Use a specific high-definition voice model:
     # First, list available voices:
     generate-voice --list-voices
     # Then use a specific name:
     generate-voice "I have a specific voice." --voice-name en-US-Chirp3-HD-Zephyr

  4. Read text from a file and save as WAV:
     generate-voice --input-file script.txt --output-file output.wav --audio-format WAV

  5. Pipe text from another command:
     echo "System update complete." | generate-voice --temp

  6. Sample all available voices to find your favorite:
     generate-voice --sample-voices

CONFIGURATION:
  Ensure you have Google Cloud credentials set up:
  $ gcloud auth application-default login
  
  Or set the environment variable:
  $ export GOOGLE_APPLICATION_CREDENTIALS="/path/to/key.json"

For more details, visit: https://github.com/charles-forsyth/generate-gemini-voice
"""
    parser = argparse.ArgumentParser(
        description=(
            "Generate high-quality speech from text using Google Cloud's "
            "latest 'Chirp' models."
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=epilog_examples
    )

    # --- Input Arguments ---
    input_group = parser.add_argument_group('Input Options (provide one)')
    input_group.add_argument(
        "text", nargs="?", type=str, default=None,
        help=(
            "The text to synthesize. Optional if using --input-file or piping "
            "text via stdin."
        )
    )
    input_group.add_argument(
        "--input-file", type=str, metavar="FILE",
        help="Read the text to synthesize from a specific file path."
    )

    # --- Output Arguments ---
    output_group = parser.add_argument_group('Output Options')
    output_group.add_argument(
        "--output-file", type=str, metavar="FILE", default=None,
        help=(
            "Save the generated audio to this file. If omitted, a filename "
            "is automatically generated based on the text and timestamp. "
            "Ignored if --temp is used."
        )
    )
    output_group.add_argument(
        "--audio-format", type=str, default="MP3",
        choices=["MP3", "WAV", "OGG"],
        help=(
            "The audio file format. 'MP3' (default) is widely compatible. "
            "'WAV' is uncompressed linear PCM. 'OGG' uses the Opus codec."
        )
    )
    output_group.add_argument(
        "--temp", action="store_true",
        help=(
            "Generate the audio to a temporary file, play it immediately, "
            "and then delete it. Useful for quick previews."
        )
    )
    output_group.add_argument(
        "--no-play", action="store_true",
        help=(
            "Disable automatic playback of the generated audio file. "
            "Default behavior is to play after generation."
        )
    )

    # --- Voice Configuration ---
    voice_group = parser.add_argument_group('Voice Configuration')
    voice_group.add_argument(
        "--language-code", type=str, default="en-US", metavar="CODE",
        help="The BCP-47 language code for the voice (default: 'en-US')."
    )
    voice_group.add_argument(
        "--voice-name", type=str, default="en-US-Chirp3-HD-Zephyr", metavar="NAME",
        help=(
            "The specific Google Cloud Voice name to use. "
            "Default: 'en-US-Chirp3-HD-Zephyr'. "
            "Use --list-voices to see all available options."
        )
    )
    voice_group.add_argument(
        "--list-voices", action="store_true",
        help="List all available 'en-US' 'Chirp3' voices in a table and exit."
    )
    voice_group.add_argument(
        "--sample-voices", action="store_true",
        help=(
            "Iterate through all available 'Chirp3' voices, playing a short "
            "sample of each (e.g., 'Hello, I am [Voice Name]')."
        )
    )

    # --- Project Configuration ---
    project_group = parser.add_argument_group('Project Configuration')
    project_group.add_argument(
        "--project-id", type=str, default=settings.gcloud_project, metavar="ID",
        help=(
            "The Google Cloud Project ID to bill for usage. "
            "Defaults to the 'GCLOUD_PROJECT' environment variable "
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

        if args.sample_voices:
            try:
                valid_voices = list_chirp_voices(args.language_code)
                if not valid_voices:
                    print(f"No voices found for language '{args.language_code}'.", file=sys.stderr)
                    sys.exit(1)
                
                print(f"Found {len(valid_voices)} voices. Starting sampling...", file=sys.stderr)
                print("Press Ctrl+C to stop.", file=sys.stderr)

                for voice in valid_voices:
                    print(f"\nSampling voice: {voice.name}", file=sys.stderr)
                    sample_text = f"Hello, I am {voice.name}."
                    
                    suffix = f".{args.audio_format.lower()}"
                    with tempfile.NamedTemporaryFile(suffix=suffix, delete=True) as temp_audio_file:
                        temp_filename = temp_audio_file.name
                        try:
                            generate_speech(
                                text=sample_text,
                                output_file=temp_filename,
                                voice_name=voice.name,
                                language_code=args.language_code,
                                audio_format=args.audio_format,
                                project_id=args.project_id
                            )
                            if not args.no_play:
                                play_audio(temp_filename)
                        except RuntimeError as e:
                            print(f"Error sampling {voice.name}: {e}", file=sys.stderr)
                            # Continue to next voice instead of exiting
                            continue
                
                print("\nSampling complete.", file=sys.stderr)
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
                "No input provided. Please provide text as an argument, use "
                "--input-file, or pipe text to the script."
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