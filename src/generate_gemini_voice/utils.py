import contextlib
import datetime
import os
import re
import sys

# Import settings to ensure env var is set before pygame import
from generate_gemini_voice.config import settings

# Ensure the env var is set in os.environ for pygame to see it
if settings.pygame_hide_support_prompt:
    os.environ["PYGAME_HIDE_SUPPORT_PROMPT"] = settings.pygame_hide_support_prompt

import pygame


def create_filename(text: str, audio_format: str) -> str:
    """Creates a sanitized, unique filename from the input text and a timestamp."""
    sanitized_text = re.sub(r"[^\\w\\s-]", "", text).strip()
    sanitized_text = re.sub(r"[-\\s]+", "_", sanitized_text)
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    # Truncate to a reasonable length
    base_filename = f"{sanitized_text[:50]}_{timestamp}.{audio_format.lower()}"
    return base_filename

def play_audio(file_path: str):
    """Plays an audio file using pygame."""
    try:
        pygame.mixer.init()
        pygame.mixer.music.load(file_path)
        pygame.mixer.music.play()
        while pygame.mixer.music.get_busy():
            pygame.time.Clock().tick(10)
    except KeyboardInterrupt:
        pygame.mixer.music.stop()
        print("\nPlayback interrupted by user.", file=sys.stderr)
    except pygame.error as e:
        print(f"Error playing audio: {e}", file=sys.stderr)
    finally:
        # cleanup to release file handle
        with contextlib.suppress(Exception):
            pygame.mixer.quit()