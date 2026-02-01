"""
Decision Audit Trail Tests

Tests for the decision_audit module including models, storage, logger, and extractor.
"""

import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

import pytest

# Add backend to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'apps', 'backend'))

from decision_audit.models import (
    ConfidenceLevel,
    DecisionContext,
    DecisionEntry,
    DecisionFilter,
    DecisionType,
)
from decision_audit.storage import DecisionStorage, get_decision_count, load_decisions
from decision_audit.logger import DecisionAuditLogger, emit_decision_marker, get_decision_logger


# ============================================================================
# Unit Tests for DecisionType Enum
# ============================================================================

class TestDecisionType:
    """Unit tests for the DecisionType enum."""

    def test_all_decision_types_exist(self):
        """All expected decision types should be defined."""
        expected = [
            "approach_chosen",
            "alternative_rejected",
            "context_used",
            "pattern_followed",
            "file_selected",
            "tool_selected",
            "error_recovery",
        ]
        for type_val in expected:
            assert type_val in [t.value for t in DecisionType]

    def test_decision_type_values(self):
        """Decision types should have correct string values."""
        assert DecisionType.APPROACH_CHOSEN.value == "approach_chosen"
        assert DecisionType.ALTERNATIVE_REJECTED.value == "alternative_rejected"
        assert DecisionType.CONTEXT_USED.value == "context_used"
        assert DecisionType.PATTERN_FOLLOWED.value == "pattern_followed"
        assert DecisionType.FILE_SELECTED.value == "file_selected"
        assert DecisionType.TOOL_SELECTED.value == "tool_selected"
        assert DecisionType.ERROR_RECOVERY.value == "error_recovery"

    def test_decision_type_is_string_enum(self):
        """DecisionType should be a string enum for JSON serialization."""
        assert isinstance(DecisionType.APPROACH_CHOSEN.value, str)
        # String comparison should work
        assert DecisionType.APPROACH_CHOSEN == "approach_chosen"


# ============================================================================
# Unit Tests for ConfidenceLevel Enum
# ============================================================================

class TestConfidenceLevel:
    """Unit tests for the ConfidenceLevel enum."""

    def test_confidence_levels_exist(self):
        """All expected confidence levels should be defined."""
        expected = ["high", "medium", "low"]
        for level in expected:
            assert level in [c.value for c in ConfidenceLevel]

    def test_confidence_level_values(self):
        """Confidence levels should have correct string values."""
        assert ConfidenceLevel.HIGH.value == "high"
        assert ConfidenceLevel.MEDIUM.value == "medium"
        assert ConfidenceLevel.LOW.value == "low"


# ============================================================================
# Unit Tests for DecisionContext Dataclass
# ============================================================================

class TestDecisionContext:
    """Unit tests for the DecisionContext dataclass."""

    def test_create_decision_context(self):
        """Should create a DecisionContext with required fields."""
        ctx = DecisionContext(
            source="file_read",
            content="path/to/file.py"
        )
        assert ctx.source == "file_read"
        assert ctx.content == "path/to/file.py"
        assert ctx.timestamp is None
        assert ctx.metadata == {}

    def test_create_context_with_all_fields(self):
        """Should create a DecisionContext with all fields."""
        ctx = DecisionContext(
            source="graphiti_query",
            content="Search for auth patterns",
            timestamp="2026-01-26T12:00:00Z",
            metadata={"query_type": "semantic", "results": 5}
        )
        assert ctx.source == "graphiti_query"
        assert ctx.content == "Search for auth patterns"
        assert ctx.timestamp == "2026-01-26T12:00:00Z"
        assert ctx.metadata["query_type"] == "semantic"

    def test_to_dict(self):
        """to_dict() should convert context to dictionary."""
        ctx = DecisionContext(
            source="file_read",
            content="test.py",
            timestamp="2026-01-26T12:00:00Z",
            metadata={"line": 10}
        )
        result = ctx.to_dict()
        assert result["source"] == "file_read"
        assert result["content"] == "test.py"
        assert result["timestamp"] == "2026-01-26T12:00:00Z"
        assert result["metadata"]["line"] == 10

    def test_to_dict_excludes_none_timestamp(self):
        """to_dict() should exclude None timestamp."""
        ctx = DecisionContext(source="test", content="data")
        result = ctx.to_dict()
        assert "timestamp" not in result

    def test_from_dict(self):
        """from_dict() should create context from dictionary."""
        data = {
            "source": "user_input",
            "content": "User said to use hooks",
            "timestamp": "2026-01-26T13:00:00Z",
            "metadata": {"confidence": "high"}
        }
        ctx = DecisionContext.from_dict(data)
        assert ctx.source == "user_input"
        assert ctx.content == "User said to use hooks"
        assert ctx.timestamp == "2026-01-26T13:00:00Z"
        assert ctx.metadata["confidence"] == "high"

    def test_from_dict_with_missing_fields(self):
        """from_dict() should handle missing optional fields."""
        data = {"source": "test", "content": "data"}
        ctx = DecisionContext.from_dict(data)
        assert ctx.timestamp is None
        assert ctx.metadata == {}


# ============================================================================
# Unit Tests for DecisionEntry Dataclass
# ============================================================================

class TestDecisionEntry:
    """Unit tests for the DecisionEntry dataclass."""

    def test_create_decision_entry(self):
        """Should create a DecisionEntry with required fields."""
        entry = DecisionEntry(
            id="dec-001",
            timestamp="2026-01-26T12:00:00Z",
            decision_type=DecisionType.APPROACH_CHOSEN.value,
            description="Use React hooks",
            reasoning="Follows existing patterns"
        )
        assert entry.id == "dec-001"
        assert entry.decision_type == "approach_chosen"
        assert entry.description == "Use React hooks"
        assert entry.reasoning == "Follows existing patterns"
        assert entry.alternatives_considered == []
        assert entry.context_used == []
        assert entry.confidence_level == "medium"
        assert entry.annotation is None

    def test_create_entry_with_all_fields(self):
        """Should create a DecisionEntry with all fields."""
        ctx = DecisionContext(source="file_read", content="test.py")
        entry = DecisionEntry(
            id="dec-002",
            timestamp="2026-01-26T12:00:00Z",
            decision_type=DecisionType.TOOL_SELECTED.value,
            description="Selected Bash for command execution",
            reasoning="Need to run npm install",
            alternatives_considered=["Read tool", "Python subprocess"],
            context_used=[ctx],
            subtask_id="subtask-1-1",
            phase="coding",
            confidence_level=ConfidenceLevel.HIGH.value,
            annotation="good_pattern",
            annotation_note="This worked well"
        )
        assert entry.subtask_id == "subtask-1-1"
        assert entry.phase == "coding"
        assert len(entry.context_used) == 1
        assert entry.confidence_level == "high"
        assert entry.annotation == "good_pattern"

    def test_to_dict(self):
        """to_dict() should convert entry to dictionary."""
        ctx = DecisionContext(source="test", content="data")
        entry = DecisionEntry(
            id="dec-003",
            timestamp="2026-01-26T12:00:00Z",
            decision_type="approach_chosen",
            description="Test decision",
            reasoning="Test reasoning",
            alternatives_considered=["Option A", "Option B"],
            context_used=[ctx],
            subtask_id="subtask-1",
            phase="planning"
        )
        result = entry.to_dict()

        assert result["id"] == "dec-003"
        assert result["decision_type"] == "approach_chosen"
        assert len(result["alternatives_considered"]) == 2
        assert len(result["context_used"]) == 1
        assert result["context_used"][0]["source"] == "test"

    def test_from_dict(self):
        """from_dict() should create entry from dictionary."""
        data = {
            "id": "dec-004",
            "timestamp": "2026-01-26T14:00:00Z",
            "decision_type": "file_selected",
            "description": "Selected utils.py",
            "reasoning": "Contains helper functions",
            "alternatives_considered": ["helpers.py"],
            "context_used": [{"source": "glob", "content": "*.py"}],
            "subtask_id": "subtask-2",
            "phase": "coding",
            "confidence_level": "low",
            "annotation": "bad_pattern",
            "annotation_note": "Should have used helpers.py"
        }
        entry = DecisionEntry.from_dict(data)

        assert entry.id == "dec-004"
        assert entry.decision_type == "file_selected"
        assert len(entry.alternatives_considered) == 1
        assert len(entry.context_used) == 1
        assert entry.context_used[0].source == "glob"
        assert entry.annotation == "bad_pattern"

    def test_from_dict_with_defaults(self):
        """from_dict() should use defaults for missing fields."""
        data = {
            "id": "dec-005",
            "timestamp": "2026-01-26T15:00:00Z",
            "description": "Minimal entry",
            "reasoning": "Test"
        }
        entry = DecisionEntry.from_dict(data)

        assert entry.decision_type == "approach_chosen"  # Default
        assert entry.alternatives_considered == []
        assert entry.context_used == []
        assert entry.confidence_level == "medium"


# ============================================================================
# Unit Tests for DecisionFilter Dataclass
# ============================================================================

class TestDecisionFilter:
    """Unit tests for the DecisionFilter dataclass."""

    def test_create_empty_filter(self):
        """Should create a filter with no criteria."""
        f = DecisionFilter()
        assert f.decision_type is None
        assert f.subtask_id is None
        assert f.phase is None
        assert f.annotation is None
        assert f.since is None
        assert f.until is None

    def test_create_filter_with_criteria(self):
        """Should create a filter with specific criteria."""
        now = datetime.now(timezone.utc)
        f = DecisionFilter(
            decision_type="approach_chosen",
            subtask_id="subtask-1",
            phase="coding",
            annotation="good_pattern",
            since=now
        )
        assert f.decision_type == "approach_chosen"
        assert f.subtask_id == "subtask-1"
        assert f.phase == "coding"
        assert f.annotation == "good_pattern"
        assert f.since == now


# ============================================================================
# Unit Tests for DecisionStorage
# ============================================================================

class TestDecisionStorage:
    """Unit tests for the DecisionStorage class."""

    def test_create_storage(self, tmp_path):
        """Should create storage with empty decisions list."""
        storage = DecisionStorage(tmp_path)
        assert storage.spec_dir == tmp_path
        data = storage.get_data()
        assert data["decisions"] == []
        assert "spec_id" in data
        assert "created_at" in data

    def test_add_entry(self, tmp_path):
        """add_entry() should add and persist a decision."""
        storage = DecisionStorage(tmp_path)
        entry = DecisionEntry(
            id="dec-001",
            timestamp=datetime.now(timezone.utc).isoformat(),
            decision_type="approach_chosen",
            description="Test decision",
            reasoning="Test reasoning"
        )
        storage.add_entry(entry)

        # Verify in memory
        assert len(storage.get_all()) == 1

        # Verify persisted
        decisions_file = tmp_path / "decisions.json"
        assert decisions_file.exists()
        with open(decisions_file) as f:
            data = json.load(f)
        assert len(data["decisions"]) == 1
        assert data["decisions"][0]["id"] == "dec-001"

    def test_add_entries_batch(self, tmp_path):
        """add_entries() should add multiple decisions at once."""
        storage = DecisionStorage(tmp_path)
        entries = [
            DecisionEntry(
                id=f"dec-{i}",
                timestamp=datetime.now(timezone.utc).isoformat(),
                decision_type="approach_chosen",
                description=f"Decision {i}",
                reasoning=f"Reason {i}"
            )
            for i in range(3)
        ]
        storage.add_entries(entries)

        assert len(storage.get_all()) == 3

    def test_get_entry(self, tmp_path):
        """get_entry() should retrieve a specific decision by ID."""
        storage = DecisionStorage(tmp_path)
        entry = DecisionEntry(
            id="dec-unique",
            timestamp=datetime.now(timezone.utc).isoformat(),
            decision_type="tool_selected",
            description="Unique decision",
            reasoning="Unique reasoning"
        )
        storage.add_entry(entry)

        retrieved = storage.get_entry("dec-unique")
        assert retrieved is not None
        assert retrieved.id == "dec-unique"
        assert retrieved.description == "Unique decision"

        # Non-existent ID
        assert storage.get_entry("dec-nonexistent") is None

    def test_update_entry(self, tmp_path):
        """update_entry() should modify existing decision."""
        storage = DecisionStorage(tmp_path)
        entry = DecisionEntry(
            id="dec-update",
            timestamp=datetime.now(timezone.utc).isoformat(),
            decision_type="approach_chosen",
            description="Original description",
            reasoning="Original reasoning"
        )
        storage.add_entry(entry)

        # Update
        result = storage.update_entry("dec-update", {"description": "Updated description"})
        assert result is True

        # Verify update
        updated = storage.get_entry("dec-update")
        assert updated.description == "Updated description"

        # Non-existent ID
        assert storage.update_entry("dec-nonexistent", {"description": "x"}) is False

    def test_annotate(self, tmp_path):
        """annotate() should add annotation to decision."""
        storage = DecisionStorage(tmp_path)
        entry = DecisionEntry(
            id="dec-annotate",
            timestamp=datetime.now(timezone.utc).isoformat(),
            decision_type="approach_chosen",
            description="Decision to annotate",
            reasoning="Some reasoning"
        )
        storage.add_entry(entry)

        # Add annotation
        result = storage.annotate("dec-annotate", "good_pattern", "This worked well")
        assert result is True

        # Verify annotation
        annotated = storage.get_entry("dec-annotate")
        assert annotated.annotation == "good_pattern"
        assert annotated.annotation_note == "This worked well"

    def test_query_by_type(self, tmp_path):
        """query() should filter by decision type."""
        storage = DecisionStorage(tmp_path)
        storage.add_entries([
            DecisionEntry(
                id="dec-1",
                timestamp=datetime.now(timezone.utc).isoformat(),
                decision_type="approach_chosen",
                description="Approach 1",
                reasoning="R1"
            ),
            DecisionEntry(
                id="dec-2",
                timestamp=datetime.now(timezone.utc).isoformat(),
                decision_type="tool_selected",
                description="Tool 1",
                reasoning="R2"
            ),
            DecisionEntry(
                id="dec-3",
                timestamp=datetime.now(timezone.utc).isoformat(),
                decision_type="approach_chosen",
                description="Approach 2",
                reasoning="R3"
            ),
        ])

        approaches = storage.query(decision_type="approach_chosen")
        assert len(approaches) == 2
        assert all(d.decision_type == "approach_chosen" for d in approaches)

    def test_query_by_subtask(self, tmp_path):
        """query() should filter by subtask ID."""
        storage = DecisionStorage(tmp_path)
        storage.add_entries([
            DecisionEntry(
                id="dec-1",
                timestamp=datetime.now(timezone.utc).isoformat(),
                decision_type="approach_chosen",
                description="D1",
                reasoning="R1",
                subtask_id="subtask-1"
            ),
            DecisionEntry(
                id="dec-2",
                timestamp=datetime.now(timezone.utc).isoformat(),
                decision_type="approach_chosen",
                description="D2",
                reasoning="R2",
                subtask_id="subtask-2"
            ),
        ])

        results = storage.query(subtask_id="subtask-1")
        assert len(results) == 1
        assert results[0].subtask_id == "subtask-1"

    def test_query_by_phase(self, tmp_path):
        """query() should filter by phase."""
        storage = DecisionStorage(tmp_path)
        storage.add_entries([
            DecisionEntry(
                id="dec-1",
                timestamp=datetime.now(timezone.utc).isoformat(),
                decision_type="approach_chosen",
                description="D1",
                reasoning="R1",
                phase="planning"
            ),
            DecisionEntry(
                id="dec-2",
                timestamp=datetime.now(timezone.utc).isoformat(),
                decision_type="approach_chosen",
                description="D2",
                reasoning="R2",
                phase="coding"
            ),
        ])

        results = storage.query(phase="coding")
        assert len(results) == 1
        assert results[0].phase == "coding"

    def test_query_by_annotation(self, tmp_path):
        """query() should filter by annotation."""
        storage = DecisionStorage(tmp_path)
        storage.add_entries([
            DecisionEntry(
                id="dec-1",
                timestamp=datetime.now(timezone.utc).isoformat(),
                decision_type="approach_chosen",
                description="D1",
                reasoning="R1",
                annotation="good_pattern"
            ),
            DecisionEntry(
                id="dec-2",
                timestamp=datetime.now(timezone.utc).isoformat(),
                decision_type="approach_chosen",
                description="D2",
                reasoning="R2",
                annotation="bad_pattern"
            ),
            DecisionEntry(
                id="dec-3",
                timestamp=datetime.now(timezone.utc).isoformat(),
                decision_type="approach_chosen",
                description="D3",
                reasoning="R3"
            ),
        ])

        good = storage.query(annotation="good_pattern")
        assert len(good) == 1
        assert good[0].annotation == "good_pattern"

    def test_query_with_limit(self, tmp_path):
        """query() should respect limit parameter."""
        storage = DecisionStorage(tmp_path)
        storage.add_entries([
            DecisionEntry(
                id=f"dec-{i}",
                timestamp=datetime.now(timezone.utc).isoformat(),
                decision_type="approach_chosen",
                description=f"D{i}",
                reasoning=f"R{i}"
            )
            for i in range(10)
        ])

        results = storage.query(limit=3)
        assert len(results) == 3

    def test_query_combined_filters(self, tmp_path):
        """query() should combine multiple filters."""
        storage = DecisionStorage(tmp_path)
        storage.add_entries([
            DecisionEntry(
                id="dec-1",
                timestamp=datetime.now(timezone.utc).isoformat(),
                decision_type="approach_chosen",
                description="D1",
                reasoning="R1",
                subtask_id="subtask-1",
                phase="coding"
            ),
            DecisionEntry(
                id="dec-2",
                timestamp=datetime.now(timezone.utc).isoformat(),
                decision_type="approach_chosen",
                description="D2",
                reasoning="R2",
                subtask_id="subtask-1",
                phase="planning"
            ),
            DecisionEntry(
                id="dec-3",
                timestamp=datetime.now(timezone.utc).isoformat(),
                decision_type="tool_selected",
                description="D3",
                reasoning="R3",
                subtask_id="subtask-1",
                phase="coding"
            ),
        ])

        results = storage.query(
            decision_type="approach_chosen",
            subtask_id="subtask-1",
            phase="coding"
        )
        assert len(results) == 1
        assert results[0].id == "dec-1"

    def test_query_by_filter_object(self, tmp_path):
        """query_by_filter() should use DecisionFilter object."""
        storage = DecisionStorage(tmp_path)
        storage.add_entries([
            DecisionEntry(
                id="dec-1",
                timestamp=datetime.now(timezone.utc).isoformat(),
                decision_type="approach_chosen",
                description="D1",
                reasoning="R1",
                phase="coding"
            ),
        ])

        filter_obj = DecisionFilter(phase="coding")
        results = storage.query_by_filter(filter_obj)
        assert len(results) == 1

    def test_get_by_subtask(self, tmp_path):
        """get_by_subtask() should return decisions for subtask."""
        storage = DecisionStorage(tmp_path)
        storage.add_entries([
            DecisionEntry(
                id="dec-1",
                timestamp=datetime.now(timezone.utc).isoformat(),
                decision_type="approach_chosen",
                description="D1",
                reasoning="R1",
                subtask_id="subtask-1"
            ),
            DecisionEntry(
                id="dec-2",
                timestamp=datetime.now(timezone.utc).isoformat(),
                decision_type="tool_selected",
                description="D2",
                reasoning="R2",
                subtask_id="subtask-1"
            ),
        ])

        results = storage.get_by_subtask("subtask-1")
        assert len(results) == 2

    def test_get_by_phase(self, tmp_path):
        """get_by_phase() should return decisions for phase."""
        storage = DecisionStorage(tmp_path)
        storage.add_entries([
            DecisionEntry(
                id="dec-1",
                timestamp=datetime.now(timezone.utc).isoformat(),
                decision_type="approach_chosen",
                description="D1",
                reasoning="R1",
                phase="coding"
            ),
        ])

        results = storage.get_by_phase("coding")
        assert len(results) == 1

    def test_get_summary(self, tmp_path):
        """get_summary() should return decision statistics."""
        storage = DecisionStorage(tmp_path)
        storage.add_entries([
            DecisionEntry(
                id="dec-1",
                timestamp=datetime.now(timezone.utc).isoformat(),
                decision_type="approach_chosen",
                description="D1",
                reasoning="R1",
                phase="coding",
                annotation="good_pattern"
            ),
            DecisionEntry(
                id="dec-2",
                timestamp=datetime.now(timezone.utc).isoformat(),
                decision_type="tool_selected",
                description="D2",
                reasoning="R2",
                phase="coding",
                annotation="bad_pattern"
            ),
            DecisionEntry(
                id="dec-3",
                timestamp=datetime.now(timezone.utc).isoformat(),
                decision_type="approach_chosen",
                description="D3",
                reasoning="R3",
                phase="planning"
            ),
        ])

        summary = storage.get_summary()

        assert summary["total_decisions"] == 3
        assert summary["by_type"]["approach_chosen"] == 2
        assert summary["by_type"]["tool_selected"] == 1
        assert summary["by_phase"]["coding"] == 2
        assert summary["by_phase"]["planning"] == 1
        assert summary["by_annotation"]["good_pattern"] == 1
        assert summary["by_annotation"]["bad_pattern"] == 1
        assert summary["by_annotation"]["unannotated"] == 1

    def test_clear(self, tmp_path):
        """clear() should remove all decisions."""
        storage = DecisionStorage(tmp_path)
        storage.add_entries([
            DecisionEntry(
                id=f"dec-{i}",
                timestamp=datetime.now(timezone.utc).isoformat(),
                decision_type="approach_chosen",
                description=f"D{i}",
                reasoning=f"R{i}"
            )
            for i in range(5)
        ])

        assert len(storage.get_all()) == 5
        storage.clear()
        assert len(storage.get_all()) == 0

    def test_load_existing_file(self, tmp_path):
        """Storage should load existing decisions file."""
        # Create initial data
        decisions_file = tmp_path / "decisions.json"
        initial_data = {
            "spec_id": "test-spec",
            "created_at": "2026-01-26T10:00:00Z",
            "updated_at": "2026-01-26T10:00:00Z",
            "decisions": [
                {
                    "id": "existing-dec",
                    "timestamp": "2026-01-26T10:00:00Z",
                    "decision_type": "approach_chosen",
                    "description": "Existing decision",
                    "reasoning": "Loaded from file",
                    "alternatives_considered": [],
                    "context_used": [],
                    "confidence_level": "medium"
                }
            ]
        }
        with open(decisions_file, "w") as f:
            json.dump(initial_data, f)

        # Create storage - should load existing
        storage = DecisionStorage(tmp_path)
        assert len(storage.get_all()) == 1
        assert storage.get_all()[0].id == "existing-dec"


# ============================================================================
# Unit Tests for Storage Helper Functions
# ============================================================================

class TestStorageHelpers:
    """Unit tests for storage helper functions."""

    def test_load_decisions(self, tmp_path):
        """load_decisions() should load from file."""
        # Create decisions file
        decisions_file = tmp_path / "decisions.json"
        data = {
            "spec_id": "test",
            "decisions": [{"id": "dec-1", "description": "Test"}]
        }
        with open(decisions_file, "w") as f:
            json.dump(data, f)

        loaded = load_decisions(tmp_path)
        assert loaded is not None
        assert len(loaded["decisions"]) == 1

    def test_load_decisions_missing_file(self, tmp_path):
        """load_decisions() should return None for missing file."""
        assert load_decisions(tmp_path) is None

    def test_get_decision_count(self, tmp_path):
        """get_decision_count() should return correct count."""
        storage = DecisionStorage(tmp_path)
        storage.add_entries([
            DecisionEntry(
                id=f"dec-{i}",
                timestamp=datetime.now(timezone.utc).isoformat(),
                decision_type="approach_chosen",
                description=f"D{i}",
                reasoning=f"R{i}"
            )
            for i in range(7)
        ])

        assert get_decision_count(tmp_path) == 7

    def test_get_decision_count_no_file(self, tmp_path):
        """get_decision_count() should return 0 for missing file."""
        assert get_decision_count(tmp_path) == 0


# ============================================================================
# Integration Tests for DecisionAuditLogger
# ============================================================================

class TestDecisionAuditLogger:
    """Integration tests for DecisionAuditLogger."""

    @pytest.fixture(autouse=True)
    def reset_singleton(self):
        """Reset singleton before each test."""
        DecisionAuditLogger.reset_instance()
        yield
        DecisionAuditLogger.reset_instance()

    def test_create_logger(self, tmp_path):
        """Should create logger with storage."""
        logger = DecisionAuditLogger(tmp_path, emit_markers=False)
        assert logger.spec_dir == tmp_path
        assert logger.storage is not None
        assert logger.enabled is True

    def test_create_disabled_logger(self, tmp_path):
        """Should create disabled logger without storage."""
        logger = DecisionAuditLogger(tmp_path, enabled=False, emit_markers=False)
        assert logger.storage is None
        assert logger.enabled is False

    def test_log_decision(self, tmp_path):
        """log_decision() should create and persist decision."""
        logger = DecisionAuditLogger(tmp_path, emit_markers=False)

        entry = logger.log_decision(
            decision_type=DecisionType.APPROACH_CHOSEN,
            description="Use hooks for state",
            reasoning="Follows React best practices",
            alternatives=["Redux", "MobX"],
            confidence=ConfidenceLevel.HIGH
        )

        assert entry.id.startswith("dec-")
        assert entry.decision_type == "approach_chosen"
        assert entry.description == "Use hooks for state"
        assert len(entry.alternatives_considered) == 2

        # Verify persisted
        decisions = logger.get_decisions()
        assert len(decisions) == 1

    def test_log_approach_chosen(self, tmp_path):
        """log_approach_chosen() should log approach decision."""
        logger = DecisionAuditLogger(tmp_path, emit_markers=False)

        entry = logger.log_approach_chosen(
            description="Using TypeScript strict mode",
            reasoning="Catches more errors at compile time",
            alternatives=["Loose mode", "JavaScript only"]
        )

        assert entry.decision_type == "approach_chosen"
        assert "strict mode" in entry.description

    def test_log_alternative_rejected(self, tmp_path):
        """log_alternative_rejected() should log rejection."""
        logger = DecisionAuditLogger(tmp_path, emit_markers=False)

        entry = logger.log_alternative_rejected(
            description="Rejected using class components",
            reasoning="Hooks are more maintainable"
        )

        assert entry.decision_type == "alternative_rejected"

    def test_log_context_used(self, tmp_path):
        """log_context_used() should log context influence."""
        logger = DecisionAuditLogger(tmp_path, emit_markers=False)
        ctx = DecisionContext(
            source="graphiti_query",
            content="Found auth patterns"
        )

        entry = logger.log_context_used(
            description="Using established auth patterns",
            reasoning="Graphiti showed existing implementation",
            context=ctx
        )

        assert entry.decision_type == "context_used"
        assert len(entry.context_used) == 1

    def test_log_pattern_followed(self, tmp_path):
        """log_pattern_followed() should log pattern adherence."""
        logger = DecisionAuditLogger(tmp_path, emit_markers=False)

        entry = logger.log_pattern_followed(
            description="Following error handling pattern",
            reasoning="Matches existing codebase style",
            pattern_source="utils/error-handler.ts"
        )

        assert entry.decision_type == "pattern_followed"
        assert len(entry.context_used) == 1
        assert entry.context_used[0].source == "pattern_file"

    def test_log_file_selected(self, tmp_path):
        """log_file_selected() should log file selection."""
        logger = DecisionAuditLogger(tmp_path, emit_markers=False)

        entry = logger.log_file_selected(
            description="Selected utils.ts for modification",
            reasoning="Contains helper functions to extend",
            file_path="src/utils.ts",
            alternatives=["helpers.ts", "common.ts"]
        )

        assert entry.decision_type == "file_selected"
        assert len(entry.context_used) == 1
        assert entry.context_used[0].metadata["file_path"] == "src/utils.ts"

    def test_log_tool_selected(self, tmp_path):
        """log_tool_selected() should log tool selection."""
        logger = DecisionAuditLogger(tmp_path, emit_markers=False)

        entry = logger.log_tool_selected(
            description="Using Bash for npm operations",
            reasoning="Need to execute shell commands",
            tool_name="Bash",
            alternatives=["Read", "Edit"]
        )

        assert entry.decision_type == "tool_selected"
        assert entry.context_used[0].metadata["tool"] == "Bash"

    def test_log_error_recovery(self, tmp_path):
        """log_error_recovery() should log recovery decisions."""
        logger = DecisionAuditLogger(tmp_path, emit_markers=False)

        entry = logger.log_error_recovery(
            description="Retrying with different approach",
            reasoning="Initial approach failed with timeout",
            error="Command timed out after 30s",
            recovery_action="Using async version"
        )

        assert entry.decision_type == "error_recovery"
        assert "timed out" in entry.context_used[0].content.lower()

    def test_set_phase_and_subtask(self, tmp_path):
        """Logged decisions should inherit current phase and subtask."""
        logger = DecisionAuditLogger(tmp_path, emit_markers=False)

        logger.set_phase("coding")
        logger.set_subtask("subtask-2-1")

        entry = logger.log_approach_chosen(
            description="Test decision",
            reasoning="Test reasoning"
        )

        assert entry.phase == "coding"
        assert entry.subtask_id == "subtask-2-1"

    def test_override_phase_and_subtask(self, tmp_path):
        """Explicit phase/subtask should override defaults."""
        logger = DecisionAuditLogger(tmp_path, emit_markers=False)

        logger.set_phase("coding")
        logger.set_subtask("subtask-1")

        entry = logger.log_approach_chosen(
            description="Test",
            reasoning="Test",
            phase="planning",
            subtask_id="subtask-2"
        )

        assert entry.phase == "planning"
        assert entry.subtask_id == "subtask-2"

    def test_annotate_decision(self, tmp_path):
        """annotate_decision() should add annotation."""
        logger = DecisionAuditLogger(tmp_path, emit_markers=False)

        entry = logger.log_approach_chosen(
            description="Test decision",
            reasoning="Test reasoning"
        )

        result = logger.annotate_decision(
            entry.id,
            "good_pattern",
            "This approach worked well"
        )

        assert result is True

        # Verify annotation persisted
        decisions = logger.get_decisions()
        assert decisions[0].annotation == "good_pattern"
        assert decisions[0].annotation_note == "This approach worked well"

    def test_annotate_nonexistent_decision(self, tmp_path):
        """annotate_decision() should return False for missing ID."""
        logger = DecisionAuditLogger(tmp_path, emit_markers=False)

        result = logger.annotate_decision(
            "nonexistent-id",
            "good_pattern"
        )

        assert result is False

    def test_get_decisions_filtering(self, tmp_path):
        """get_decisions() should filter results."""
        logger = DecisionAuditLogger(tmp_path, emit_markers=False)

        logger.set_phase("coding")
        logger.log_approach_chosen(description="Approach 1", reasoning="R1")
        logger.log_tool_selected(
            description="Tool 1",
            reasoning="R2",
            tool_name="Bash"
        )

        logger.set_phase("planning")
        logger.log_approach_chosen(description="Approach 2", reasoning="R3")

        # Filter by type
        approaches = logger.get_decisions(decision_type=DecisionType.APPROACH_CHOSEN)
        assert len(approaches) == 2

        # Filter by phase
        coding = logger.get_decisions(phase="coding")
        assert len(coding) == 2

    def test_get_decision_summary(self, tmp_path):
        """get_decision_summary() should return statistics."""
        logger = DecisionAuditLogger(tmp_path, emit_markers=False)

        logger.log_approach_chosen(description="A1", reasoning="R1")
        logger.log_approach_chosen(description="A2", reasoning="R2")
        logger.log_tool_selected(description="T1", reasoning="R3", tool_name="Bash")

        summary = logger.get_decision_summary()

        assert summary["total_decisions"] == 3
        assert summary["by_type"]["approach_chosen"] == 2
        assert summary["by_type"]["tool_selected"] == 1

    def test_disabled_logger_operations(self, tmp_path):
        """Disabled logger should handle operations gracefully."""
        logger = DecisionAuditLogger(tmp_path, enabled=False, emit_markers=False)

        # Should not crash
        entry = logger.log_approach_chosen(description="Test", reasoning="Test")

        # Entry still created (for in-memory use)
        assert entry is not None

        # But no decisions persisted
        decisions = logger.get_decisions()
        assert len(decisions) == 0

        # Annotation returns False
        assert logger.annotate_decision("id", "good") is False

        # Summary is empty
        summary = logger.get_decision_summary()
        assert summary["total_decisions"] == 0

    def test_singleton_pattern(self, tmp_path):
        """get_instance() should return singleton."""
        logger1 = DecisionAuditLogger.get_instance(spec_dir=tmp_path, emit_markers=False)
        logger2 = DecisionAuditLogger.get_instance()

        assert logger1 is logger2

    def test_get_decision_logger_convenience(self, tmp_path):
        """get_decision_logger() should return logger instance."""
        logger = get_decision_logger(spec_dir=tmp_path)

        assert logger is not None
        assert isinstance(logger, DecisionAuditLogger)

    def test_context_from_dict(self, tmp_path):
        """Logger should handle dict context input."""
        logger = DecisionAuditLogger(tmp_path, emit_markers=False)

        entry = logger.log_context_used(
            description="Using file content",
            reasoning="Found relevant code",
            context={"source": "file_read", "content": "path/to/file.py"}
        )

        assert len(entry.context_used) == 1
        assert entry.context_used[0].source == "file_read"

    def test_context_from_list(self, tmp_path):
        """Logger should handle list of contexts."""
        logger = DecisionAuditLogger(tmp_path, emit_markers=False)

        contexts = [
            DecisionContext(source="file_read", content="file1.py"),
            DecisionContext(source="graphiti", content="query result"),
        ]

        entry = logger.log_context_used(
            description="Multiple sources",
            reasoning="Combined context",
            context=contexts
        )

        assert len(entry.context_used) == 2


# ============================================================================
# Tests for Streaming Markers
# ============================================================================

class TestStreamingMarkers:
    """Tests for streaming marker emission."""

    def test_emit_decision_marker_enabled(self, capsys):
        """emit_decision_marker() should print when enabled."""
        emit_decision_marker(
            "DECISION_LOGGED",
            {"id": "dec-001", "type": "approach_chosen"},
            enabled=True
        )

        captured = capsys.readouterr()
        assert "__DECISION_LOG_DECISION_LOGGED__:" in captured.out
        assert "dec-001" in captured.out

    def test_emit_decision_marker_disabled(self, capsys):
        """emit_decision_marker() should not print when disabled."""
        emit_decision_marker(
            "DECISION_LOGGED",
            {"id": "dec-001"},
            enabled=False
        )

        captured = capsys.readouterr()
        assert captured.out == ""

    def test_logger_emits_markers(self, tmp_path, capsys):
        """Logger should emit markers when enabled."""
        logger = DecisionAuditLogger(tmp_path, emit_markers=True)

        logger.log_approach_chosen(
            description="Test decision",
            reasoning="Test reasoning"
        )

        captured = capsys.readouterr()
        assert "__DECISION_LOG_DECISION_LOGGED__:" in captured.out

    def test_logger_suppresses_markers(self, tmp_path, capsys):
        """Logger should suppress markers when disabled."""
        logger = DecisionAuditLogger(tmp_path, emit_markers=False)

        logger.log_approach_chosen(
            description="Test decision",
            reasoning="Test reasoning"
        )

        captured = capsys.readouterr()
        assert "__DECISION_LOG_" not in captured.out


# ============================================================================
# Tests for Public API Exports
# ============================================================================

class TestPublicAPIExports:
    """Tests for the decision_audit public API exports."""

    def test_all_expected_exports(self):
        """All expected exports should be available from package."""
        from decision_audit import (
            # Logger
            DecisionAuditLogger,
            get_decision_logger,
            emit_decision_marker,
            # Models
            DecisionType,
            DecisionEntry,
            DecisionContext,
            DecisionFilter,
            ConfidenceLevel,
            # Storage
            DecisionStorage,
            load_decisions,
            get_decision_count,
            # Extractor
            extract_decisions_from_response,
            extract_decisions_sync,
            is_decision_extraction_enabled,
        )
        # If imports succeed, the test passes
        assert True

    def test_extractor_imports(self):
        """Extractor functions should be importable."""
        from decision_audit import (
            is_decision_extraction_enabled,
            extract_decisions_from_response,
            extract_decisions_sync,
        )

        # Check functions are callable
        assert callable(is_decision_extraction_enabled)
        assert callable(extract_decisions_from_response)
        assert callable(extract_decisions_sync)


# ============================================================================
# Integration Tests for Extractor Helper Functions
# ============================================================================

class TestExtractorHelpers:
    """Tests for extractor helper functions (not requiring LLM)."""

    def test_parse_extraction_response_valid_json(self):
        """_parse_extraction_response should parse valid JSON."""
        from decision_audit.extractor import _parse_extraction_response

        response = '{"decisions": [{"type": "approach_chosen", "description": "Test"}]}'
        result = _parse_extraction_response(response)

        assert result is not None
        assert len(result["decisions"]) == 1

    def test_parse_extraction_response_with_code_block(self):
        """Should handle markdown code blocks."""
        from decision_audit.extractor import _parse_extraction_response

        response = '''```json
{"decisions": [{"type": "tool_selected", "description": "Used Bash"}]}
```'''
        result = _parse_extraction_response(response)

        assert result is not None
        assert len(result["decisions"]) == 1

    def test_parse_extraction_response_empty(self):
        """Should return None for empty response."""
        from decision_audit.extractor import _parse_extraction_response

        assert _parse_extraction_response("") is None
        assert _parse_extraction_response("   ") is None

    def test_parse_extraction_response_invalid_json(self):
        """Should return None for invalid JSON."""
        from decision_audit.extractor import _parse_extraction_response

        assert _parse_extraction_response("not json at all") is None
        assert _parse_extraction_response('{"incomplete":') is None

    def test_convert_to_decision_entries(self):
        """_convert_to_decision_entries should create DecisionEntry objects."""
        from decision_audit.extractor import _convert_to_decision_entries

        raw_decisions = [
            {
                "type": "approach_chosen",
                "description": "Using hooks",
                "reasoning": "Modern pattern",
                "alternatives_considered": ["classes", "mobx"],
                "context_used": [{"source": "docs", "content": "React docs"}],
                "confidence": "high"
            },
            {
                "type": "file_selected",
                "description": "Selected utils.ts",
                "reasoning": "Has helpers",
                "confidence": "medium"
            }
        ]

        entries = _convert_to_decision_entries(
            raw_decisions,
            subtask_id="subtask-1",
            phase="coding"
        )

        assert len(entries) == 2
        assert entries[0].decision_type == "approach_chosen"
        assert entries[0].subtask_id == "subtask-1"
        assert entries[0].phase == "coding"
        assert entries[0].confidence_level == "high"
        assert len(entries[0].alternatives_considered) == 2
        assert len(entries[0].context_used) == 1

    def test_convert_handles_invalid_type(self):
        """Should use default for invalid decision type."""
        from decision_audit.extractor import _convert_to_decision_entries

        raw_decisions = [
            {
                "type": "invalid_type",
                "description": "Test",
                "reasoning": "Test"
            }
        ]

        entries = _convert_to_decision_entries(raw_decisions)

        assert len(entries) == 1
        assert entries[0].decision_type == "approach_chosen"  # Default

    def test_convert_handles_invalid_confidence(self):
        """Should use default for invalid confidence level."""
        from decision_audit.extractor import _convert_to_decision_entries

        raw_decisions = [
            {
                "type": "approach_chosen",
                "description": "Test",
                "reasoning": "Test",
                "confidence": "very_high"  # Invalid
            }
        ]

        entries = _convert_to_decision_entries(raw_decisions)

        assert len(entries) == 1
        assert entries[0].confidence_level == "medium"  # Default

    def test_build_extraction_prompt(self):
        """_build_extraction_prompt should include response text."""
        from decision_audit.extractor import _build_extraction_prompt

        prompt = _build_extraction_prompt(
            "Test agent response about using React hooks",
            subtask_id="subtask-1-1"
        )

        assert "Test agent response" in prompt
        assert "subtask-1-1" in prompt
        assert "AGENT RESPONSE TO ANALYZE" in prompt

    def test_build_extraction_prompt_truncates_long_text(self):
        """Should truncate very long response text."""
        from decision_audit.extractor import _build_extraction_prompt, MAX_RESPONSE_CHARS

        long_text = "x" * (MAX_RESPONSE_CHARS + 5000)
        prompt = _build_extraction_prompt(long_text)

        # Should mention truncation
        assert "truncated" in prompt


# ============================================================================
# Integration Test Markers
# ============================================================================

@pytest.mark.integration
class TestDecisionAuditIntegration:
    """Full integration tests for the decision audit system."""

    @pytest.fixture(autouse=True)
    def reset_singleton(self):
        """Reset singleton before each test."""
        DecisionAuditLogger.reset_instance()
        yield
        DecisionAuditLogger.reset_instance()

    def test_full_decision_lifecycle(self, tmp_path):
        """Test complete decision lifecycle: log -> query -> annotate -> export."""
        # Create logger
        logger = DecisionAuditLogger(tmp_path, emit_markers=False)
        logger.set_phase("coding")
        logger.set_subtask("subtask-1-1")

        # Log various decisions
        dec1 = logger.log_approach_chosen(
            description="Using TypeScript strict mode",
            reasoning="Catches more errors",
            alternatives=["loose mode", "no typescript"]
        )

        dec2 = logger.log_file_selected(
            description="Selected config.ts",
            reasoning="Central config location",
            file_path="src/config.ts"
        )

        logger.set_subtask("subtask-1-2")
        dec3 = logger.log_tool_selected(
            description="Using Bash for installation",
            reasoning="Need npm commands",
            tool_name="Bash"
        )

        # Query decisions
        all_decisions = logger.get_decisions()
        assert len(all_decisions) == 3

        subtask1_decisions = logger.get_decisions(subtask_id="subtask-1-1")
        assert len(subtask1_decisions) == 2

        # Annotate decisions
        logger.annotate_decision(dec1.id, "good_pattern", "Strict mode worked well")
        logger.annotate_decision(dec2.id, "bad_pattern", "Should have used env vars")

        # Get summary
        summary = logger.get_decision_summary()
        assert summary["total_decisions"] == 3
        assert summary["by_annotation"]["good_pattern"] == 1
        assert summary["by_annotation"]["bad_pattern"] == 1
        assert summary["by_annotation"]["unannotated"] == 1

        # Verify persistence by creating new storage instance
        new_storage = DecisionStorage(tmp_path)
        assert len(new_storage.get_all()) == 3

        # Query annotated
        good_patterns = new_storage.query(annotation="good_pattern")
        assert len(good_patterns) == 1
        assert good_patterns[0].annotation_note == "Strict mode worked well"

    def test_decision_recovery_from_file(self, tmp_path):
        """Test that decisions survive across logger instances."""
        # First session
        logger1 = DecisionAuditLogger(tmp_path, emit_markers=False)
        logger1.log_approach_chosen(
            description="Session 1 decision",
            reasoning="First reasoning"
        )

        # Reset singleton
        DecisionAuditLogger.reset_instance()

        # Second session
        logger2 = DecisionAuditLogger(tmp_path, emit_markers=False)
        logger2.log_approach_chosen(
            description="Session 2 decision",
            reasoning="Second reasoning"
        )

        # Should have both decisions
        all_decisions = logger2.get_decisions()
        assert len(all_decisions) == 2

        descriptions = [d.description for d in all_decisions]
        assert "Session 1 decision" in descriptions
        assert "Session 2 decision" in descriptions
