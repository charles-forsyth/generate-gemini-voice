import pytest
import struct
from generate_gemini_voice.utils import split_text_into_chunks, combine_audio_data

def test_split_text_small():
    text = "Short text."
    chunks = split_text_into_chunks(text, limit=100)
    assert len(chunks) == 1
    assert chunks[0] == "Short text."

def test_split_text_sentences():
    # Sentences are roughly 10-15 chars. Limit 30.
    # "Sentence one. " (14) + "Sentence two. " (14) = 28. Fits.
    # "Sentence three." (15). Next chunk.
    text = "Sentence one. Sentence two. Sentence three."
    chunks = split_text_into_chunks(text, limit=30)
    
    assert len(chunks) == 2
    assert chunks[0] == "Sentence one. Sentence two."
    assert chunks[1] == "Sentence three."

def test_split_text_hard_split():
    # Single word longer than limit
    text = "A" * 50
    chunks = split_text_into_chunks(text, limit=20)
    assert len(chunks) == 3
    assert len(chunks[0]) == 20
    assert len(chunks[1]) == 20
    assert len(chunks[2]) == 10

def test_combine_mp3():
    c1 = b"part1"
    c2 = b"part2"
    combined = combine_audio_data([c1, c2], "MP3")
    assert combined == b"part1part2"

def test_combine_wav():
    # Mock WAV header (44 bytes)
    # ChunkSize at offset 4 (4 bytes)
    # Subchunk2Size at offset 40 (4 bytes)
    
    # Chunk 1: Header + 10 bytes data
    # ChunkSize = 36 + 10 = 46
    # Subchunk2Size = 10
    header1 = bytearray(44)
    struct.pack_into('<I', header1, 4, 46)
    struct.pack_into('<I', header1, 40, 10)
    c1 = bytes(header1) + b"A" * 10
    
    # Chunk 2: Header + 20 bytes data
    # ChunkSize = 36 + 20 = 56
    # Subchunk2Size = 20
    header2 = bytearray(44)
    struct.pack_into('<I', header2, 4, 56)
    struct.pack_into('<I', header2, 40, 20)
    c2 = bytes(header2) + b"B" * 20
    
    combined = combine_audio_data([c1, c2], "WAV")
    
    # Expected:
    # Header from c1, patched.
    # Total data = 30 bytes.
    # New ChunkSize = 36 + 30 = 66
    # New Subchunk2Size = 30
    # Data = A...B...
    
    assert len(combined) == 44 + 30
    
    new_chunk_size = struct.unpack_from('<I', combined, 4)[0]
    new_sub_size = struct.unpack_from('<I', combined, 40)[0]
    
    assert new_sub_size == 30
    assert new_chunk_size == 66
    assert combined[44:] == b"A" * 10 + b"B" * 20

def test_split_text_multibyte():
    # Emoji is 4 bytes.
    # Text: 3 emojis. 12 bytes. Limit 10.
    text = "🙂🙂🙂"
    chunks = split_text_into_chunks(text, limit=10)
    # Should split. "🙂🙂" (8 bytes) and "🙂" (4 bytes).
    assert len(chunks) == 2
    assert chunks[0] == "🙂🙂"
    assert chunks[1] == "🙂"
