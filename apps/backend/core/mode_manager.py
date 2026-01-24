"""
Permission Mode Management

This module provides per-session permission mode management with support for
user-controlled autonomy levels (Explore/Ask/Execute).

Inspired by Craft Agents OSS mode-manager.ts and mode-types.ts
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, Set, Callable, Optional, List, Any
import logging

logger = logging.getLogger(__name__)


class PermissionMode(Enum):
    """
    Permission modes controlling agent autonomy levels.

    SAFE (Explore): Read-only operations, blocks writes, never prompts
    ASK: Prompts before making edits (default)
    ALLOW_ALL (Execute): Automatic execution, no prompts
    """
    SAFE = "safe"
    ASK = "ask"
    ALLOW_ALL = "allow-all"


# Order for mode cycling (SHIFT+TAB)
PERMISSION_MODE_ORDER = [
    PermissionMode.SAFE,
    PermissionMode.ASK,
    PermissionMode.ALLOW_ALL
]


# Mode configuration with display info
PERMISSION_MODE_CONFIG = {
    PermissionMode.SAFE: {
        "display_name": "Explore",
        "description": "Read-only exploration. Blocks writes, never prompts.",
        "shortcut_hint": "SHIFT+TAB",
        "color": "green",
        "icon": "eye",
    },
    PermissionMode.ASK: {
        "display_name": "Ask to Edit",
        "description": "Prompts before making edits.",
        "shortcut_hint": "SHIFT+TAB",
        "color": "amber",
        "icon": "edit",
    },
    PermissionMode.ALLOW_ALL: {
        "display_name": "Execute",
        "description": "Automatic execution, no prompts.",
        "shortcut_hint": "SHIFT+TAB",
        "color": "violet",
        "icon": "zap",
    },
}


@dataclass
class ModeState:
    """
    Per-session mode state.

    Attributes:
        session_id: Unique identifier for the session
        permission_mode: Current permission mode
        on_state_change: Optional callback when state changes
        metadata: Optional additional state data
    """
    session_id: str
    permission_mode: PermissionMode = PermissionMode.ASK
    on_state_change: Optional[Callable[['ModeState'], None]] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


class ModeManager:
    """
    Per-session permission mode state manager.

    Key design principles:
    - NO GLOBAL STATE: Each session has isolated state
    - Dual notification: callbacks (for agent sync) + subscribers (for React)
    - Memory leak prevention via cleanup_session()

    Usage:
        manager = ModeManager()

        # Get/set mode for a session
        state = manager.get_state("session-123")
        manager.set_permission_mode("session-123", PermissionMode.SAFE)

        # Cycle through modes (for SHIFT+TAB)
        new_mode = manager.cycle_permission_mode("session-123")

        # Subscribe to changes
        unsubscribe = manager.subscribe("session-123", on_change)

        # Cleanup when session ends
        manager.cleanup_session("session-123")
    """

    def __init__(self):
        self._states: Dict[str, ModeState] = {}
        self._callbacks: Dict[str, Callable[[ModeState], None]] = {}
        self._subscribers: Dict[str, Set[Callable[[], None]]] = {}

    def get_state(self, session_id: str) -> ModeState:
        """
        Get the mode state for a session, creating if needed.

        Args:
            session_id: The session identifier

        Returns:
            ModeState for the session
        """
        if session_id not in self._states:
            self._states[session_id] = ModeState(
                session_id=session_id,
                permission_mode=PermissionMode.ASK  # Default
            )
            logger.debug(f"Created new mode state for session {session_id}")
        return self._states[session_id]

    def get_permission_mode(self, session_id: str) -> PermissionMode:
        """
        Get the current permission mode for a session.

        Args:
            session_id: The session identifier

        Returns:
            Current PermissionMode
        """
        return self.get_state(session_id).permission_mode

    def set_permission_mode(self, session_id: str, mode: PermissionMode) -> None:
        """
        Set the permission mode for a session.

        Args:
            session_id: The session identifier
            mode: The new permission mode
        """
        state = self.get_state(session_id)
        old_mode = state.permission_mode
        state.permission_mode = mode

        if old_mode != mode:
            logger.info(
                f"Session {session_id} mode changed: "
                f"{old_mode.value} -> {mode.value}"
            )
            self._notify_change(session_id, state)

    def cycle_permission_mode(
        self,
        session_id: str,
        enabled_modes: Optional[List[PermissionMode]] = None
    ) -> PermissionMode:
        """
        Cycle to the next permission mode (for SHIFT+TAB shortcut).

        Args:
            session_id: The session identifier
            enabled_modes: Optional subset of modes to cycle through

        Returns:
            The new permission mode
        """
        modes = enabled_modes if enabled_modes and len(enabled_modes) >= 2 else PERMISSION_MODE_ORDER
        current = self.get_state(session_id).permission_mode

        try:
            current_idx = modes.index(current)
        except ValueError:
            # Current mode not in list, start from beginning
            current_idx = -1

        next_idx = (current_idx + 1) % len(modes)
        next_mode = modes[next_idx]

        self.set_permission_mode(session_id, next_mode)
        return next_mode

    def register_callback(
        self,
        session_id: str,
        callback: Callable[[ModeState], None]
    ) -> Callable[[], None]:
        """
        Register a callback for state changes (agent sync).

        Args:
            session_id: The session identifier
            callback: Function to call with new state

        Returns:
            Unregister function
        """
        self._callbacks[session_id] = callback

        def unregister():
            if session_id in self._callbacks:
                del self._callbacks[session_id]

        return unregister

    def subscribe(
        self,
        session_id: str,
        subscriber: Callable[[], None]
    ) -> Callable[[], None]:
        """
        Subscribe to state changes (React/UI).

        Args:
            session_id: The session identifier
            subscriber: Function to call on change (no args)

        Returns:
            Unsubscribe function
        """
        if session_id not in self._subscribers:
            self._subscribers[session_id] = set()

        self._subscribers[session_id].add(subscriber)

        def unsubscribe():
            if session_id in self._subscribers:
                self._subscribers[session_id].discard(subscriber)

        return unsubscribe

    def _notify_change(self, session_id: str, state: ModeState) -> None:
        """Notify callbacks and subscribers of state change."""
        # Notify state callback (with state arg)
        if session_id in self._callbacks:
            try:
                self._callbacks[session_id](state)
            except Exception as e:
                logger.error(f"Error in mode callback for {session_id}: {e}")

        # Notify subscribers (no args)
        for subscriber in self._subscribers.get(session_id, set()).copy():
            try:
                subscriber()
            except Exception as e:
                logger.error(f"Error in mode subscriber for {session_id}: {e}")

    def cleanup_session(self, session_id: str) -> None:
        """
        Clean up all state for a session to prevent memory leaks.

        Should be called when a session ends.

        Args:
            session_id: The session identifier
        """
        self._states.pop(session_id, None)
        self._callbacks.pop(session_id, None)
        self._subscribers.pop(session_id, None)
        logger.debug(f"Cleaned up mode state for session {session_id}")

    def get_all_sessions(self) -> List[str]:
        """Get list of all active session IDs."""
        return list(self._states.keys())

    def get_mode_config(self, mode: PermissionMode) -> dict:
        """Get display configuration for a mode."""
        return PERMISSION_MODE_CONFIG.get(mode, {})


def is_write_operation(tool_name: str) -> bool:
    """
    Check if a tool performs write operations.

    Used by SAFE mode to block write operations.

    Args:
        tool_name: Name of the tool

    Returns:
        True if tool performs writes
    """
    write_tools = {
        # File operations
        'write_file', 'edit_file', 'delete_file', 'create_file',
        'write', 'edit', 'delete', 'create',
        'file_write', 'file_edit', 'file_delete', 'file_create',

        # Bash operations that modify
        'bash', 'shell', 'execute', 'run_command',

        # Git operations that modify
        'git_commit', 'git_push', 'git_checkout',

        # MCP tools that modify
        'mcp__filesystem__write_file',
        'mcp__filesystem__create_directory',
        'mcp__filesystem__delete_file',
    }

    tool_lower = tool_name.lower()
    return any(write_tool in tool_lower for write_tool in write_tools)


def should_prompt_for_tool(
    tool_name: str,
    mode: PermissionMode,
    is_destructive: bool = False
) -> bool:
    """
    Determine if a tool should prompt for user confirmation.

    Args:
        tool_name: Name of the tool
        mode: Current permission mode
        is_destructive: Whether the operation is destructive

    Returns:
        True if should prompt, False if auto-approve or block
    """
    if mode == PermissionMode.ALLOW_ALL:
        return False  # Never prompt

    if mode == PermissionMode.SAFE:
        return False  # Block (handled separately)

    # ASK mode: prompt for writes and destructive operations
    if mode == PermissionMode.ASK:
        return is_write_operation(tool_name) or is_destructive

    return False


def should_block_tool(tool_name: str, mode: PermissionMode) -> bool:
    """
    Determine if a tool should be blocked entirely.

    Args:
        tool_name: Name of the tool
        mode: Current permission mode

    Returns:
        True if should block
    """
    if mode == PermissionMode.SAFE:
        return is_write_operation(tool_name)
    return False


# Singleton instance for convenience
mode_manager = ModeManager()


# Convenience functions using default manager
def get_mode(session_id: str) -> PermissionMode:
    """Get permission mode for session using default manager."""
    return mode_manager.get_permission_mode(session_id)


def set_mode(session_id: str, mode: PermissionMode) -> None:
    """Set permission mode for session using default manager."""
    mode_manager.set_permission_mode(session_id, mode)


def cycle_mode(session_id: str) -> PermissionMode:
    """Cycle permission mode for session using default manager."""
    return mode_manager.cycle_permission_mode(session_id)
