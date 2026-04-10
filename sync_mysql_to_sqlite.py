import os
import shutil
from pathlib import Path

from sqlalchemy import MetaData, create_engine, delete, inspect, select
from sqlalchemy.engine import URL
from sqlalchemy.exc import OperationalError

from config import get_settings
from database import Base
import models  # noqa: F401


TARGET_SQLITE_PATH = Path("sqlite_snapshot.db")


def build_mysql_url() -> str:
    settings = get_settings()
    if settings.database_url_override and not settings.database_url_override.startswith("sqlite"):
        return settings.database_url_override
    return str(
        URL.create(
            "mysql+pymysql",
            username=settings.db_user,
            password=settings.db_password,
            host=settings.db_host,
            port=int(settings.db_port),
            database=settings.db_name,
        )
    )


def main() -> None:
    mysql_url = build_mysql_url()
    temp_sqlite_path = Path(os.environ.get("TEMP", ".")) / "sis_export.db"
    if temp_sqlite_path.exists():
        temp_sqlite_path.unlink()

    sqlite_url = f"sqlite:///{temp_sqlite_path.resolve().as_posix()}"

    source_engine = create_engine(mysql_url, pool_pre_ping=True)
    target_engine = create_engine(sqlite_url, connect_args={"check_same_thread": False})

    Base.metadata.create_all(bind=target_engine)

    try:
        source_metadata = MetaData()
        source_metadata.reflect(bind=source_engine)
        source_inspector = inspect(source_engine)
    except RuntimeError as exc:
        if "cryptography" in str(exc):
            raise RuntimeError(
                "MySQL authentication needs the 'cryptography' package. "
                "Run 'pip install -r requirements.txt' and try again."
            ) from exc
        raise
    except OperationalError as exc:
        raise RuntimeError(
            "Could not connect to MySQL with the current .env settings. "
            "Check DB_USER, DB_PASSWORD, DB_HOST, DB_PORT, and DB_NAME, then run the export again."
        ) from exc

    table_names = [table.name for table in Base.metadata.sorted_tables]

    with source_engine.connect() as source_connection, target_engine.begin() as target_connection:
        for table in reversed(Base.metadata.sorted_tables):
            target_connection.execute(delete(table))

        for table_name in table_names:
            if not source_inspector.has_table(table_name):
                print(f"Skipping missing MySQL table: {table_name}")
                continue

            source_table = source_metadata.tables[table_name]
            target_table = Base.metadata.tables[table_name]
            rows = source_connection.execute(select(source_table)).mappings().all()
            if not rows:
                print(f"Copied 0 rows from {table_name}")
                continue

            target_connection.execute(target_table.insert(), [dict(row) for row in rows])
            print(f"Copied {len(rows)} rows from {table_name}")

    if TARGET_SQLITE_PATH.exists():
        TARGET_SQLITE_PATH.unlink()
    shutil.copyfile(temp_sqlite_path, TARGET_SQLITE_PATH)
    print(f"SQLite snapshot created at {TARGET_SQLITE_PATH.resolve()}")


if __name__ == "__main__":
    main()
