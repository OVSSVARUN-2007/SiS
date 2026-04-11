import logging
import shutil
from pathlib import Path

from sqlalchemy import create_engine, inspect, text
from sqlalchemy.engine import make_url
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import declarative_base, sessionmaker

from config import get_settings

settings = get_settings()
PROJECT_ROOT = Path(__file__).resolve().parent
DEFAULT_SQLITE_SNAPSHOT = PROJECT_ROOT / "sqlite_snapshot.db"
DEFAULT_LOCAL_SQLITE = PROJECT_ROOT / "sis.db"
_database_ready = False
logger = logging.getLogger(__name__)


def _sqlite_file_url(path: Path) -> str:
    return f"sqlite:///{path.resolve().as_posix()}"


def _preferred_database_url() -> str:
    configured_url = settings.database_url
    parsed_url = make_url(configured_url)

    # Railway internal hosts resolve only inside Railway's private network.
    if (
        not settings.is_vercel
        and parsed_url.get_backend_name() == "mysql"
        and (parsed_url.host or "").endswith(".railway.internal")
    ):
        return _sqlite_file_url(DEFAULT_LOCAL_SQLITE)

    return configured_url


DATABASE_URL = _preferred_database_url()
DATABASE_BACKEND = make_url(DATABASE_URL).get_backend_name()


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

def _build_engine(database_url: str):
    database_backend = make_url(database_url).get_backend_name()
    engine_kwargs = {"pool_pre_ping": database_backend != "sqlite"}
    if database_backend == "sqlite":
        engine_kwargs["connect_args"] = {"check_same_thread": False}
    return create_engine(database_url, **engine_kwargs)


engine = _build_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


def get_db():
    ensure_database_ready()
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
    global _database_ready, DATABASE_URL, DATABASE_BACKEND, engine, SessionLocal
    if _database_ready or not settings.enable_startup_schema_sync:
        return

    import models  # noqa: F401

    try:
        Base.metadata.create_all(bind=engine)
        ensure_schema_upgrade()
        _database_ready = True
    except OperationalError:
        if settings.is_vercel or DATABASE_BACKEND == "sqlite":
            raise

        logger.warning(
            "Primary database is unreachable; falling back to local SQLite database at %s",
            DEFAULT_LOCAL_SQLITE,
        )
        DATABASE_URL = _sqlite_file_url(DEFAULT_LOCAL_SQLITE)
        DATABASE_BACKEND = "sqlite"
        engine = _build_engine(DATABASE_URL)
        SessionLocal.configure(bind=engine)
        Base.metadata.create_all(bind=engine)
        ensure_schema_upgrade()
        _database_ready = True
