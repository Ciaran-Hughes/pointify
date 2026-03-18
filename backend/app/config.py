import os
import secrets
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # Ollama
    ollama_url: str = "http://localhost:11434"
    ollama_model: str = "gpt-oss:20b"

    # JWT
    jwt_secret: str = ""
    jwt_algorithm: str = "HS256"
    jwt_access_expire_minutes: int = 30
    jwt_refresh_expire_days: int = 7

    # Database
    db_path: str = "data/pointify.db"

    # CORS
    cors_origins: str = "http://localhost:5173"

    # Logging
    log_level: str = "INFO"

    # File upload limits
    max_upload_mb: int = 50
    max_recording_minutes: int = 5

    # API docs (off by default; set ENABLE_DOCS=true for local development)
    enable_docs: bool = False

    # Buffer (optional — feature is disabled when token is empty)
    buffer_api_token: str = ""
    buffer_organization_id: str = ""

    @property
    def buffer_enabled(self) -> bool:
        return bool(self.buffer_api_token)

    @property
    def cors_origins_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    @property
    def max_upload_bytes(self) -> int:
        return self.max_upload_mb * 1024 * 1024

    @property
    def db_url(self) -> str:
        db_file = Path(self.db_path)
        db_file.parent.mkdir(parents=True, exist_ok=True)
        return f"sqlite:///{db_file.resolve()}"

    def ensure_jwt_secret(self) -> str:
        """Return JWT secret, auto-generating and persisting if not set."""
        if self.jwt_secret:
            return self.jwt_secret
        # Auto-generate and write to .env
        new_secret = secrets.token_hex(32)
        env_path = Path(".env")
        if env_path.exists():
            content = env_path.read_text()
            if "JWT_SECRET=" in content:
                lines = [
                    f"JWT_SECRET={new_secret}" if l.startswith("JWT_SECRET=") else l
                    for l in content.splitlines()
                ]
                env_path.write_text("\n".join(lines) + "\n")
            else:
                with env_path.open("a") as f:
                    f.write(f"\nJWT_SECRET={new_secret}\n")
        else:
            env_path.write_text(f"JWT_SECRET={new_secret}\n")
        os.environ["JWT_SECRET"] = new_secret
        return new_secret


settings = Settings()
