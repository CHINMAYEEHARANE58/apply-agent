"""Compatibility import; use app.config.settings in new modules."""

from app.config.settings import Settings, get_settings

__all__ = ["Settings", "get_settings"]
