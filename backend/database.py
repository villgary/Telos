import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base
from backend.config import get_settings

settings = get_settings()
DATABASE_URL = settings.database_url

is_sqlite = DATABASE_URL.startswith("sqlite")
if not is_sqlite:
    os.environ["DB_SSLMODE"] = settings.db_ssl_mode

connect_args = {}
if not is_sqlite:
    connect_args["sslmode"] = os.getenv("DB_SSLMODE", "prefer")

if is_sqlite:
    engine = create_engine(
        DATABASE_URL,
        connect_args=connect_args,
        echo=False,
    )
else:
    engine = create_engine(
        DATABASE_URL,
        pool_size=int(os.getenv("DB_POOL_SIZE", "10")),
        max_overflow=int(os.getenv("DB_MAX_OVERFLOW", "20")),
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
    from backend import models  # noqa: F401
    Base.metadata.create_all(bind=engine)
