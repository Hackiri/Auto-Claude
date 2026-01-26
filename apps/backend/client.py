"""
Claude client module facade.

Provides Claude API client utilities.
Uses lazy imports to avoid circular dependencies.
"""

from typing import Any


def __getattr__(name: str) -> Any:
    """Lazy import to avoid circular imports with auto_claude_tools."""
    from core import client as _client

    return getattr(_client, name)


def create_client(*args: Any, **kwargs: Any) -> Any:
    """Create a Claude client instance."""
    from core.client import create_client as _create_client

    return _create_client(*args, **kwargs)


__all__ = [
    "create_client",
]
