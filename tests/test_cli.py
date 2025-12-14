import pytest
from unittest.mock import patch, MagicMock
from generate_gemini_voice.cli import main
import sys

def test_cli_list_voices(mock_tts_client, capsys):
    """Test the --list-voices argument."""
    with patch.object(sys, 'argv', ["generate-voice", "--list-voices"]):
        # It returns instead of exiting, so we just call it
        main()
    
    mock_tts_client.list_voices.assert_called_once()
    captured = capsys.readouterr()
    assert "Available 'en-US' 'Chirp3' Voices" in captured.out

def test_cli_generate_text(mock_tts_client, mock_pygame, tmp_path):
    """Test generating voice from text argument."""
    output = tmp_path / "cli_test.mp3"
    with patch.object(sys, 'argv', [
        "generate-voice", 
        "Hello World", 
        "--output-file", str(output),
        "--no-play"
    ]):
        main()
        
    mock_tts_client.synthesize_speech.assert_called_once()
    # Ensure file was created (by our mock core logic or the actual file write in core)
    # Since we mocked the client, the core logic still runs and writes the "fake_audio_content"
    assert output.exists()
    assert output.read_bytes() == b"fake_audio_content"

def test_cli_generate_temp(mock_tts_client, mock_pygame):
    """Test generating voice to a temp file."""
    with patch.object(sys, 'argv', [
        "generate-voice", 
        "Hello World", 
        "--temp"
    ]):
        main()
        
    mock_tts_client.synthesize_speech.assert_called_once()
    # Verify play_audio was called
    # We mocked pygame module in utils, so we check if mixer.music.play was called
    mock_pygame.mixer.music.play.assert_called()

def test_cli_no_input(capsys):
    """Test CLI fails with no input."""
    # We mock isatty to True so it doesn't try to read from stdin
    with patch('sys.stdin.isatty', return_value=True):
        with patch.object(sys, 'argv', ["generate-voice"]):
            with pytest.raises(SystemExit):
                main()
    
    captured = capsys.readouterr()
    assert "No input provided" in captured.err or "usage:" in captured.err

def test_cli_invalid_voice(mock_tts_client, capsys):
    """Test CLI fails with invalid voice name."""
    with patch.object(sys, 'argv', ["generate-voice", "Hi", "--voice-name", "INVALID"]):
        with pytest.raises(SystemExit):
            main()
    
    captured = capsys.readouterr()
    assert "Invalid voice name" in captured.err