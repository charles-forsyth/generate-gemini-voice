import pytest
import struct
import os
from unittest.mock import MagicMock, patch
from generate_gemini_voice.utils import split_text_into_chunks
from generate_gemini_voice.core import generate_speech, _synthesize_single_chunk

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

def test_split_text_multibyte():
    # Emoji is 4 bytes.
    # Text: 3 emojis. 12 bytes. Limit 10.
    text = "🙂🙂🙂"
    chunks = split_text_into_chunks(text, limit=10)
    # Should split. "🙂🙂" (8 bytes) and "🙂" (4 bytes).
    assert len(chunks) == 2
    assert chunks[0] == "🙂🙂"
    assert chunks[1] == "🙂"

def test_split_text_strict_bytes():
    # Construct a string where chars are 4 bytes.
    # 20 chars = 80 bytes. Limit 30 bytes.
    # Should split into chunks of max 7 chars (28 bytes).
    text = "🙂" * 20
    chunks = split_text_into_chunks(text, limit=30)
    
    for c in chunks:
        assert len(c.encode('utf-8')) <= 30
    
    assert len(chunks) >= 3
    assert "".join(chunks) == text

@patch('generate_gemini_voice.core._synthesize_single_chunk')
def test_generate_speech_streaming_mp3(mock_synthesize, tmp_path):
    """Test streaming MP3 concatenation."""
    # Mock return 3 chunks
    mock_synthesize.side_effect = [b"chunk1", b"chunk2", b"chunk3"]
    
    output_file = tmp_path / "stream_test.mp3"
    
    # We need to mock split_text_into_chunks too, or provide text that splits into 3
    with patch('generate_gemini_voice.core.split_text_into_chunks') as mock_split:
        mock_split.return_value = ["t1", "t2", "t3"]
        
        generate_speech(
            text="ignored",
            output_file=str(output_file),
            audio_format="MP3"
        )
        
    assert output_file.read_bytes() == b"chunk1chunk2chunk3"

@patch('generate_gemini_voice.core._synthesize_single_chunk')
def test_generate_speech_streaming_wav(mock_synthesize, tmp_path):
    """Test streaming WAV stitching and header patching."""
    # Construct Mock WAV chunks
    # Chunk 1: Header + 10 bytes "A"
    header1 = bytearray(44)
    struct.pack_into('<I', header1, 4, 36+10) # ChunkSize
    struct.pack_into('<I', header1, 40, 10)    # Subchunk2Size
    c1 = bytes(header1) + b"A"*10
    
    # Chunk 2: Header + 20 bytes "B"
    header2 = bytearray(44)
    struct.pack_into('<I', header2, 4, 36+20)
    struct.pack_into('<I', header2, 40, 20)
    c2 = bytes(header2) + b"B"*20
    
    mock_synthesize.side_effect = [c1, c2]
    
    output_file = tmp_path / "stream_test.wav"
    
    with patch('generate_gemini_voice.core.split_text_into_chunks') as mock_split:
        mock_split.return_value = ["t1", "t2"]
        
        generate_speech(
            text="ignored",
            output_file=str(output_file),
            audio_format="WAV"
        )
        
    content = output_file.read_bytes()
    
    # Expected: 44 header + 10 A + 20 B = 74 bytes total
    assert len(content) == 74
    
    # Check patched header
    chunk_size = struct.unpack_from('<I', content, 4)[0]
    sub_size = struct.unpack_from('<I', content, 40)[0]
    
    assert sub_size == 30 # 10 + 20
    assert chunk_size == 66 # 36 + 30
    assert content[44:] == b"A"*10 + b"B"*20