"""Application configuration using Pydantic Settings."""

import json
from pathlib import Path
from typing import List

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # AI Configuration
    anthropic_api_key: str = ""
    openai_api_key: str = ""

    # Voice / ElevenLabs Configuration
    elevenlabs_api_key: str = ""
    elevenlabs_voice_id: str = ""  # Defaults to "Adam" in client if empty

    # GitHub Integration
    github_token: str = ""  # Personal access token for GitHub API

    # Supabase Configuration (optional - only needed if using Supabase)
    supabase_url: str = ""
    supabase_anon_key: str = ""

    # Database Configuration
    # Default: SQLite (zero setup, perfect for single-user)
    # Optional: PostgreSQL/Supabase for production or multi-user
    database_url: str = "sqlite+aiosqlite:///./data/nexus.db"
    database_url_sync: str = "sqlite:///./data/nexus.db"

    # Redis
    redis_url: str = "redis://localhost:6379"

    # Vector Database
    chromadb_path: str = "./data/chroma"

    # Obsidian Integration
    obsidian_vault_path: str = ""

    # Claude History
    claude_history_path: str = "~/.claude/projects"

    # Google OAuth Configuration
    google_client_id: str = ""
    google_client_secret: str = ""
    google_redirect_uri: str = "http://localhost:8000/api/integrations/google/callback"

    # Plaid Configuration (for banking/investment integration)
    plaid_client_id: str = ""
    plaid_secret: str = ""
    plaid_env: str = "sandbox"  # sandbox, development, or production

    # Server Configuration
    host: str = "0.0.0.0"
    port: int = 8000
    debug: bool = True

    # CORS Configuration
    cors_origins: List[str] = ["http://localhost:3000", "http://127.0.0.1:3000"]

    @field_validator("cors_origins", mode="before")
    @classmethod
    def parse_cors_origins(cls, v: str | List[str]) -> List[str]:
        """Parse CORS origins from JSON string or list."""
        if isinstance(v, str):
            try:
                return json.loads(v)
            except json.JSONDecodeError:
                return [origin.strip() for origin in v.split(",")]
        return v

    @property
    def is_sqlite(self) -> bool:
        """Check if using SQLite database."""
        return self.database_url.startswith("sqlite")

    @property
    def chromadb_path_resolved(self) -> Path:
        """Get resolved ChromaDB path."""
        return Path(self.chromadb_path).expanduser().resolve()

    @property
    def obsidian_vault_path_resolved(self) -> Path | None:
        """Get resolved Obsidian vault path."""
        if not self.obsidian_vault_path:
            return None
        return Path(self.obsidian_vault_path).expanduser().resolve()

    @property
    def claude_history_path_resolved(self) -> Path:
        """Get resolved Claude history path."""
        return Path(self.claude_history_path).expanduser().resolve()


settings = Settings()
