"""
Conflict Predictor
==================

Predicts merge conflicts BEFORE they occur by comparing worktree changes
against the base branch using non-destructive git operations.

Uses `git merge-tree --write-tree` for in-memory conflict detection
without modifying the working directory, then leverages ConflictDetector
for semantic analysis of detected conflicts.
"""

from __future__ import annotations

import logging
import re
import subprocess
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any

from .conflict_detector import ConflictDetector
from .types import ConflictSeverity

# Import debug utilities
try:
    from debug import debug, debug_success, debug_warning
except ImportError:

    def debug(*args, **kwargs):
        pass

    def debug_success(*args, **kwargs):
        pass

    def debug_warning(*args, **kwargs):
        pass


logger = logging.getLogger(__name__)
MODULE = "merge.conflict_predictor"


class ConflictType(Enum):
    """Classification of predicted conflict types."""

    CONTENT = "content"  # Both sides modified same lines
    ADD_ADD = "add_add"  # Both sides added a file
    MODIFY_DELETE = "modify_delete"  # One side modified, other deleted
    RENAME = "rename"  # File renamed differently on each side
    UNKNOWN = "unknown"


@dataclass
class PredictedConflict:
    """
    A single predicted conflict for a file.

    Attributes:
        file_path: Path to the conflicting file (relative to project root)
        conflict_type: Classification of the conflict
        severity: How serious the conflict is
        description: Human-readable description of the conflict
        metadata: Additional context (conflict markers, line ranges, etc.)
    """

    file_path: str
    conflict_type: ConflictType
    severity: ConflictSeverity
    description: str
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "file_path": self.file_path,
            "conflict_type": self.conflict_type.value,
            "severity": self.severity.value,
            "description": self.description,
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> PredictedConflict:
        """Create from dictionary."""
        return cls(
            file_path=data["file_path"],
            conflict_type=ConflictType(data["conflict_type"]),
            severity=ConflictSeverity(data["severity"]),
            description=data.get("description", ""),
            metadata=data.get("metadata", {}),
        )


@dataclass
class PredictionResult:
    """
    Complete result of a conflict prediction analysis.

    Attributes:
        has_conflicts: Whether any conflicts were detected
        conflicts: List of predicted conflicts
        affected_files: All files that differ between branches
        base_branch: The base branch compared against
        spec_branch: The worktree branch
        commits_behind: How many commits the base has advanced
        needs_rebase: Whether the worktree needs rebasing
        error: Error message if prediction failed
    """

    has_conflicts: bool = False
    conflicts: list[PredictedConflict] = field(default_factory=list)
    affected_files: list[str] = field(default_factory=list)
    base_branch: str = ""
    spec_branch: str = ""
    commits_behind: int = 0
    needs_rebase: bool = False
    error: str | None = None

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "has_conflicts": self.has_conflicts,
            "conflicts": [c.to_dict() for c in self.conflicts],
            "affected_files": self.affected_files,
            "base_branch": self.base_branch,
            "spec_branch": self.spec_branch,
            "commits_behind": self.commits_behind,
            "needs_rebase": self.needs_rebase,
            "error": self.error,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> PredictionResult:
        """Create from dictionary."""
        return cls(
            has_conflicts=data.get("has_conflicts", False),
            conflicts=[
                PredictedConflict.from_dict(c) for c in data.get("conflicts", [])
            ],
            affected_files=data.get("affected_files", []),
            base_branch=data.get("base_branch", ""),
            spec_branch=data.get("spec_branch", ""),
            commits_behind=data.get("commits_behind", 0),
            needs_rebase=data.get("needs_rebase", False),
            error=data.get("error"),
        )

    @property
    def critical_count(self) -> int:
        """Count of critical/high severity conflicts."""
        return sum(
            1
            for c in self.conflicts
            if c.severity in (ConflictSeverity.CRITICAL, ConflictSeverity.HIGH)
        )


class ConflictPredictor:
    """
    Predicts merge conflicts using non-destructive git operations.

    Uses `git merge-tree --write-tree` to detect conflicts in-memory
    without modifying the working directory, then classifies and
    assesses severity of each conflict.

    Example:
        predictor = ConflictPredictor(
            worktree_path=Path("/path/to/worktree"),
            base_branch="main",
        )
        result = predictor.predict()
        if result.has_conflicts:
            for conflict in result.conflicts:
                print(f"{conflict.file_path}: {conflict.severity.value}")
    """

    def __init__(
        self,
        worktree_path: Path,
        base_branch: str = "main",
        detector: ConflictDetector | None = None,
    ):
        """
        Initialize the conflict predictor.

        Args:
            worktree_path: Path to the worktree directory
            base_branch: Base branch to compare against
            detector: Optional ConflictDetector for semantic analysis
        """
        self._worktree_path = Path(worktree_path)
        self._base_branch = base_branch
        self._detector = detector or ConflictDetector()
        debug(
            MODULE,
            "Initialized ConflictPredictor",
            worktree=str(worktree_path),
            base_branch=base_branch,
        )

    def predict(self) -> PredictionResult:
        """
        Run conflict prediction analysis.

        Performs a non-destructive merge check using git merge-tree
        and returns structured prediction results.

        Returns:
            PredictionResult with conflict details
        """
        result = PredictionResult(base_branch=self._base_branch)

        # Detect the spec branch (current HEAD of the worktree)
        spec_branch = self._get_current_branch()
        if not spec_branch:
            result.error = "Could not determine worktree branch"
            return result
        result.spec_branch = spec_branch

        # Get merge base and check how far behind
        merge_base = self._get_merge_base(spec_branch)
        if not merge_base:
            result.error = (
                f"Could not find merge base between "
                f"{self._base_branch} and {spec_branch}"
            )
            return result

        # Count commits the base branch is ahead
        commits_behind = self._count_commits_ahead(merge_base)
        result.commits_behind = commits_behind
        result.needs_rebase = commits_behind > 0

        # Get files changed in the worktree
        result.affected_files = self._get_changed_files(merge_base)

        # Run non-destructive merge-tree check
        conflicts = self._run_merge_tree(spec_branch)
        result.conflicts = conflicts
        result.has_conflicts = len(conflicts) > 0

        if result.has_conflicts:
            debug(
                MODULE,
                f"Predicted {len(conflicts)} conflicts",
                files=[c.file_path for c in conflicts],
            )
        else:
            debug_success(MODULE, "No conflicts predicted")

        return result

    def _get_current_branch(self) -> str | None:
        """Get the current branch name of the worktree."""
        try:
            result = subprocess.run(
                ["git", "rev-parse", "--abbrev-ref", "HEAD"],
                cwd=self._worktree_path,
                capture_output=True,
                text=True,
                timeout=10,
            )
            if result.returncode == 0:
                return result.stdout.strip()
        except (subprocess.CalledProcessError, subprocess.TimeoutExpired) as e:
            debug_warning(MODULE, f"Failed to get current branch: {e}")
        return None

    def _get_merge_base(self, spec_branch: str) -> str | None:
        """Find the merge base between base branch and spec branch."""
        try:
            result = subprocess.run(
                ["git", "merge-base", self._base_branch, spec_branch],
                cwd=self._worktree_path,
                capture_output=True,
                text=True,
                timeout=10,
            )
            if result.returncode == 0:
                return result.stdout.strip()
        except (subprocess.CalledProcessError, subprocess.TimeoutExpired) as e:
            debug_warning(MODULE, f"Failed to find merge base: {e}")
        return None

    def _count_commits_ahead(self, merge_base: str) -> int:
        """Count how many commits the base branch is ahead of the merge base."""
        try:
            result = subprocess.run(
                [
                    "git",
                    "rev-list",
                    "--count",
                    f"{merge_base}..{self._base_branch}",
                ],
                cwd=self._worktree_path,
                capture_output=True,
                text=True,
                timeout=10,
            )
            if result.returncode == 0:
                return int(result.stdout.strip())
        except (
            subprocess.CalledProcessError,
            subprocess.TimeoutExpired,
            ValueError,
        ) as e:
            debug_warning(MODULE, f"Failed to count commits ahead: {e}")
        return 0

    def _get_changed_files(self, merge_base: str) -> list[str]:
        """Get files changed between merge base and worktree HEAD."""
        try:
            result = subprocess.run(
                ["git", "diff", "--name-only", f"{merge_base}..HEAD"],
                cwd=self._worktree_path,
                capture_output=True,
                text=True,
                timeout=30,
            )
            if result.returncode == 0:
                return [
                    f.strip()
                    for f in result.stdout.strip().split("\n")
                    if f.strip()
                ]
        except (subprocess.CalledProcessError, subprocess.TimeoutExpired) as e:
            debug_warning(MODULE, f"Failed to get changed files: {e}")
        return []

    def _run_merge_tree(self, spec_branch: str) -> list[PredictedConflict]:
        """
        Run git merge-tree --write-tree for non-destructive conflict detection.

        Args:
            spec_branch: The worktree's branch name

        Returns:
            List of predicted conflicts
        """
        try:
            result = subprocess.run(
                [
                    "git",
                    "merge-tree",
                    "--write-tree",
                    "--no-messages",
                    self._base_branch,
                    spec_branch,
                ],
                cwd=self._worktree_path,
                capture_output=True,
                text=True,
                timeout=30,
            )

            # Exit code 0 means no conflicts
            if result.returncode == 0:
                return []

            # Exit code 1 means conflicts detected
            return self._parse_merge_tree_output(
                result.stdout + result.stderr
            )

        except subprocess.TimeoutExpired:
            debug_warning(MODULE, "git merge-tree timed out")
            return []
        except Exception as e:
            debug_warning(MODULE, f"git merge-tree failed: {e}")
            return []

    def _parse_merge_tree_output(self, output: str) -> list[PredictedConflict]:
        """
        Parse git merge-tree output to extract conflict information.

        Args:
            output: Combined stdout+stderr from git merge-tree

        Returns:
            List of predicted conflicts
        """
        conflicts: list[PredictedConflict] = []
        seen_files: set[str] = set()

        for line in output.split("\n"):
            if "CONFLICT" not in line:
                continue

            conflict_type = self._classify_conflict_line(line)
            file_path = self._extract_file_path(line)

            if not file_path or file_path in seen_files:
                continue

            # Skip .auto-claude internal files
            if file_path.startswith(".auto-claude/"):
                continue

            seen_files.add(file_path)
            severity = self._assess_severity(file_path, conflict_type)

            conflicts.append(
                PredictedConflict(
                    file_path=file_path,
                    conflict_type=conflict_type,
                    severity=severity,
                    description=line.strip(),
                )
            )

        return conflicts

    def _classify_conflict_line(self, line: str) -> ConflictType:
        """Classify the type of conflict from a merge-tree output line."""
        line_lower = line.lower()
        if "modify/delete" in line_lower:
            return ConflictType.MODIFY_DELETE
        if "add/add" in line_lower:
            return ConflictType.ADD_ADD
        if "rename" in line_lower:
            return ConflictType.RENAME
        if "content" in line_lower or "merge conflict" in line_lower:
            return ConflictType.CONTENT
        return ConflictType.CONTENT  # Default to content conflict

    def _extract_file_path(self, line: str) -> str | None:
        """Extract the file path from a conflict line."""
        # Match patterns like "Merge conflict in path/to/file"
        # or "CONFLICT (content): Merge conflict in path/to/file"
        match = re.search(
            r"(?:Merge conflict in|CONFLICT.*?:)\s*(.+?)(?:\s*$|\s+\()",
            line,
        )
        if match:
            return match.group(1).strip()

        # Fallback: try to extract any path-like string after CONFLICT
        match = re.search(r"CONFLICT\s*\([^)]+\):\s*(.+?)(?:\s*$)", line)
        if match:
            path = match.group(1).strip()
            # Clean up common suffixes
            path = re.sub(r"\s+\(.*\)$", "", path)
            return path if path else None

        return None

    def _assess_severity(
        self, file_path: str, conflict_type: ConflictType
    ) -> ConflictSeverity:
        """
        Assess the severity of a predicted conflict.

        Args:
            file_path: Path to the conflicting file
            conflict_type: The type of conflict detected

        Returns:
            Severity level for the conflict
        """
        # Modify/delete and rename conflicts are typically high severity
        if conflict_type == ConflictType.MODIFY_DELETE:
            return ConflictSeverity.HIGH
        if conflict_type == ConflictType.RENAME:
            return ConflictSeverity.HIGH

        # Lock files and generated files are low severity
        if _is_generated_file(file_path):
            return ConflictSeverity.LOW

        # Config files can be tricky
        if _is_config_file(file_path):
            return ConflictSeverity.MEDIUM

        # Default content conflicts are medium
        return ConflictSeverity.MEDIUM


def _is_generated_file(file_path: str) -> bool:
    """Check if a file is generated/lock file (lower conflict severity)."""
    generated_patterns = (
        "package-lock.json",
        "yarn.lock",
        "pnpm-lock.yaml",
        "Pipfile.lock",
        "poetry.lock",
        "uv.lock",
        ".min.js",
        ".min.css",
        ".map",
    )
    return any(file_path.endswith(p) for p in generated_patterns)


def _is_config_file(file_path: str) -> bool:
    """Check if a file is a configuration file."""
    config_patterns = (
        "package.json",
        "tsconfig.json",
        "pyproject.toml",
        "setup.cfg",
        "requirements.txt",
        ".eslintrc",
        ".prettierrc",
    )
    name = file_path.rsplit("/", 1)[-1] if "/" in file_path else file_path
    return any(name.endswith(p) or name == p for p in config_patterns)
