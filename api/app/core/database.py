"""Compatibility import; use app.config.database in new modules."""

from app.config.database import Base, SessionLocal, engine, get_session

__all__ = ["Base", "SessionLocal", "engine", "get_session"]
