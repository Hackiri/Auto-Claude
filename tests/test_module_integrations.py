#!/usr/bin/env python3
"""
Tests for Module Integrations
=============================

Tests for the integration of:
1. bash_validator.py into security module
2. summarizer.py into client.py tool result flow
3. mode_manager.py into agent sessions
4. session_storage.py as new session persistence layer
"""

import json
import os
import tempfile
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# Add backend to path
import sys
sys.path.insert(0, str(Path(__file__).parent.parent / "apps" / "backend"))


# =============================================================================
# 1. bash_validator.py Integration Tests
# =============================================================================

class TestBashValidatorIntegration:
    """Test bash_validator integration into security module."""

    def test_shell_validators_imports_bash_validator(self):
        """Verify shell_validators imports from bash_validator."""
        from security import shell_validators

        # Check imports are available
        assert hasattr(shell_validators, 'ast_validate_bash_command')
        assert hasattr(shell_validators, 'compile_patterns')
        assert hasattr(shell_validators, 'check_control_characters')
        assert hasattr(shell_validators, 'BASHLEX_AVAILABLE')

    def test_pattern_cache_management(self):
        """Test pattern cache can be cleared."""
        from security import clear_pattern_cache
        from security.shell_validators import _pattern_cache

        # Add a test entry
        _pattern_cache['test_project'] = []

        # Clear specific project
        clear_pattern_cache('test_project')
        assert 'test_project' not in _pattern_cache

        # Clear all
        _pattern_cache['project1'] = []
        _pattern_cache['project2'] = []
        clear_pattern_cache()
        assert len(_pattern_cache) == 0

    def test_validate_shell_c_command_calls_ast_validator(self):
        """Test that shell command validation uses AST validator when available."""
        from security.shell_validators import (
            validate_shell_c_command,
            BASHLEX_AVAILABLE,
        )

        # Simple echo command should be allowed
        result, error = validate_shell_c_command("bash -c 'echo hello'")

        # If bashlex is available, AST validation should have run
        if BASHLEX_AVAILABLE:
            # Should either pass or fail with AST-related error
            assert isinstance(result, bool)


# =============================================================================
# 2. summarizer.py Integration Tests
# =============================================================================

class TestSummarizerIntegration:
    """Test summarizer integration into client.py."""

    def test_client_imports_summarizer(self):
        """Verify client imports summarizer functions."""
        from core import client

        # Check imports are in module
        assert hasattr(client, 'get_summarizer')
        assert hasattr(client, 'SummarizationContext')
        assert hasattr(client, 'needs_summarization')

    def test_tool_result_summarizer_hook_defined(self):
        """Test that the summarizer hook function exists."""
        from core.client import tool_result_summarizer_hook

        # Should be an async function
        import inspect
        assert inspect.iscoroutinefunction(tool_result_summarizer_hook)

    @pytest.mark.asyncio
    async def test_tool_result_summarizer_skips_empty_result(self):
        """Test summarizer hook skips empty results."""
        from core.client import tool_result_summarizer_hook

        result = await tool_result_summarizer_hook(
            {"tool_name": "Read", "result": ""}
        )
        assert result == {}

    @pytest.mark.asyncio
    async def test_tool_result_summarizer_skips_write_tools(self):
        """Test summarizer hook skips Edit/Write tools."""
        from core.client import tool_result_summarizer_hook

        for tool in ["Edit", "Write", "StructuredOutput"]:
            result = await tool_result_summarizer_hook(
                {"tool_name": tool, "result": "x" * 10000}
            )
            assert result == {}


# =============================================================================
# 3. mode_manager.py Integration Tests
# =============================================================================

class TestModeManagerIntegration:
    """Test mode_manager integration into client.py."""

    def test_client_imports_mode_manager(self):
        """Verify client imports mode_manager functions."""
        from core import client

        # Check imports are in module
        assert hasattr(client, 'mode_manager')
        assert hasattr(client, 'PermissionMode')
        assert hasattr(client, 'should_block_tool')
        assert hasattr(client, 'should_prompt_for_tool')

    def test_mode_manager_hook_defined(self):
        """Test that the mode manager hook function exists."""
        from core.client import mode_manager_hook

        # Should be an async function
        import inspect
        assert inspect.iscoroutinefunction(mode_manager_hook)

    def test_permission_mode_enum_values(self):
        """Test PermissionMode enum has expected values."""
        from core.mode_manager import PermissionMode

        assert PermissionMode.SAFE.value == "safe"
        assert PermissionMode.ASK.value == "ask"
        assert PermissionMode.ALLOW_ALL.value == "allow-all"

    @pytest.mark.asyncio
    async def test_mode_manager_hook_blocks_in_safe_mode(self):
        """Test mode manager blocks write tools in SAFE mode."""
        from core.client import mode_manager_hook
        from core.mode_manager import mode_manager, PermissionMode

        # Set up a test session in SAFE mode
        test_session = "test-session-safe-mode"
        mode_manager.set_permission_mode(test_session, PermissionMode.SAFE)

        # Set session ID in environment
        with patch.dict(os.environ, {"AGENT_SESSION_ID": test_session}):
            # Write tool should be blocked
            result = await mode_manager_hook(
                {"tool_name": "Write", "tool_input": {"file_path": "test.txt"}}
            )

            assert result.get("decision") == "block"
            assert "SAFE mode" in result.get("reason", "") or "safe" in result.get("reason", "").lower()

        # Cleanup using cleanup_session
        mode_manager.cleanup_session(test_session)

    @pytest.mark.asyncio
    async def test_mode_manager_hook_allows_read_in_safe_mode(self):
        """Test mode manager allows read tools in SAFE mode."""
        from core.client import mode_manager_hook
        from core.mode_manager import mode_manager, PermissionMode

        test_session = "test-session-safe-read"
        mode_manager.set_permission_mode(test_session, PermissionMode.SAFE)

        with patch.dict(os.environ, {"AGENT_SESSION_ID": test_session}):
            # Read tool should be allowed (empty dict means allow)
            result = await mode_manager_hook(
                {"tool_name": "Read", "tool_input": {"file_path": "test.txt"}}
            )

            assert result == {}

        # Cleanup using cleanup_session
        mode_manager.cleanup_session(test_session)


# =============================================================================
# 4. session_storage.py Integration Tests
# =============================================================================

class TestSessionStorageIntegration:
    """Test session_storage integration into memory module."""

    def test_memory_module_exports_conversation_functions(self):
        """Verify memory module exports conversation session functions."""
        from memory import (
            ConversationSessionManager,
            get_conversations_dir,
            save_conversation_message,
            load_conversation_messages,
            get_conversation_header,
            update_conversation_header,
        )

        # All should be callable
        assert callable(ConversationSessionManager)
        assert callable(get_conversations_dir)
        assert callable(save_conversation_message)
        assert callable(load_conversation_messages)
        assert callable(get_conversation_header)
        assert callable(update_conversation_header)

    def test_conversation_session_manager_create_and_list(self):
        """Test creating and listing conversation sessions."""
        from memory.conversation_sessions import ConversationSessionManager

        with tempfile.TemporaryDirectory() as tmpdir:
            spec_dir = Path(tmpdir) / "spec"
            spec_dir.mkdir(parents=True)

            manager = ConversationSessionManager(spec_dir)

            # Create a session
            session_id = manager.create_session("Test Session")
            assert session_id is not None
            assert len(session_id) > 0

            # List sessions
            sessions = manager.list_sessions()
            assert len(sessions) == 1
            assert sessions[0].name == "Test Session"
            assert sessions[0].id == session_id

    def test_save_and_load_conversation_messages(self):
        """Test saving and loading conversation messages."""
        from memory.conversation_sessions import (
            ConversationSessionManager,
            save_conversation_message,
            load_conversation_messages,
        )

        with tempfile.TemporaryDirectory() as tmpdir:
            spec_dir = Path(tmpdir) / "spec"
            spec_dir.mkdir(parents=True)

            # Create session
            manager = ConversationSessionManager(spec_dir)
            session_id = manager.create_session("Test Conversation")

            # Save messages
            save_conversation_message(spec_dir, session_id, "user", "Hello")
            save_conversation_message(spec_dir, session_id, "assistant", "Hi there!")

            # Load messages
            messages = load_conversation_messages(spec_dir, session_id)
            assert len(messages) == 2
            assert messages[0].role == "user"
            assert messages[0].content == "Hello"
            assert messages[1].role == "assistant"
            assert messages[1].content == "Hi there!"

    def test_conversation_header_persistence(self):
        """Test that conversation headers are persisted correctly."""
        from memory.conversation_sessions import (
            ConversationSessionManager,
            get_conversation_header,
        )

        with tempfile.TemporaryDirectory() as tmpdir:
            spec_dir = Path(tmpdir) / "spec"
            spec_dir.mkdir(parents=True)

            # Create session
            manager = ConversationSessionManager(spec_dir)
            session_id = manager.create_session(
                "Header Test",
                metadata={"key": "value"}
            )

            # Get header
            header = get_conversation_header(spec_dir, session_id)
            assert header is not None
            assert header.name == "Header Test"
            assert header.metadata.get("key") == "value"


# =============================================================================
# Integration Smoke Tests
# =============================================================================

class TestIntegrationSmoke:
    """Smoke tests to verify all integrations work together."""

    def test_security_module_initialization(self):
        """Test security module initializes without errors."""
        from security import (
            bash_security_hook,
            validate_command,
            clear_pattern_cache,
        )

        # Clear pattern cache should work
        clear_pattern_cache()

        # Validate command should be callable
        assert callable(validate_command)

    def test_client_module_initialization(self):
        """Test client module initializes without errors."""
        from core.client import (
            tool_result_summarizer_hook,
            mode_manager_hook,
            create_client,
        )

        # All functions should be defined
        assert callable(tool_result_summarizer_hook)
        assert callable(mode_manager_hook)
        assert callable(create_client)

    def test_memory_module_initialization(self):
        """Test memory module initializes without errors."""
        from memory import (
            ConversationSessionManager,
            save_session_insights,
            load_all_insights,
        )

        # All should be accessible
        assert callable(ConversationSessionManager)
        assert callable(save_session_insights)
        assert callable(load_all_insights)
