from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    database_url: str = "sqlite:///./edm_platform.db"
    data_dir: str = "./data"
    jwt_secret: str = "change-me-dev-only"
    jwt_expire_minutes: int = 120
    event_bus: str = "inprocess"
    kafka_bootstrap_servers: str = "localhost:9092"
    cors_origins: str = "http://localhost:5173"
    secret_encryption_key: str = "change-me-dev-only-32-bytes-min!!"
    enable_scheduler: bool = True
    max_upload_mb: int = 100
    auth_rate_limit_max_attempts: int = 10
    auth_rate_limit_window_seconds: int = 300
    smtp_host: str = ""
    smtp_port: int = 587
    smtp_username: str = ""
    smtp_password: str = ""
    smtp_from_address: str = "edm-platform@example.com"
    smtp_use_tls: bool = True
    webhook_timeout_seconds: int = 5

    @property
    def data_path(self) -> Path:
        path = Path(self.data_dir)
        path.mkdir(parents=True, exist_ok=True)
        return path

    @property
    def cors_origin_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]

    def weak_secret_warnings(self) -> list[str]:
        """Human-readable warnings about secrets that are still at their insecure
        out-of-the-box defaults, or too short to be a real secret. Logged loudly at
        startup (see app/main.py) rather than enforced -- a hard failure here would
        break the zero-config first run .env.example is designed for; the goal is to
        make running insecurely a visible choice, not a silent one."""
        warnings = []
        if self.jwt_secret == "change-me-dev-only":
            warnings.append("JWT_SECRET is still the default value -- anyone can forge tokens")
        elif len(self.jwt_secret) < 32:
            warnings.append("JWT_SECRET is shorter than the recommended 32 bytes")
        if self.secret_encryption_key == "change-me-dev-only-32-bytes-min!!":
            warnings.append(
                "SECRET_ENCRYPTION_KEY is still the default value -- stored credentials "
                "are only as safe as this secret"
            )
        return warnings


settings = Settings()
