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

def split_text_into_chunks(text: str, limit: int = 4000) -> list[str]:
    """
    Splits text into chunks strictly less than `limit` bytes (UTF-8 encoded), 
    attempting to break on sentence boundaries, then words, then characters.
    """
    if not text:
        return []
        
    encoded_text = text.encode('utf-8')
    if len(encoded_text) <= limit:
        return [text]

    chunks = []
    current_chunk = ""
    current_chunk_bytes = 0
    
    # 1. Primary Split: Sentence boundaries (. ! ? or newlines)
    # We use a regex that keeps the delimiter with the sentence
    sentences = re.split(r'(?<=[.!?\n])\s+', text)

    for sentence in sentences:
        sentence_bytes = len(sentence.encode('utf-8'))
        
        # Calculate separator size (space) if we append to current chunk
        sep_len = 1 if current_chunk else 0
        
        if current_chunk_bytes + sep_len + sentence_bytes <= limit:
            # Fits in current chunk
            if current_chunk:
                current_chunk += " " + sentence
                current_chunk_bytes += 1 + sentence_bytes
            else:
                current_chunk = sentence
                current_chunk_bytes = sentence_bytes
        else:
            # Doesn't fit. 
            # First, save what we have if it's not empty
            if current_chunk:
                chunks.append(current_chunk.strip())
                current_chunk = ""
                current_chunk_bytes = 0
            
            # Now handle the current sentence.
            # It might be small enough to be the start of a new chunk,
            # or it might be huge (larger than limit) and need further splitting.
            
            if sentence_bytes <= limit:
                current_chunk = sentence
                current_chunk_bytes = sentence_bytes
            else:
                # The sentence itself is too big. We must split it.
                # We need to slice 'sentence' such that the slice encoded is <= limit.
                remaining_sentence = sentence
                
                while remaining_sentence:
                    # If remaining fits, done
                    if len(remaining_sentence.encode('utf-8')) <= limit:
                        current_chunk = remaining_sentence
                        current_chunk_bytes = len(remaining_sentence.encode('utf-8'))
                        break
                        
                    # Find a safe split point.
                    # We can't use simple slicing because Python slices chars, not bytes.
                    # We need to find char index k such that remaining_sentence[:k] is just under limit.
                    
                    # Estimate char length. 
                    # 1 char >= 1 byte. So limit chars is the absolute max (if ASCII).
                    # If all 4-byte chars, limit/4 is min.
                    
                    # Start with a safe upper bound estimate based on ratio
                    rem_bytes = len(remaining_sentence.encode('utf-8'))
                    rem_chars = len(remaining_sentence)
                    avg_bytes_per_char = rem_bytes / rem_chars
                    
                    target_chars = int(limit / avg_bytes_per_char)
                    
                    # Refine target_chars to be strictly <= limit bytes
                    # Try to grow if safe, shrink if not
                    
                    # Heuristic: Start slightly optimistic, then shrink
                    candidate_str = remaining_sentence[:target_chars + 100] # +padding for variation
                    while len(candidate_str.encode('utf-8')) > limit:
                        # Too big, slice off end. 
                        # How much? proportional diff
                        curr_b = len(candidate_str.encode('utf-8'))
                        diff = curr_b - limit
                        # Approximate chars to drop (assume 1 byte/char to be conservative in dropping?)
                        # No, assume max density to drop faster?
                        drop_chars = max(1, int(diff / 4)) # assume big chars to drop fewer? No.
                        # safer: drop 1 char at least.
                        candidate_str = candidate_str[:-1] 
                    
                    # Now candidate_str fits. But is it a clean split?
                    # Try to find a space or punctuation near the end.
                    # Look back up to 20% of the chunk size
                    best_split_idx = -1
                    lookback_limit = int(len(candidate_str) * 0.2)
                    
                    # Try weaker punctuation first: , ; :
                    match = re.search(r'[;,:]\s', candidate_str[-lookback_limit:])
                    if match:
                        # Found punctuation. Split *after* it (and space).
                        # match.end() is relative to the slice start
                        # real index in candidate_str is len(candidate_str) - lookback_limit + match.end()
                        best_split_idx = len(candidate_str) - lookback_limit + match.end()
                    else:
                        # Try space
                        space_idx = candidate_str.rfind(' ')
                        if space_idx != -1 and (len(candidate_str) - space_idx) < lookback_limit:
                            best_split_idx = space_idx
                    
                    if best_split_idx != -1:
                        # Clean split found
                        final_chunk = candidate_str[:best_split_idx].strip()
                        # Adjust remaining
                        # We cut at best_split_idx.
                        # But wait, candidate_str is a prefix of remaining_sentence.
                        # So we advance remaining_sentence by best_split_idx
                        remaining_sentence = remaining_sentence[best_split_idx:].strip()
                    else:
                        # Hard split
                        final_chunk = candidate_str
                        remaining_sentence = remaining_sentence[len(final_chunk):].strip()
                        
                    chunks.append(final_chunk)

    # Append any leftovers
    if current_chunk:
        chunks.append(current_chunk.strip())
        
    return chunks