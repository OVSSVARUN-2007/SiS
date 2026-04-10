from sqlalchemy import create_engine, text
from sqlalchemy.orm import declarative_base, sessionmaker

from config import get_settings

settings = get_settings()
DATABASE_URL = settings.database_url

engine = create_engine(DATABASE_URL, pool_pre_ping=True)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def _column_exists(connection, table_name: str, column_name: str) -> bool:
    query = text(
        """
        SELECT COUNT(*) AS cnt
        FROM information_schema.COLUMNS
        WHERE TABLE_SCHEMA = :schema
          AND TABLE_NAME = :table
          AND COLUMN_NAME = :column
        """
    )
    result = connection.execute(
        query,
        {"schema": settings.db_name, "table": table_name, "column": column_name},
    ).scalar()
    return bool(result)


def ensure_schema_upgrade() -> None:
    upgrades = [
        ("student_register", "department", "VARCHAR(100) NULL"),
        ("student_register", "academic_year", "INT NULL"),
        ("student_register", "section", "VARCHAR(20) NULL"),
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
            connection.execute(
                text(f"ALTER TABLE `{table_name}` ADD COLUMN `{column_name}` {definition}")
            )
