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

    @property
    def data_path(self) -> Path:
        path = Path(self.data_dir)
        path.mkdir(parents=True, exist_ok=True)
        return path

    @property
    def cors_origin_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]


settings = Settings()
