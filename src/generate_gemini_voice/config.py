from pathlib import Path
from typing import Optional
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

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
        env_file=[".env", str(Path.home() / ".env")],
        env_file_encoding="utf-8",
        extra="ignore"
    )

settings = Settings()