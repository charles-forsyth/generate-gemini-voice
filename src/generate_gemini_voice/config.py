import os
import stat
import sys
from pathlib import Path
from typing import Optional

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

# The ONLY config file this tool reads. We deliberately do not read ./.env or
# ~/.env: those commonly hold unrelated keys for other tools, and silently
# picking one up is how the wrong (or a dead) key ends up being used.
APP_NAME = "generate-gemini-voice"
USER_CONFIG_DIR = Path.home() / ".config" / APP_NAME
USER_CONFIG_FILE = USER_CONFIG_DIR / ".env"

PLACEHOLDER_KEY = "replace_with_your_api_key"


def ensure_config_exists() -> None:
    """Create the config file with placeholders if missing; keep it owner-only."""
    if not USER_CONFIG_FILE.exists():
        try:
            USER_CONFIG_DIR.mkdir(parents=True, exist_ok=True)
            # Create with 0600 from the start, never world-readable even briefly.
            fd = os.open(USER_CONFIG_FILE, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
            with os.fdopen(fd, "w") as f:
                f.write(
                    f"# Configuration for {APP_NAME}\n"
                    "# GEMINI_API_KEY: restrict to generativelanguage.googleapis.com.\n"
                    "#   Used by the default Gemini 3.8 TTS models.\n"
                    "# GOOGLE_API_KEY: restrict to texttospeech.googleapis.com.\n"
                    "#   Used for Chirp 3 HD voices. Gemini 2.5 TTS models use\n"
                    "#   gcloud application-default credentials instead.\n\n"
                    f"GEMINI_API_KEY={PLACEHOLDER_KEY}\n"
                    f"GOOGLE_API_KEY={PLACEHOLDER_KEY}\n"
                    "GCLOUD_PROJECT=replace_with_your_project_id\n"
                    "PYGAME_HIDE_SUPPORT_PROMPT=1\n"
                )
            print(
                f"Created new configuration file at: {USER_CONFIG_FILE}",
                file=sys.stderr,
            )
            print(
                "Edit it to add your GOOGLE_API_KEY and GCLOUD_PROJECT.",
                file=sys.stderr,
            )
        except OSError as e:
            print(f"Warning: could not create {USER_CONFIG_FILE}: {e}", file=sys.stderr)
        return

    # Existing file: tighten permissions if group/other can read it.
    try:
        mode = stat.S_IMODE(USER_CONFIG_FILE.stat().st_mode)
        if mode & 0o077:
            os.chmod(USER_CONFIG_FILE, 0o600)
            print(
                f"Note: tightened permissions on {USER_CONFIG_FILE} to 600.",
                file=sys.stderr,
            )
    except OSError:
        pass


def mask_key(key: Optional[str]) -> str:
    """Show only the last 4 characters of a secret."""
    if not key:
        return "<none>"
    return f"...{key[-4:]}" if len(key) > 8 else "<set>"


class Settings(BaseSettings):
    google_api_key: Optional[str] = Field(
        default=None, validation_alias="GOOGLE_API_KEY"
    )
    # Gemini API key (restrict to generativelanguage.googleapis.com). Used for
    # the Gemini 3.8 TTS models, which are only on the Gemini API today.
    gemini_api_key: Optional[str] = Field(
        default=None, validation_alias="GEMINI_API_KEY"
    )
    gcloud_project: str = Field(
        default="ucr-research-computing", validation_alias="GCLOUD_PROJECT"
    )
    pygame_hide_support_prompt: str = Field(
        default="1", validation_alias="PYGAME_HIDE_SUPPORT_PROMPT"
    )

    # Real environment variables still win over the file (standard behavior),
    # so an explicit `GOOGLE_API_KEY=... generate-voice ...` works for one run.
    model_config = SettingsConfigDict(
        env_file=str(USER_CONFIG_FILE),
        env_file_encoding="utf-8",
        extra="ignore",
    )


settings = Settings()
