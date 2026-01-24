#!/usr/bin/env python3
"""
Conversation Session Storage
============================

Provides JSONL-based conversation session persistence using the core.session_storage module.
This complements the existing session insights storage by storing full message history.

Features:
- Atomic writes (no corruption on crash)
- Pre-computed headers for fast listing
- Resilient parsing that skips corrupted lines
- Fast session listing for UI without loading all messages

Usage:
    from memory.conversation_sessions import (
        ConversationSessionManager,
        save_conversation_message,
        load_conversation_messages,
    )

    # Initialize manager for a spec
    manager = ConversationSessionManager(spec_dir)

    # Create a new conversation session
    session_id = manager.create_session("Implementing auth feature")

    # Save messages as they stream in
    save_conversation_message(spec_dir, session_id, "user", "Implement login")
    save_conversation_message(spec_dir, session_id, "assistant", "I'll add...")

    # List all sessions (fast - reads only headers)
    sessions = manager.list_sessions()

    # Load full conversation for a session
    messages = load_conversation_messages(spec_dir, session_id)
"""

import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from core.session_storage import (
    SessionHeader,
    SessionManager,
    SessionStorage,
    StoredMessage,
    TodoState,
    generate_id,
    now_iso,
)

from .paths import get_memory_dir

logger = logging.getLogger(__name__)


def get_conversations_dir(spec_dir: Path) -> Path:
    """
    Get the conversations directory for a spec.

    Args:
        spec_dir: Path to spec directory

    Returns:
        Path to conversations directory
    """
    conversations_dir = get_memory_dir(spec_dir) / "conversations"
    conversations_dir.mkdir(parents=True, exist_ok=True)
    return conversations_dir


class ConversationSessionManager:
    """
    Manager for conversation sessions within a spec.

    Wraps SessionManager with spec-aware paths.

    Usage:
        manager = ConversationSessionManager(spec_dir)
        session_id = manager.create_session("Feature: Add auth")
        sessions = manager.list_sessions()
    """

    def __init__(self, spec_dir: Path):
        """
        Initialize conversation session manager.

        Args:
            spec_dir: Path to spec directory
        """
        self.spec_dir = spec_dir
        self.conversations_dir = get_conversations_dir(spec_dir)
        self._manager = SessionManager(str(self.conversations_dir))

    def create_session(
        self,
        name: str,
        session_id: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> str:
        """
        Create a new conversation session.

        Args:
            name: Session name/description
            session_id: Optional ID (auto-generated if not provided)
            metadata: Optional additional metadata

        Returns:
            Session ID
        """
        if session_id is None:
            session_id = generate_id()

        header = SessionHeader(
            id=session_id,
            name=name,
            todo_state=TodoState.IN_PROGRESS,
            created_at=now_iso(),
            updated_at=now_iso(),
            metadata=metadata or {},
        )

        storage = self._manager.get_session(session_id)
        storage.save_atomic(header, [])

        logger.info(f"Created conversation session {session_id}: {name}")
        return session_id

    def get_session(self, session_id: str) -> SessionStorage:
        """
        Get storage for a session.

        Args:
            session_id: Session identifier

        Returns:
            SessionStorage instance
        """
        return self._manager.get_session(session_id)

    def list_sessions(
        self,
        filter_state: TodoState | None = None,
    ) -> list[SessionHeader]:
        """
        List all conversation sessions (fast - reads only headers).

        Args:
            filter_state: Optional state to filter by

        Returns:
            List of session headers
        """
        return self._manager.list_sessions(filter_state)

    def delete_session(self, session_id: str) -> bool:
        """
        Delete a conversation session.

        Args:
            session_id: Session to delete

        Returns:
            True if deleted, False if not found
        """
        return self._manager.delete_session(session_id)

    def archive_session(self, session_id: str) -> None:
        """
        Mark a session as done/archived.

        Args:
            session_id: Session to archive
        """
        self._manager.archive_session(session_id)


def save_conversation_message(
    spec_dir: Path,
    session_id: str,
    role: str,
    content: str,
    tool_use: dict[str, Any] | None = None,
    metadata: dict[str, Any] | None = None,
) -> str:
    """
    Append a message to a conversation session.

    Args:
        spec_dir: Path to spec directory
        session_id: Session ID
        role: Message role (user, assistant, system)
        content: Message content
        tool_use: Optional tool use data
        metadata: Optional additional metadata

    Returns:
        Message ID
    """
    conversations_dir = get_conversations_dir(spec_dir)
    storage = SessionStorage(str(conversations_dir / f"{session_id}.jsonl"))

    # Create message
    message_id = generate_id()
    message = StoredMessage(
        id=message_id,
        role=role,
        content=content,
        timestamp=now_iso(),
        tool_use=tool_use,
        metadata=metadata or {},
    )

    # Append to session
    storage.append_message(message)

    return message_id


def load_conversation_messages(
    spec_dir: Path,
    session_id: str,
) -> list[StoredMessage]:
    """
    Load all messages for a conversation session.

    Args:
        spec_dir: Path to spec directory
        session_id: Session ID

    Returns:
        List of messages
    """
    conversations_dir = get_conversations_dir(spec_dir)
    storage = SessionStorage(str(conversations_dir / f"{session_id}.jsonl"))
    return storage.load_messages_resilient()


def get_conversation_header(
    spec_dir: Path,
    session_id: str,
) -> SessionHeader | None:
    """
    Get header for a conversation session (fast - doesn't load messages).

    Args:
        spec_dir: Path to spec directory
        session_id: Session ID

    Returns:
        SessionHeader or None if not found
    """
    conversations_dir = get_conversations_dir(spec_dir)
    storage = SessionStorage(str(conversations_dir / f"{session_id}.jsonl"))
    return storage.load_header()


def update_conversation_header(
    spec_dir: Path,
    session_id: str,
    **updates: Any,
) -> None:
    """
    Update conversation session header fields.

    Args:
        spec_dir: Path to spec directory
        session_id: Session ID
        **updates: Fields to update (name, todo_state, flagged, etc.)
    """
    conversations_dir = get_conversations_dir(spec_dir)
    storage = SessionStorage(str(conversations_dir / f"{session_id}.jsonl"))

    header = storage.load_header()
    if header is None:
        logger.warning(f"Cannot update header: session {session_id} not found")
        return

    # Apply updates
    for key, value in updates.items():
        if hasattr(header, key):
            setattr(header, key, value)

    storage.update_header(header)
