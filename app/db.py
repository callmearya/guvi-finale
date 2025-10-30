"""SQLAlchemy helper for PostgreSQL connections."""
from sqlalchemy import create_engine
from sqlalchemy.orm import scoped_session, sessionmaker, declarative_base

from app.config import get_settings


settings = get_settings()


engine = create_engine(
    settings.database_url,
    echo=settings.database_echo,
    pool_pre_ping=True,
    future=True,
)

SessionLocal = scoped_session(
    sessionmaker(autocommit=False, autoflush=False, bind=engine)
)

Base = declarative_base()


def init_db() -> None:
    """Create database tables if they are missing."""
    from app.models import db_models  # noqa: F401 -- register models

    Base.metadata.create_all(bind=engine)
