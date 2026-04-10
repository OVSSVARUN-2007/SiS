import os
import tempfile
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import quote_plus

from dotenv import load_dotenv

load_dotenv()


@dataclass(frozen=True)
class Settings:
    database_url_override: str
    db_user: str
    db_password: str
    db_host: str
    db_port: str
    db_name: str
    secret_key: str
    hf_api_key: str
    hf_model_id: str
    admin_setup_key: str
    is_vercel: bool
    enable_startup_schema_sync: bool

    @property
    def database_url(self) -> str:
        if self.database_url_override:
            return self.database_url_override
        escaped_password = quote_plus(self.db_password)
        return (
            f"mysql+pymysql://{self.db_user}:{escaped_password}"
            f"@{self.db_host}:{self.db_port}/{self.db_name}"
        )


def _read_env(name: str, default: str = "") -> str:
    return (os.getenv(name, default) or "").strip()


def _read_first_env(*names: str, default: str = "") -> str:
    for name in names:
        value = _read_env(name)
        if value:
            return value
    return default


def _default_database_url(is_vercel: bool) -> str:
    explicit_url = _read_env("DATABASE_URL")
    if explicit_url:
        return explicit_url
    if is_vercel:
        temp_root = Path("/tmp")
        if os.name == "nt":
            temp_root = Path(tempfile.gettempdir())
        return f"sqlite:///{(temp_root / 'sis.db').resolve().as_posix()}"
    return ""


def get_settings() -> Settings:
    is_vercel = _read_env("VERCEL", "") == "1"
    auto_migrate_default = "true"
    enable_startup_schema_sync = _read_env("ENABLE_STARTUP_SCHEMA_SYNC", auto_migrate_default).lower() in {
        "1",
        "true",
        "yes",
        "on",
    }

    return Settings(
        database_url_override=_default_database_url(is_vercel),
        db_user=_read_env("DB_USER", "root"),
        db_password=_read_env("DB_PASSWORD", ""),
        db_host=_read_env("DB_HOST", "localhost"),
        db_port=_read_env("DB_PORT", "3306"),
        db_name=_read_env("DB_NAME", "sis"),
        secret_key=_read_env("SECRET_KEY", "change-me-now"),
        hf_api_key=_read_first_env("HF_API_KEY", "HUGGINGFACE_API_KEY"),
        hf_model_id=_read_env("HF_MODEL_ID", "mistralai/Mistral-7B-Instruct-v0.1"),
        admin_setup_key=_read_env("ADMIN_SETUP_KEY", ""),
        is_vercel=is_vercel,
        enable_startup_schema_sync=enable_startup_schema_sync,
    )
