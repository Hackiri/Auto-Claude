#!/usr/bin/env python3
"""
Tests for ConflictPredictor, ResolutionAdvisor, and ConflictMonitor
===================================================================

Covers:
- ConflictPredictor: conflict detection with mock git data, parsing, severity
- ResolutionAdvisor: resolution advice generation for various conflict types
- ConflictMonitor: lifecycle (start/stop), check_now, report persistence
"""

import json
import sys
import time
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

# Add auto-claude directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent / "apps" / "backend"))

from merge.conflict_predictor import (
    ConflictPredictor,
    ConflictType,
    PredictedConflict,
    PredictionResult,
    _is_config_file,
    _is_generated_file,
)
from merge.conflict_monitor import (
    ConflictMonitor,
    ConflictReport,
    WorktreeConflictStatus,
)
from merge.resolution_advisor import ConflictAdvice, ResolutionAdvisor
from merge.types import (
    ChangeType,
    ConflictRegion,
    ConflictSeverity,
    MergeStrategy,
)


# =============================================================================
# ConflictPredictor Tests
# =============================================================================


class TestConflictType:
    """Tests for ConflictType enum."""

    def test_conflict_types_exist(self):
        assert ConflictType.CONTENT.value == "content"
        assert ConflictType.ADD_ADD.value == "add_add"
        assert ConflictType.MODIFY_DELETE.value == "modify_delete"
        assert ConflictType.RENAME.value == "rename"
        assert ConflictType.UNKNOWN.value == "unknown"


class TestPredictedConflict:
    """Tests for PredictedConflict dataclass."""

    def test_to_dict(self):
        conflict = PredictedConflict(
            file_path="src/app.py",
            conflict_type=ConflictType.CONTENT,
            severity=ConflictSeverity.MEDIUM,
            description="Merge conflict in src/app.py",
        )
        d = conflict.to_dict()
        assert d["file_path"] == "src/app.py"
        assert d["conflict_type"] == "content"
        assert d["severity"] == "medium"
        assert d["description"] == "Merge conflict in src/app.py"
        assert d["metadata"] == {}

    def test_from_dict(self):
        data = {
            "file_path": "src/app.py",
            "conflict_type": "add_add",
            "severity": "high",
            "description": "Both added src/app.py",
            "metadata": {"key": "value"},
        }
        conflict = PredictedConflict.from_dict(data)
        assert conflict.file_path == "src/app.py"
        assert conflict.conflict_type == ConflictType.ADD_ADD
        assert conflict.severity == ConflictSeverity.HIGH
        assert conflict.metadata == {"key": "value"}

    def test_roundtrip(self):
        original = PredictedConflict(
            file_path="test.ts",
            conflict_type=ConflictType.RENAME,
            severity=ConflictSeverity.HIGH,
            description="Rename conflict",
            metadata={"old": "a.ts", "new": "b.ts"},
        )
        restored = PredictedConflict.from_dict(original.to_dict())
        assert restored.file_path == original.file_path
        assert restored.conflict_type == original.conflict_type
        assert restored.severity == original.severity


class TestPredictionResult:
    """Tests for PredictionResult dataclass."""

    def test_defaults(self):
        result = PredictionResult()
        assert result.has_conflicts is False
        assert result.conflicts == []
        assert result.affected_files == []
        assert result.commits_behind == 0
        assert result.needs_rebase is False
        assert result.error is None

    def test_critical_count(self):
        result = PredictionResult(
            has_conflicts=True,
            conflicts=[
                PredictedConflict("a.py", ConflictType.CONTENT, ConflictSeverity.CRITICAL, ""),
                PredictedConflict("b.py", ConflictType.CONTENT, ConflictSeverity.LOW, ""),
                PredictedConflict("c.py", ConflictType.CONTENT, ConflictSeverity.HIGH, ""),
            ],
        )
        assert result.critical_count == 2

    def test_to_dict_from_dict_roundtrip(self):
        original = PredictionResult(
            has_conflicts=True,
            conflicts=[
                PredictedConflict("x.py", ConflictType.CONTENT, ConflictSeverity.MEDIUM, "desc"),
            ],
            affected_files=["x.py", "y.py"],
            base_branch="main",
            spec_branch="feature/test",
            commits_behind=3,
            needs_rebase=True,
        )
        restored = PredictionResult.from_dict(original.to_dict())
        assert restored.has_conflicts is True
        assert len(restored.conflicts) == 1
        assert restored.commits_behind == 3
        assert restored.needs_rebase is True
        assert restored.base_branch == "main"


class TestConflictPredictorClassifyLine:
    """Tests for ConflictPredictor._classify_conflict_line."""

    def setup_method(self):
        self.predictor = ConflictPredictor.__new__(ConflictPredictor)

    def test_modify_delete(self):
        assert self.predictor._classify_conflict_line(
            "CONFLICT (modify/delete): file.py deleted in HEAD"
        ) == ConflictType.MODIFY_DELETE

    def test_add_add(self):
        assert self.predictor._classify_conflict_line(
            "CONFLICT (add/add): Merge conflict in new_file.py"
        ) == ConflictType.ADD_ADD

    def test_rename(self):
        assert self.predictor._classify_conflict_line(
            "CONFLICT (rename/rename): Rename conflict for file.py"
        ) == ConflictType.RENAME

    def test_content(self):
        assert self.predictor._classify_conflict_line(
            "CONFLICT (content): Merge conflict in src/app.py"
        ) == ConflictType.CONTENT

    def test_unknown_defaults_to_content(self):
        assert self.predictor._classify_conflict_line(
            "CONFLICT (something_else): weird line"
        ) == ConflictType.CONTENT


class TestConflictPredictorExtractPath:
    """Tests for ConflictPredictor._extract_file_path."""

    def setup_method(self):
        self.predictor = ConflictPredictor.__new__(ConflictPredictor)

    def test_merge_conflict_in_pattern(self):
        path = self.predictor._extract_file_path(
            "CONFLICT (content): Merge conflict in src/app.py"
        )
        assert path == "src/app.py"

    def test_fallback_pattern(self):
        path = self.predictor._extract_file_path(
            "CONFLICT (modify/delete): src/utils.py deleted in HEAD"
        )
        assert path is not None


class TestConflictPredictorSeverity:
    """Tests for ConflictPredictor._assess_severity."""

    def setup_method(self):
        self.predictor = ConflictPredictor.__new__(ConflictPredictor)

    def test_modify_delete_is_high(self):
        assert self.predictor._assess_severity("app.py", ConflictType.MODIFY_DELETE) == ConflictSeverity.HIGH

    def test_rename_is_high(self):
        assert self.predictor._assess_severity("app.py", ConflictType.RENAME) == ConflictSeverity.HIGH

    def test_generated_file_is_low(self):
        assert self.predictor._assess_severity("package-lock.json", ConflictType.CONTENT) == ConflictSeverity.LOW

    def test_config_file_is_medium(self):
        assert self.predictor._assess_severity("package.json", ConflictType.CONTENT) == ConflictSeverity.MEDIUM

    def test_regular_file_is_medium(self):
        assert self.predictor._assess_severity("src/main.py", ConflictType.CONTENT) == ConflictSeverity.MEDIUM


class TestConflictPredictorParseMergeTree:
    """Tests for ConflictPredictor._parse_merge_tree_output."""

    def setup_method(self):
        self.predictor = ConflictPredictor.__new__(ConflictPredictor)

    def test_parses_content_conflict(self):
        output = "CONFLICT (content): Merge conflict in src/app.py\n"
        conflicts = self.predictor._parse_merge_tree_output(output)
        assert len(conflicts) == 1
        assert conflicts[0].file_path == "src/app.py"
        assert conflicts[0].conflict_type == ConflictType.CONTENT

    def test_skips_auto_claude_files(self):
        output = "CONFLICT (content): Merge conflict in .auto-claude/specs/001/plan.json\n"
        conflicts = self.predictor._parse_merge_tree_output(output)
        assert len(conflicts) == 0

    def test_deduplicates_files(self):
        output = (
            "CONFLICT (content): Merge conflict in src/app.py\n"
            "CONFLICT (content): Merge conflict in src/app.py\n"
        )
        conflicts = self.predictor._parse_merge_tree_output(output)
        assert len(conflicts) == 1

    def test_multiple_conflicts(self):
        output = (
            "CONFLICT (content): Merge conflict in src/a.py\n"
            "CONFLICT (add/add): Merge conflict in src/b.py\n"
        )
        conflicts = self.predictor._parse_merge_tree_output(output)
        assert len(conflicts) == 2

    def test_no_conflict_lines(self):
        output = "Auto-merging src/app.py\nSome other output\n"
        conflicts = self.predictor._parse_merge_tree_output(output)
        assert len(conflicts) == 0


class TestConflictPredictorPredict:
    """Tests for ConflictPredictor.predict with mocked git commands."""

    @patch("merge.conflict_predictor.subprocess.run")
    def test_predict_no_conflicts(self, mock_run):
        """predict() returns clean result when no conflicts."""
        # Mock git responses in order: rev-parse, merge-base, rev-list, diff, merge-tree
        mock_run.side_effect = [
            MagicMock(returncode=0, stdout="feature/test\n"),  # current branch
            MagicMock(returncode=0, stdout="abc123\n"),  # merge base
            MagicMock(returncode=0, stdout="5\n"),  # commits ahead
            MagicMock(returncode=0, stdout="src/a.py\nsrc/b.py\n"),  # changed files
            MagicMock(returncode=0, stdout="", stderr=""),  # merge-tree (no conflicts)
        ]

        predictor = ConflictPredictor(
            worktree_path=Path("/tmp/test"), base_branch="main"
        )
        result = predictor.predict()

        assert result.has_conflicts is False
        assert result.spec_branch == "feature/test"
        assert result.commits_behind == 5
        assert result.needs_rebase is True
        assert result.affected_files == ["src/a.py", "src/b.py"]

    @patch("merge.conflict_predictor.subprocess.run")
    def test_predict_with_conflicts(self, mock_run):
        """predict() returns conflicts from merge-tree."""
        mock_run.side_effect = [
            MagicMock(returncode=0, stdout="feature/x\n"),
            MagicMock(returncode=0, stdout="abc123\n"),
            MagicMock(returncode=0, stdout="2\n"),
            MagicMock(returncode=0, stdout="src/app.py\n"),
            MagicMock(
                returncode=1,
                stdout="CONFLICT (content): Merge conflict in src/app.py\n",
                stderr="",
            ),
        ]

        predictor = ConflictPredictor(
            worktree_path=Path("/tmp/test"), base_branch="main"
        )
        result = predictor.predict()

        assert result.has_conflicts is True
        assert len(result.conflicts) == 1
        assert result.conflicts[0].file_path == "src/app.py"

    @patch("merge.conflict_predictor.subprocess.run")
    def test_predict_no_branch(self, mock_run):
        """predict() handles missing branch gracefully."""
        mock_run.side_effect = [
            MagicMock(returncode=1, stdout=""),  # can't get branch
        ]

        predictor = ConflictPredictor(
            worktree_path=Path("/tmp/test"), base_branch="main"
        )
        result = predictor.predict()

        assert result.error is not None
        assert "branch" in result.error.lower()

    @patch("merge.conflict_predictor.subprocess.run")
    def test_predict_no_merge_base(self, mock_run):
        """predict() handles missing merge base."""
        mock_run.side_effect = [
            MagicMock(returncode=0, stdout="feature/x\n"),
            MagicMock(returncode=1, stdout=""),  # no merge base
        ]

        predictor = ConflictPredictor(
            worktree_path=Path("/tmp/test"), base_branch="main"
        )
        result = predictor.predict()

        assert result.error is not None
        assert "merge base" in result.error.lower()


class TestHelperFunctions:
    """Tests for module-level helper functions."""

    def test_is_generated_file(self):
        assert _is_generated_file("package-lock.json") is True
        assert _is_generated_file("yarn.lock") is True
        assert _is_generated_file("dist/bundle.min.js") is True
        assert _is_generated_file("src/app.py") is False

    def test_is_config_file(self):
        assert _is_config_file("package.json") is True
        assert _is_config_file("pyproject.toml") is True
        assert _is_config_file("nested/dir/tsconfig.json") is True
        assert _is_config_file("src/main.py") is False


# =============================================================================
# ResolutionAdvisor Tests
# =============================================================================


class TestResolutionAdvisor:
    """Tests for ResolutionAdvisor."""

    def setup_method(self):
        self.advisor = ResolutionAdvisor()

    def test_advise_empty_list(self):
        advices = self.advisor.advise([])
        assert advices == []

    def test_advise_auto_mergeable_conflict(self):
        """Conflicts already marked auto-mergeable use existing strategy."""
        conflict = ConflictRegion(
            file_path="test.py",
            location="file_top",
            tasks_involved=["t1", "t2"],
            change_types=[ChangeType.ADD_IMPORT, ChangeType.ADD_IMPORT],
            severity=ConflictSeverity.LOW,
            can_auto_merge=True,
            merge_strategy=MergeStrategy.COMBINE_IMPORTS,
            reason="Compatible imports",
        )
        advices = self.advisor.advise([conflict])
        assert len(advices) == 1
        assert advices[0].strategy == MergeStrategy.COMBINE_IMPORTS
        assert "auto-merge" in advices[0].rationale.lower()

    def test_advise_additive_changes(self):
        """All-additive conflicts get additive strategy."""
        conflict = ConflictRegion(
            file_path="test.py",
            location="function:App",
            tasks_involved=["t1", "t2"],
            change_types=[ChangeType.ADD_FUNCTION, ChangeType.ADD_FUNCTION],
            severity=ConflictSeverity.LOW,
            can_auto_merge=False,
        )
        advices = self.advisor.advise([conflict])
        assert len(advices) == 1
        assert advices[0].strategy == MergeStrategy.APPEND_FUNCTIONS
        assert "additive" in advices[0].rationale.lower()

    def test_advise_critical_conflict(self):
        """Critical severity → HUMAN_REQUIRED."""
        conflict = ConflictRegion(
            file_path="core.py",
            location="function:main",
            tasks_involved=["t1", "t2"],
            change_types=[ChangeType.MODIFY_FUNCTION, ChangeType.MODIFY_FUNCTION],
            severity=ConflictSeverity.CRITICAL,
            can_auto_merge=False,
        )
        advices = self.advisor.advise([conflict])
        assert len(advices) == 1
        assert advices[0].strategy == MergeStrategy.HUMAN_REQUIRED
        assert advices[0].complexity_score >= 0.9

    def test_advise_high_severity(self):
        """High severity → AI_REQUIRED."""
        conflict = ConflictRegion(
            file_path="app.py",
            location="function:handler",
            tasks_involved=["t1", "t2"],
            change_types=[ChangeType.MODIFY_FUNCTION, ChangeType.MODIFY_FUNCTION],
            severity=ConflictSeverity.HIGH,
            can_auto_merge=False,
        )
        advices = self.advisor.advise([conflict])
        assert len(advices) == 1
        assert advices[0].strategy == MergeStrategy.AI_REQUIRED

    def test_advise_medium_severity_two_tasks(self):
        """Medium severity with 2 tasks → ORDER_BY_TIME."""
        conflict = ConflictRegion(
            file_path="app.py",
            location="function:process",
            tasks_involved=["t1", "t2"],
            change_types=[ChangeType.MODIFY_VARIABLE, ChangeType.MODIFY_VARIABLE],
            severity=ConflictSeverity.MEDIUM,
            can_auto_merge=False,
        )
        advices = self.advisor.advise([conflict])
        assert len(advices) == 1
        assert advices[0].strategy == MergeStrategy.ORDER_BY_TIME

    def test_advise_medium_severity_many_tasks(self):
        """Medium severity with 3+ tasks → ORDER_BY_DEPENDENCY."""
        conflict = ConflictRegion(
            file_path="app.py",
            location="function:process",
            tasks_involved=["t1", "t2", "t3"],
            change_types=[ChangeType.MODIFY_VARIABLE],
            severity=ConflictSeverity.MEDIUM,
            can_auto_merge=False,
        )
        advices = self.advisor.advise([conflict])
        assert len(advices) == 1
        assert advices[0].strategy == MergeStrategy.ORDER_BY_DEPENDENCY

    def test_advise_hook_additive(self):
        """ADD_HOOK_CALL gets HOOKS_FIRST strategy."""
        conflict = ConflictRegion(
            file_path="App.tsx",
            location="function:App",
            tasks_involved=["t1", "t2"],
            change_types=[ChangeType.ADD_HOOK_CALL, ChangeType.ADD_HOOK_CALL],
            severity=ConflictSeverity.LOW,
            can_auto_merge=False,
        )
        advices = self.advisor.advise([conflict])
        assert advices[0].strategy == MergeStrategy.HOOKS_FIRST

    def test_conflict_advice_to_dict(self):
        """ConflictAdvice.to_dict serializes correctly."""
        conflict = ConflictRegion(
            file_path="test.py",
            location="file_top",
            tasks_involved=["t1"],
            change_types=[ChangeType.ADD_IMPORT],
            severity=ConflictSeverity.LOW,
            can_auto_merge=True,
            merge_strategy=MergeStrategy.COMBINE_IMPORTS,
        )
        advice = ConflictAdvice(
            conflict=conflict,
            strategy=MergeStrategy.COMBINE_IMPORTS,
            rationale="Test rationale",
            complexity_score=0.2,
            recommended_action="Auto-merge",
        )
        d = advice.to_dict()
        assert d["strategy"] == "combine_imports"
        assert d["complexity_score"] == 0.2
        assert d["rationale"] == "Test rationale"

    def test_complexity_increases_with_tasks(self):
        """More tasks increases complexity score."""
        conflict_2 = ConflictRegion(
            file_path="a.py",
            location="func",
            tasks_involved=["t1", "t2"],
            change_types=[ChangeType.MODIFY_FUNCTION],
            severity=ConflictSeverity.MEDIUM,
            can_auto_merge=False,
        )
        conflict_5 = ConflictRegion(
            file_path="a.py",
            location="func",
            tasks_involved=["t1", "t2", "t3", "t4", "t5"],
            change_types=[ChangeType.MODIFY_FUNCTION],
            severity=ConflictSeverity.MEDIUM,
            can_auto_merge=False,
        )
        advice_2 = self.advisor.advise([conflict_2])[0]
        advice_5 = self.advisor.advise([conflict_5])[0]
        assert advice_5.complexity_score >= advice_2.complexity_score


# =============================================================================
# ConflictMonitor Tests
# =============================================================================


class TestConflictReport:
    """Tests for ConflictReport dataclass."""

    def test_defaults(self):
        report = ConflictReport()
        assert report.has_conflicts is False
        assert report.total_conflicts == 0
        assert report.worktrees_checked == 0

    def test_has_conflicts_property(self):
        report = ConflictReport(worktrees_with_conflicts=1)
        assert report.has_conflicts is True

    def test_total_conflicts(self):
        status = WorktreeConflictStatus(
            spec_name="test",
            worktree_path="/tmp/wt",
            prediction=PredictionResult(
                has_conflicts=True,
                conflicts=[
                    PredictedConflict("a.py", ConflictType.CONTENT, ConflictSeverity.MEDIUM, ""),
                    PredictedConflict("b.py", ConflictType.CONTENT, ConflictSeverity.LOW, ""),
                ],
            ),
            checked_at="2026-01-01T00:00:00",
        )
        report = ConflictReport(
            worktrees_checked=1,
            worktrees_with_conflicts=1,
            statuses=[status],
        )
        assert report.total_conflicts == 2

    def test_roundtrip(self):
        report = ConflictReport(
            timestamp="2026-01-01T00:00:00",
            worktrees_checked=2,
            worktrees_with_conflicts=1,
            errors=["some error"],
        )
        restored = ConflictReport.from_dict(report.to_dict())
        assert restored.timestamp == report.timestamp
        assert restored.worktrees_checked == 2
        assert restored.errors == ["some error"]


class TestConflictMonitorLifecycle:
    """Tests for ConflictMonitor start/stop/is_running."""

    def test_start_stop(self, tmp_path):
        monitor = ConflictMonitor(project_dir=tmp_path, check_interval=9999)
        assert monitor.is_running is False

        monitor.start()
        assert monitor.is_running is True

        monitor.stop()
        assert monitor.is_running is False

    def test_double_start_is_safe(self, tmp_path):
        monitor = ConflictMonitor(project_dir=tmp_path, check_interval=9999)
        monitor.start()
        monitor.start()  # should not raise
        assert monitor.is_running is True
        monitor.stop()

    def test_stop_without_start(self, tmp_path):
        monitor = ConflictMonitor(project_dir=tmp_path)
        monitor.stop()  # should not raise
        assert monitor.is_running is False

    def test_latest_report_initially_none(self, tmp_path):
        monitor = ConflictMonitor(project_dir=tmp_path)
        assert monitor.latest_report is None


class TestConflictMonitorCheckNow:
    """Tests for ConflictMonitor.check_now with mocked worktrees."""

    def test_check_now_no_worktrees(self, tmp_path):
        """check_now returns empty report when no worktrees exist."""
        monitor = ConflictMonitor(project_dir=tmp_path, base_branch="main")
        report = monitor.check_now()

        assert report.worktrees_checked == 0
        assert report.has_conflicts is False
        assert report.timestamp != ""

    @patch.object(ConflictPredictor, "predict")
    def test_check_now_with_worktree(self, mock_predict, tmp_path):
        """check_now runs predictor on discovered worktrees."""
        # Create fake worktree directory with .git marker
        wt_dir = tmp_path / ".auto-claude" / "worktrees" / "tasks" / "001-feature"
        wt_dir.mkdir(parents=True)
        (wt_dir / ".git").write_text("gitdir: /path/to/git")

        mock_predict.return_value = PredictionResult(has_conflicts=False)

        monitor = ConflictMonitor(project_dir=tmp_path, base_branch="main")
        report = monitor.check_now()

        assert report.worktrees_checked == 1
        assert report.has_conflicts is False
        assert len(report.statuses) == 1
        assert report.statuses[0].spec_name == "001-feature"

    @patch.object(ConflictPredictor, "predict")
    def test_check_now_with_conflicts(self, mock_predict, tmp_path):
        """check_now correctly reports conflicts."""
        wt_dir = tmp_path / ".auto-claude" / "worktrees" / "tasks" / "002-fix"
        wt_dir.mkdir(parents=True)
        (wt_dir / ".git").write_text("gitdir: /path/to/git")

        mock_predict.return_value = PredictionResult(
            has_conflicts=True,
            conflicts=[
                PredictedConflict("x.py", ConflictType.CONTENT, ConflictSeverity.HIGH, "conflict"),
            ],
        )

        monitor = ConflictMonitor(project_dir=tmp_path, base_branch="main")
        report = monitor.check_now()

        assert report.worktrees_with_conflicts == 1
        assert report.has_conflicts is True
        assert monitor.latest_report is not None

    @patch.object(ConflictPredictor, "predict", side_effect=Exception("git error"))
    def test_check_now_handles_error(self, mock_predict, tmp_path):
        """check_now records errors without crashing."""
        wt_dir = tmp_path / ".auto-claude" / "worktrees" / "tasks" / "003-err"
        wt_dir.mkdir(parents=True)
        (wt_dir / ".git").write_text("gitdir: /path/to/git")

        monitor = ConflictMonitor(project_dir=tmp_path, base_branch="main")
        report = monitor.check_now()

        assert len(report.errors) == 1
        assert "003-err" in report.errors[0]


class TestConflictMonitorReportPersistence:
    """Tests for report save/load."""

    def test_save_and_load_report(self, tmp_path):
        """Reports are saved to disk and can be loaded."""
        monitor = ConflictMonitor(project_dir=tmp_path, base_branch="main")
        report = monitor.check_now()

        loaded = ConflictMonitor.load_latest_report(tmp_path)
        assert loaded is not None
        assert loaded.timestamp == report.timestamp

    def test_load_missing_report(self, tmp_path):
        """load_latest_report returns None when no report exists."""
        assert ConflictMonitor.load_latest_report(tmp_path) is None

    def test_report_files_created(self, tmp_path):
        """Both latest.json and timestamped report are created."""
        monitor = ConflictMonitor(project_dir=tmp_path, base_branch="main")
        monitor.check_now()

        reports_dir = tmp_path / ".auto-claude" / "conflict_reports"
        assert (reports_dir / "latest.json").exists()
        # Should also have a timestamped report
        report_files = list(reports_dir.glob("report_*.json"))
        assert len(report_files) >= 1
