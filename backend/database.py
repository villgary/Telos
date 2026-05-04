import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base
from backend.config import get_settings

settings = get_settings()
DATABASE_URL = settings.database_url

is_sqlite = DATABASE_URL.startswith("sqlite")

connect_args = {}
if not is_sqlite:
    connect_args["sslmode"] = settings.db_ssl_mode

if is_sqlite:
    engine = create_engine(
        DATABASE_URL,
        connect_args=connect_args,
        echo=False,
    )
else:
    engine = create_engine(
        DATABASE_URL,
        pool_size=settings.db_pool_size,
        max_overflow=settings.db_max_overflow,
        pool_recycle=int(os.getenv("DB_POOL_RECYCLE", "3600")),
        pool_pre_ping=True,
        echo=False,
        connect_args=connect_args,
    )

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db():
    """Initialize database.

    Note: This is now a no-op since database schema management is handled
    by Alembic migrations. This function is kept for backwards compatibility.
    """
    pass
