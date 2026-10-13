from collections.abc import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.config.connection import postgres_connection_url
from app.config.settings import get_settings


class Base(DeclarativeBase):
    pass


engine = create_engine(
    postgres_connection_url(get_settings().database_url),
    pool_pre_ping=True,
    pool_recycle=300,
    hide_parameters=True,
)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)


def get_session() -> Generator[Session, None, None]:
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()
