import shutil
from pathlib import Path

from sqlalchemy import create_engine, inspect, text
from sqlalchemy.engine import make_url
from sqlalchemy.orm import declarative_base, sessionmaker

from config import get_settings

settings = get_settings()
DATABASE_URL = settings.database_url
DATABASE_BACKEND = make_url(DATABASE_URL).get_backend_name()
PROJECT_ROOT = Path(__file__).resolve().parent
DEFAULT_SQLITE_SNAPSHOT = PROJECT_ROOT / "sqlite_snapshot.db"
_database_ready = False


def _prepare_vercel_sqlite_target() -> None:
    if DATABASE_BACKEND != "sqlite" or not settings.is_vercel:
        return

    database_path = make_url(DATABASE_URL).database or ""
    if not database_path.startswith("/tmp/"):
        return

    target = Path(database_path)
    if target.exists() or not DEFAULT_SQLITE_SNAPSHOT.exists():
        return

    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(DEFAULT_SQLITE_SNAPSHOT, target)


_prepare_vercel_sqlite_target()

engine_kwargs = {"pool_pre_ping": DATABASE_BACKEND != "sqlite"}
if DATABASE_BACKEND == "sqlite":
    engine_kwargs["connect_args"] = {"check_same_thread": False}

engine = create_engine(DATABASE_URL, **engine_kwargs)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def _column_exists(connection, table_name: str, column_name: str) -> bool:
    inspector = inspect(connection)
    columns = inspector.get_columns(table_name)
    return any(column["name"] == column_name for column in columns)


def ensure_schema_upgrade() -> None:
    upgrades = [
        ("student_register", "department", "VARCHAR(100) NULL"),
        ("student_register", "academic_year", "INT NULL"),
        ("student_register", "section", "VARCHAR(20) NULL"),
        ("student_register", "email_verified", "INT NULL DEFAULT 0"),
        ("student_register", "email_otp_code", "VARCHAR(10) NULL"),
        ("student_register", "email_otp_expires_at", "TIMESTAMP NULL"),
        ("student_register", "email_otp_sent_at", "TIMESTAMP NULL"),
        ("student_requests", "proof_url", "VARCHAR(500) NULL"),
        ("student_requests", "admin_remark", "TEXT NULL"),
        ("student_requests", "reviewed_by", "INT NULL"),
        ("student_requests", "reviewed_at", "TIMESTAMP NULL"),
        ("assignments", "department", "VARCHAR(100) NULL"),
        ("assignments", "academic_year", "INT NULL"),
        ("assignments", "section", "VARCHAR(20) NULL"),
        ("attendance", "department", "VARCHAR(100) NULL"),
        ("attendance", "academic_year", "INT NULL"),
        ("attendance", "section", "VARCHAR(20) NULL"),
        ("attendance", "marked_by", "INT NULL"),
        ("notices", "category", "ENUM('notice','internship','job') NOT NULL DEFAULT 'notice'"),
        ("notices", "department", "VARCHAR(100) NULL"),
        ("notices", "academic_year", "INT NULL"),
        ("notices", "section", "VARCHAR(20) NULL"),
        ("documents", "category", "ENUM('document','internship','job') NOT NULL DEFAULT 'document'"),
        ("documents", "department", "VARCHAR(100) NULL"),
        ("documents", "academic_year", "INT NULL"),
        ("documents", "section", "VARCHAR(20) NULL"),
    ]

    with engine.begin() as connection:
        for table_name, column_name, definition in upgrades:
            if _column_exists(connection, table_name, column_name):
                continue
            if DATABASE_BACKEND == "mysql":
                connection.execute(
                    text(f"ALTER TABLE `{table_name}` ADD COLUMN `{column_name}` {definition}")
                )
            else:
                sqlite_definition = (
                    definition.replace("ENUM('notice','internship','job') NOT NULL DEFAULT 'notice'", "VARCHAR(20) NOT NULL DEFAULT 'notice'")
                    .replace("ENUM('document','internship','job') NOT NULL DEFAULT 'document'", "VARCHAR(20) NOT NULL DEFAULT 'document'")
                )
                connection.execute(
                    text(f'ALTER TABLE "{table_name}" ADD COLUMN "{column_name}" {sqlite_definition}')
                )


def ensure_database_ready() -> None:
    global _database_ready
    if _database_ready or not settings.enable_startup_schema_sync:
        return

    import models  # noqa: F401

    Base.metadata.create_all(bind=engine)
    ensure_schema_upgrade()
    _database_ready = True
