import contextlib
import datetime
import os
import re
import sys
import struct

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

def split_text_into_chunks(text: str, limit: int = 4000) -> list[str]:
    """
    Splits text into chunks strictly less than `limit` bytes (UTF-8 encoded), 
    attempting to break on sentence boundaries.
    """
    if len(text.encode('utf-8')) < limit:
        return [text]

    chunks = []
    current_chunk = ""
    
    # Split by sentence endings (. ! ? or newlines) keeping the delimiter
    sentences = re.split(r'(?<=[.!?\n])\s+', text)

    for sentence in sentences:
        # Check size in bytes
        current_bytes = len(current_chunk.encode('utf-8'))
        sentence_bytes = len(sentence.encode('utf-8'))
        # Separator (space) is 1 byte
        sep_bytes = 1 if current_chunk else 0

        if current_bytes + sentence_bytes + sep_bytes > limit:
            if current_chunk:
                chunks.append(current_chunk.strip())
                current_chunk = ""
            
            # If a single sentence is huge
            if len(sentence.encode('utf-8')) > limit:
                while len(sentence.encode('utf-8')) > limit:
                    # We need to find a split point that fits in 'limit' bytes
                    # Simple approach: binary search or just conservative char slicing?
                    # Conservative slicing: limit / 4 chars is safe lower bound, limit chars is upper.
                    
                    # Let's try to split by space first within the byte limit
                    # Construct a candidate string that fits
                    candidate = sentence
                    while len(candidate.encode('utf-8')) > limit:
                        # trim chars roughly
                        char_len = len(candidate)
                        # approximation
                        excess_ratio = limit / len(candidate.encode('utf-8'))
                        new_char_len = int(char_len * excess_ratio)
                        if new_char_len >= char_len:
                            new_char_len = char_len - 1
                        candidate = candidate[:new_char_len]
                    
                    # Now 'candidate' fits in bytes.
                    # Try to find a space in this candidate to break cleanly
                    split_idx = candidate.rfind(' ')
                    if split_idx == -1:
                        # No space, just hard chop at candidate length
                        # Ensure we don't cut in middle of multibyte char? 
                        # Python slicing handles chars, so candidate is valid string.
                        chunks.append(candidate.strip())
                        sentence = sentence[len(candidate):].strip()
                    else:
                        chunks.append(sentence[:split_idx].strip())
                        sentence = sentence[split_idx:].strip()
                current_chunk = sentence
            else:
                current_chunk = sentence
        else:
            if current_chunk:
                current_chunk += " " + sentence
            else:
                current_chunk = sentence
    
    if current_chunk:
        chunks.append(current_chunk.strip())
        
    return chunks

def combine_audio_data(audio_chunks: list[bytes], audio_format: str) -> bytes:
    """
    Combines multiple binary audio chunks into a single valid audio file.
    Handles WAV header patching; MP3/OGG are concatenated.
    """
    if not audio_chunks:
        return b""
    if len(audio_chunks) == 1:
        return audio_chunks[0]

    if audio_format.upper() == "WAV":
        # WAV (Linear16) logic
        # Header is 44 bytes.
        # We take the header from the first chunk.
        # We concatenate the data bodies (everything after byte 44) from all chunks.
        # We update the size fields in the header.
        
        first_chunk = audio_chunks[0]
        if len(first_chunk) < 44:
            # Should not happen with valid WAV
            return b"".join(audio_chunks)

        header = bytearray(first_chunk[:44])
        data_body = first_chunk[44:]
        
        for chunk in audio_chunks[1:]:
            if len(chunk) >= 44:
                data_body += chunk[44:]
            else:
                data_body += chunk
        
        total_data_len = len(data_body)
        total_file_len = 36 + total_data_len
        
        # Update ChunkSize (offset 4, 4 bytes, little endian)
        header[4:8] = struct.pack('<I', total_file_len)
        
        # Update Subchunk2Size (offset 40, 4 bytes, little endian)
        header[40:44] = struct.pack('<I', total_data_len)
        
        return bytes(header) + data_body

    else:
        # MP3 or OGG - Simple concatenation
        # Note: Concatenating OGG/Vorbis streams works (chained streams).
        # Concatenating MP3 frames usually works for players.
        return b"".join(audio_chunks)