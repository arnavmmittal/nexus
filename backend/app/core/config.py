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

    # Database
    database_url: str = "postgresql+asyncpg://nexus:nexus@localhost:5432/nexus"
    database_url_sync: str = "postgresql://nexus:nexus@localhost:5432/nexus"

    # Redis
    redis_url: str = "redis://localhost:6379"

    # Vector Database
    chromadb_path: str = "./data/chroma"

    # Obsidian Integration
    obsidian_vault_path: str = ""

    # Claude History
    claude_history_path: str = "~/.claude/projects"

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
