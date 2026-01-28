"""
JSONL Session Persistence

This module provides JSONL-based session persistence with atomic writes,
pre-computed headers for fast listing, and resilient parsing.

Inspired by Craft Agents OSS session storage patterns.
"""

import json
import logging
import os
import tempfile
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any

logger = logging.getLogger(__name__)


class TodoState(Enum):
    """Session workflow states for inbox management."""

    TODO = "todo"
    IN_PROGRESS = "in-progress"
    NEEDS_REVIEW = "needs-review"
    DONE = "done"
    CANCELLED = "cancelled"


@dataclass
class SessionHeader:
    """
    Line 1 of JSONL - fast metadata access without parsing all messages.

    This enables fast session list rendering by reading only the first line.

    Attributes:
        id: Unique session identifier
        name: User-friendly session name
        todo_state: Current workflow state
        message_count: Number of messages (pre-computed)
        preview: Pre-computed preview text for list display
        has_unread: Whether session has unread messages
        flagged: Whether session is flagged/starred
        created_at: Session creation timestamp
        updated_at: Last update timestamp
        last_read_message_id: ID of last read message
        metadata: Optional additional metadata
    """

    id: str
    name: str
    todo_state: TodoState = TodoState.TODO
    message_count: int = 0
    preview: str = ""
    has_unread: bool = False
    flagged: bool = False
    created_at: str = ""
    updated_at: str = ""
    last_read_message_id: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict:
        """Convert to dict for JSON serialization."""
        d = asdict(self)
        d["todo_state"] = self.todo_state.value
        return d

    @classmethod
    def from_dict(cls, data: dict) -> "SessionHeader":
        """Create from dict, handling enum conversion."""
        if "todo_state" in data:
            data = data.copy()
            data["todo_state"] = TodoState(data["todo_state"])
        return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})


@dataclass
class StoredMessage:
    """
    Lines 2+ of JSONL - one message per line.

    Attributes:
        id: Unique message identifier
        role: Message role (user, assistant, system)
        content: Message content
        timestamp: ISO timestamp
        tool_use: Optional tool use data
        metadata: Optional additional data
    """

    id: str
    role: str
    content: str
    timestamp: str
    tool_use: dict[str, Any] | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict:
        """Convert to dict for JSON serialization."""
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> "StoredMessage":
        """Create from dict."""
        return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})


def generate_id() -> str:
    """Generate a unique ID for sessions/messages."""
    return str(uuid.uuid4())


def now_iso() -> str:
    """Get current time as ISO string."""
    return datetime.utcnow().isoformat() + "Z"


def compute_preview(messages: list[StoredMessage], max_length: int = 100) -> str:
    """
    Compute preview text from messages.

    Uses the last assistant message or last user message.

    Args:
        messages: List of messages
        max_length: Maximum preview length

    Returns:
        Preview string
    """
    # Find last assistant or user message
    for msg in reversed(messages):
        if msg.role in ("assistant", "user"):
            content = msg.content
            if len(content) > max_length:
                return content[: max_length - 3] + "..."
            return content
    return ""


class SessionStorage:
    """
    JSONL-based session persistence with atomic writes.

    Key features:
    - Atomic writes via temp file + rename (no corruption on crash)
    - Pre-computed header for fast list rendering
    - Resilient parsing that skips corrupted lines
    - Append-friendly for message streaming

    Usage:
        storage = SessionStorage("/path/to/session.jsonl")

        # Save session
        storage.save_atomic(header, messages)

        # Load just header (fast)
        header = storage.load_header()

        # Load all messages
        messages = storage.load_messages_resilient()

        # Append single message (fast)
        storage.append_message(message)
    """

    def __init__(self, session_path: str):
        """
        Initialize storage for a session file.

        Args:
            session_path: Path to the JSONL file
        """
        self.path = session_path

    def exists(self) -> bool:
        """Check if session file exists."""
        return os.path.exists(self.path)

    def save_atomic(self, header: SessionHeader, messages: list[StoredMessage]) -> None:
        """
        Atomic write: temp file + rename prevents corruption.

        Args:
            header: Session header with metadata
            messages: List of messages to save
        """
        # Ensure directory exists
        dir_path = os.path.dirname(self.path)
        if dir_path:
            os.makedirs(dir_path, exist_ok=True)

        # Update header with computed values
        header.message_count = len(messages)
        header.preview = compute_preview(messages)
        header.updated_at = now_iso()
        if not header.created_at:
            header.created_at = header.updated_at

        # Write to temp file first
        try:
            with tempfile.NamedTemporaryFile(
                mode="w", dir=dir_path or ".", delete=False, suffix=".jsonl.tmp"
            ) as f:
                # Line 1: Header with pre-computed metadata
                f.write(json.dumps(header.to_dict()) + "\n")

                # Lines 2+: Messages
                for msg in messages:
                    f.write(json.dumps(msg.to_dict()) + "\n")

                temp_path = f.name

            # Atomic rename
            os.replace(temp_path, self.path)
            logger.debug(f"Saved session {header.id} with {len(messages)} messages")

        except Exception as e:
            # Clean up temp file on error
            if "temp_path" in locals() and os.path.exists(temp_path):
                try:
                    os.remove(temp_path)
                except Exception:
                    pass
            raise e

    def load_header(self) -> SessionHeader | None:
        """
        Fast header read without parsing all messages.

        Returns:
            SessionHeader or None if file doesn't exist/is corrupt
        """
        try:
            with open(self.path, encoding="utf-8") as f:
                line = f.readline()
                if not line:
                    return None
                return SessionHeader.from_dict(json.loads(line))
        except FileNotFoundError:
            return None
        except json.JSONDecodeError as e:
            logger.warning(f"Corrupt header in {self.path}: {e}")
            return None
        except Exception as e:
            logger.error(f"Error loading header from {self.path}: {e}")
            return None

    def load_messages_resilient(self) -> list[StoredMessage]:
        """
        Load all messages, skipping corrupted lines.

        Returns:
            List of successfully parsed messages
        """
        messages = []
        try:
            with open(self.path, encoding="utf-8") as f:
                # Skip header
                f.readline()

                for line_num, line in enumerate(f, start=2):
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        messages.append(StoredMessage.from_dict(json.loads(line)))
                    except json.JSONDecodeError as e:
                        logger.warning(
                            f"Corrupt message at line {line_num} in {self.path}: {e}"
                        )
                        continue
                    except Exception as e:
                        logger.warning(f"Error parsing message at line {line_num}: {e}")
                        continue

        except FileNotFoundError:
            pass
        except Exception as e:
            logger.error(f"Error loading messages from {self.path}: {e}")

        return messages

    def load_full(self) -> tuple[SessionHeader | None, list[StoredMessage]]:
        """
        Load both header and messages.

        Returns:
            Tuple of (header, messages)
        """
        return self.load_header(), self.load_messages_resilient()

    def append_message(self, message: StoredMessage) -> None:
        """
        Append a single message (fast, no full rewrite).

        Note: This doesn't update the header. Use save_atomic() periodically
        to sync the header.

        Args:
            message: Message to append
        """
        try:
            with open(self.path, "a", encoding="utf-8") as f:
                f.write(json.dumps(message.to_dict()) + "\n")
        except Exception as e:
            logger.error(f"Error appending message to {self.path}: {e}")
            raise

    def update_header(self, header: SessionHeader) -> None:
        """
        Update just the header (requires full rewrite).

        Args:
            header: New header
        """
        messages = self.load_messages_resilient()
        self.save_atomic(header, messages)


class SessionManager:
    """
    Manager for multiple sessions in a directory.

    Usage:
        manager = SessionManager("/path/to/sessions/")

        # List all sessions (fast - reads only headers)
        sessions = manager.list_sessions()

        # Get or create session
        storage = manager.get_session("session-id")

        # Create new session
        session_id = manager.create_session("My Session")
    """

    def __init__(self, sessions_dir: str):
        """
        Initialize session manager.

        Args:
            sessions_dir: Directory containing session files
        """
        self.sessions_dir = sessions_dir
        os.makedirs(sessions_dir, exist_ok=True)

    def _session_path(self, session_id: str) -> str:
        """Get path for a session file."""
        return os.path.join(self.sessions_dir, f"{session_id}.jsonl")

    def get_session(self, session_id: str) -> SessionStorage:
        """
        Get storage for a session.

        Args:
            session_id: Session identifier

        Returns:
            SessionStorage instance
        """
        return SessionStorage(self._session_path(session_id))

    def create_session(self, name: str, session_id: str | None = None) -> str:
        """
        Create a new session.

        Args:
            name: Session name
            session_id: Optional ID (auto-generated if not provided)

        Returns:
            Session ID
        """
        if session_id is None:
            session_id = generate_id()

        header = SessionHeader(
            id=session_id, name=name, created_at=now_iso(), updated_at=now_iso()
        )

        storage = self.get_session(session_id)
        storage.save_atomic(header, [])

        logger.info(f"Created session {session_id}: {name}")
        return session_id

    def list_sessions(
        self, filter_state: TodoState | None = None
    ) -> list[SessionHeader]:
        """
        List all sessions (reads only headers for speed).

        Args:
            filter_state: Optional state to filter by

        Returns:
            List of session headers
        """
        sessions = []

        try:
            for filename in os.listdir(self.sessions_dir):
                if not filename.endswith(".jsonl"):
                    continue

                storage = SessionStorage(os.path.join(self.sessions_dir, filename))
                header = storage.load_header()

                if header is None:
                    continue

                if filter_state is not None and header.todo_state != filter_state:
                    continue

                sessions.append(header)

        except Exception as e:
            logger.error(f"Error listing sessions: {e}")

        # Sort by updated_at descending
        sessions.sort(key=lambda s: s.updated_at, reverse=True)
        return sessions

    def delete_session(self, session_id: str) -> bool:
        """
        Delete a session file.

        Args:
            session_id: Session to delete

        Returns:
            True if deleted, False if not found
        """
        path = self._session_path(session_id)
        try:
            os.remove(path)
            logger.info(f"Deleted session {session_id}")
            return True
        except FileNotFoundError:
            return False
        except Exception as e:
            logger.error(f"Error deleting session {session_id}: {e}")
            raise

    def archive_session(self, session_id: str) -> None:
        """
        Mark a session as done/archived.

        Args:
            session_id: Session to archive
        """
        storage = self.get_session(session_id)
        header = storage.load_header()
        if header:
            header.todo_state = TodoState.DONE
            storage.update_header(header)
            logger.info(f"Archived session {session_id}")
