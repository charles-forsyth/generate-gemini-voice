from pathlib import Path
from typing import Optional
import sys
import os
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

# Define the user config directory and file path
APP_NAME = "generate-gemini-voice"
USER_CONFIG_DIR = Path.home() / ".config" / APP_NAME
USER_CONFIG_FILE = USER_CONFIG_DIR / ".env"

def ensure_config_exists():
    """Checks for the user config file and creates it with placeholders if missing."""
    if not USER_CONFIG_FILE.exists():
        try:
            USER_CONFIG_DIR.mkdir(parents=True, exist_ok=True)
            with open(USER_CONFIG_FILE, "w") as f:
                f.write(
                    f"# Configuration for {APP_NAME}\n"
                    f"# Generated automatically. Please update with your values.\n\n"
                    f"GOOGLE_API_KEY=replace_with_your_api_key\n"
                    f"GCLOUD_PROJECT=replace_with_your_project_id\n"
                    f"# Optional: Hide pygame support prompt\n"
                    f"PYGAME_HIDE_SUPPORT_PROMPT=1\n"
                )
            # Secure the file so only the owner can read/write it
            try:
                os.chmod(USER_CONFIG_FILE, 0o600)
            except OSError as e:
                print(f"Warning: Could not set secure permissions on {USER_CONFIG_FILE}: {e}", file=sys.stderr)

            print(f"Created new configuration file at: {USER_CONFIG_FILE}", file=sys.stderr)
            print("Please edit this file to add your GOOGLE_API_KEY and GCLOUD_PROJECT.", file=sys.stderr)
        except Exception as e:
            print(f"Warning: Could not create configuration file at {USER_CONFIG_FILE}: {e}", file=sys.stderr)

# ensure_config_exists() # Removed side effect on import

class Settings(BaseSettings):
    google_application_credentials: Optional[str] = Field(
        default=None, 
        description="Path to the Google Cloud service account key file."
    )
    google_api_key: Optional[str] = Field(
        default=None,
        validation_alias="GOOGLE_API_KEY",
        description="Google Cloud API Key for authentication."
    )
    gcloud_project: str = Field(
        default="ucr-research-computing",
        validation_alias="GCLOUD_PROJECT",
        description="Google Cloud Project ID."
    )
    pygame_hide_support_prompt: str = Field(
        default="1",
        validation_alias="PYGAME_HIDE_SUPPORT_PROMPT"
    )

    model_config = SettingsConfigDict(
        env_file=[".env", str(Path.home() / ".env"), str(USER_CONFIG_FILE)],
        env_file_encoding="utf-8",
        extra="ignore"
    )

settings = Settings()