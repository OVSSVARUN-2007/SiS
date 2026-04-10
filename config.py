import os
from dataclasses import dataclass
from urllib.parse import quote_plus

from dotenv import load_dotenv

load_dotenv()


@dataclass(frozen=True)
class Settings:
    db_user: str
    db_password: str
    db_host: str
    db_port: str
    db_name: str
    secret_key: str
    hf_api_key: str
    hf_model_id: str
    admin_setup_key: str

    @property
    def database_url(self) -> str:
        escaped_password = quote_plus(self.db_password)
        return (
            f"mysql+pymysql://{self.db_user}:{escaped_password}"
            f"@{self.db_host}:{self.db_port}/{self.db_name}"
        )


def _read_env(name: str, default: str = "") -> str:
    return (os.getenv(name, default) or "").strip()


def get_settings() -> Settings:
    return Settings(
        db_user=_read_env("DB_USER", "root"),
        db_password=_read_env("DB_PASSWORD", ""),
        db_host=_read_env("DB_HOST", "localhost"),
        db_port=_read_env("DB_PORT", "3306"),
        db_name=_read_env("DB_NAME", "sis"),
        secret_key=_read_env("SECRET_KEY", "change-me-now"),
        hf_api_key=_read_env("HF_API_KEY", ""),
        hf_model_id=_read_env("HF_MODEL_ID", "mistralai/Mistral-7B-Instruct-v0.1"),
        admin_setup_key=_read_env("ADMIN_SETUP_KEY", ""),
    )
