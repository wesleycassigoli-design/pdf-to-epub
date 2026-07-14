from functools import lru_cache
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # ─── App ────────────────────────────────────────────────────────────────
    app_env: str = "development"
    secret_key: str = "change-me-in-production"
    debug: bool = False

    # ─── Database ───────────────────────────────────────────────────────────
    database_url: str

    # ─── Supabase ───────────────────────────────────────────────────────────
    supabase_url: str = ""
    supabase_service_key: str = ""
    supabase_storage_bucket: str = "pdf-epub-files"

    # ─── Upload ─────────────────────────────────────────────────────────────
    max_upload_mb: int = 100
    allowed_extensions: str = "pdf"

    # ─── Paths ──────────────────────────────────────────────────────────────
    output_dir: str = "/app/output"
    temp_dir: str = "/tmp/pdfepub"

    # ─── CORS ───────────────────────────────────────────────────────────────
    cors_origins: str = "http://localhost:3000"

    class Config:
        env_file = ".env"
        case_sensitive = False

    @property
    def max_upload_bytes(self) -> int:
        return self.max_upload_mb * 1024 * 1024

    @property
    def cors_origins_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",")]


@lru_cache()
def get_settings() -> Settings:
    return Settings()
