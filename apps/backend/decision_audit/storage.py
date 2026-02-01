"""
Storage functionality for decision audit trail.

Provides JSON file persistence and query capabilities for agent decisions.
"""

from __future__ import annotations

import json
import os
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .models import DecisionContext, DecisionEntry, DecisionFilter, DecisionType


class DecisionStorage:
    """Handles persistent storage of decision audit trail.

    Usage:
        storage = DecisionStorage(spec_dir=Path(".auto-claude/specs/001-feature"))

        # Add a decision
        entry = DecisionEntry(
            id="dec-001",
            timestamp=datetime.now(timezone.utc).isoformat(),
            decision_type=DecisionType.APPROACH_CHOSEN.value,
            description="Chose React hooks over class components",
            reasoning="Modern pattern with better TypeScript support",
            alternatives_considered=["Class components", "MobX observables"],
        )
        storage.add_entry(entry)

        # Query decisions
        decisions = storage.query(decision_type=DecisionType.APPROACH_CHOSEN.value)
    """

    DECISIONS_FILE = "decisions.json"

    def __init__(self, spec_dir: Path):
        """
        Initialize decision storage.

        Args:
            spec_dir: Path to the spec directory
        """
        self.spec_dir = Path(spec_dir)
        self.decisions_file = self.spec_dir / self.DECISIONS_FILE
        self._data: dict[str, Any] = self._load_or_create()

    def _load_or_create(self) -> dict[str, Any]:
        """Load existing decisions or create new structure."""
        if self.decisions_file.exists():
            try:
                with open(self.decisions_file, encoding="utf-8") as f:
                    return json.load(f)
            except (OSError, json.JSONDecodeError, UnicodeDecodeError):
                pass

        return {
            "spec_id": self.spec_dir.name,
            "created_at": self._timestamp(),
            "updated_at": self._timestamp(),
            "decisions": [],
        }

    def _timestamp(self) -> str:
        """Get current timestamp in ISO format."""
        return datetime.now(timezone.utc).isoformat()

    def save(self) -> None:
        """Save decisions to file atomically to prevent corruption from concurrent reads."""
        self._data["updated_at"] = self._timestamp()
        try:
            self.spec_dir.mkdir(parents=True, exist_ok=True)
            # Write to temp file first, then atomic rename to prevent corruption
            # when the UI reads mid-write
            fd, tmp_path = tempfile.mkstemp(
                dir=self.spec_dir, prefix=".decisions_", suffix=".tmp"
            )
            try:
                with os.fdopen(fd, "w", encoding="utf-8") as f:
                    json.dump(self._data, f, indent=2, ensure_ascii=False)
                # Atomic rename (on POSIX systems, rename is atomic)
                os.replace(tmp_path, self.decisions_file)
            except Exception:
                # Clean up temp file on failure
                if os.path.exists(tmp_path):
                    os.unlink(tmp_path)
                raise
        except OSError as e:
            print(f"Warning: Failed to save decisions: {e}", file=sys.stderr)

    def load(self) -> dict[str, Any]:
        """Reload data from file."""
        self._data = self._load_or_create()
        return self._data

    def add_entry(self, entry: DecisionEntry) -> None:
        """
        Add a decision entry to storage.

        Args:
            entry: The decision entry to add
        """
        self._data["decisions"].append(entry.to_dict())
        self.save()

    def add_entries(self, entries: list[DecisionEntry]) -> None:
        """
        Add multiple decision entries to storage.

        Args:
            entries: List of decision entries to add
        """
        for entry in entries:
            self._data["decisions"].append(entry.to_dict())
        self.save()

    def get_entry(self, decision_id: str) -> DecisionEntry | None:
        """
        Get a specific decision by ID.

        Args:
            decision_id: The decision ID to look up

        Returns:
            DecisionEntry if found, None otherwise
        """
        for decision_data in self._data.get("decisions", []):
            if decision_data.get("id") == decision_id:
                return DecisionEntry.from_dict(decision_data)
        return None

    def update_entry(self, decision_id: str, updates: dict[str, Any]) -> bool:
        """
        Update a decision entry.

        Args:
            decision_id: The decision ID to update
            updates: Dictionary of fields to update

        Returns:
            True if updated, False if not found
        """
        for decision_data in self._data.get("decisions", []):
            if decision_data.get("id") == decision_id:
                decision_data.update(updates)
                self.save()
                return True
        return False

    def annotate(
        self, decision_id: str, annotation: str, note: str | None = None
    ) -> bool:
        """
        Annotate a decision as good/bad pattern.

        Args:
            decision_id: The decision ID to annotate
            annotation: The annotation ("good_pattern" or "bad_pattern")
            note: Optional note explaining the annotation

        Returns:
            True if annotated, False if not found
        """
        return self.update_entry(
            decision_id,
            {"annotation": annotation, "annotation_note": note},
        )

    def query(
        self,
        decision_type: str | None = None,
        subtask_id: str | None = None,
        phase: str | None = None,
        annotation: str | None = None,
        since: datetime | None = None,
        until: datetime | None = None,
        limit: int | None = None,
    ) -> list[DecisionEntry]:
        """
        Query decisions with filters.

        Args:
            decision_type: Filter by decision type
            subtask_id: Filter by subtask ID
            phase: Filter by phase
            annotation: Filter by annotation
            since: Only entries after this time
            until: Only entries before this time
            limit: Maximum entries to return

        Returns:
            List of matching DecisionEntry objects
        """
        results: list[DecisionEntry] = []

        for decision_data in self._data.get("decisions", []):
            # Apply filters
            if decision_type and decision_data.get("decision_type") != decision_type:
                continue
            if subtask_id and decision_data.get("subtask_id") != subtask_id:
                continue
            if phase and decision_data.get("phase") != phase:
                continue
            if annotation and decision_data.get("annotation") != annotation:
                continue

            # Time filters
            if since or until:
                try:
                    entry_time = datetime.fromisoformat(
                        decision_data.get("timestamp", "")
                    )
                    if since and entry_time < since:
                        continue
                    if until and entry_time > until:
                        continue
                except (ValueError, TypeError):
                    continue

            results.append(DecisionEntry.from_dict(decision_data))

            if limit and len(results) >= limit:
                break

        return results

    def query_by_filter(self, filter_obj: DecisionFilter) -> list[DecisionEntry]:
        """
        Query decisions using a DecisionFilter object.

        Args:
            filter_obj: Filter criteria

        Returns:
            List of matching DecisionEntry objects
        """
        return self.query(
            decision_type=filter_obj.decision_type,
            subtask_id=filter_obj.subtask_id,
            phase=filter_obj.phase,
            annotation=filter_obj.annotation,
            since=filter_obj.since,
            until=filter_obj.until,
        )

    def get_all(self) -> list[DecisionEntry]:
        """Get all decisions."""
        return [
            DecisionEntry.from_dict(d)
            for d in self._data.get("decisions", [])
        ]

    def get_data(self) -> dict[str, Any]:
        """Get raw data dictionary."""
        return self._data

    def get_by_subtask(self, subtask_id: str) -> list[DecisionEntry]:
        """
        Get all decisions for a specific subtask.

        Args:
            subtask_id: The subtask ID

        Returns:
            List of DecisionEntry objects for that subtask
        """
        return self.query(subtask_id=subtask_id)

    def get_by_phase(self, phase: str) -> list[DecisionEntry]:
        """
        Get all decisions for a specific phase.

        Args:
            phase: The phase name

        Returns:
            List of DecisionEntry objects for that phase
        """
        return self.query(phase=phase)

    def get_summary(self) -> dict[str, Any]:
        """
        Get summary statistics for decisions.

        Returns:
            Dictionary with counts by type, phase, and annotation
        """
        decisions = self._data.get("decisions", [])

        summary: dict[str, Any] = {
            "total_decisions": len(decisions),
            "by_type": {},
            "by_phase": {},
            "by_annotation": {
                "good_pattern": 0,
                "bad_pattern": 0,
                "unannotated": 0,
            },
        }

        for decision in decisions:
            # Count by type
            d_type = decision.get("decision_type", "unknown")
            summary["by_type"][d_type] = summary["by_type"].get(d_type, 0) + 1

            # Count by phase
            phase = decision.get("phase") or "unspecified"
            summary["by_phase"][phase] = summary["by_phase"].get(phase, 0) + 1

            # Count by annotation
            annotation = decision.get("annotation")
            if annotation == "good_pattern":
                summary["by_annotation"]["good_pattern"] += 1
            elif annotation == "bad_pattern":
                summary["by_annotation"]["bad_pattern"] += 1
            else:
                summary["by_annotation"]["unannotated"] += 1

        return summary

    def clear(self) -> None:
        """Clear all decisions (for testing)."""
        self._data["decisions"] = []
        self.save()


def load_decisions(spec_dir: Path) -> dict[str, Any] | None:
    """
    Load decisions from a spec directory.

    Args:
        spec_dir: Path to the spec directory

    Returns:
        Decisions dictionary or None if not found
    """
    decisions_file = spec_dir / DecisionStorage.DECISIONS_FILE
    if not decisions_file.exists():
        return None

    try:
        with open(decisions_file, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, json.JSONDecodeError, UnicodeDecodeError):
        return None


def get_decision_count(spec_dir: Path) -> int:
    """
    Get the number of decisions for a spec.

    Args:
        spec_dir: Path to the spec directory

    Returns:
        Number of decisions or 0 if not found
    """
    data = load_decisions(spec_dir)
    if not data:
        return 0
    return len(data.get("decisions", []))
