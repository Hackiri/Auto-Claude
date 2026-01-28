#!/usr/bin/env python3
"""
Tests for Ralph Wiggum Iterative Loop Technique
================================================

Tests the ralph_loop package functionality including:
- Configuration loading and validation
- Completion promises definition and evaluation
- Retry strategies with approach variation
"""

import json
import pytest
from pathlib import Path
from unittest.mock import MagicMock, patch

# Import the ralph_loop modules
from ralph_loop.config import (
    RalphLoopConfig,
    DEFAULT_RALPH_CONFIG,
    VALID_RETRY_STRATEGIES,
    get_default_config,
    load_ralph_config_from_metadata,
    load_ralph_config,
    is_ralph_loop_enabled,
    get_max_iterations,
    _normalize_config,
)
from ralph_loop.promises import (
    PromiseType,
    CompletionPromise,
    PromiseResult,
    evaluate_promise,
    evaluate_all_promises,
    load_promises_from_plan,
    get_default_promises,
)
from ralph_loop.strategy import (
    RetryStrategyType,
    ApproachCategory,
    ApproachSuggestion,
    RetryDecision,
    RetryStrategy,
    get_varied_approach,
    get_retry_hints,
    create_retry_strategy,
)


# =============================================================================
# CONFIGURATION TESTS
# =============================================================================


class TestDefaultConfig:
    """Tests for default configuration values."""

    def test_get_default_config_returns_dict(self):
        """get_default_config returns a RalphLoopConfig dict."""
        config = get_default_config()

        assert isinstance(config, dict)
        assert "enabled" in config
        assert "max_coder_iterations" in config
        assert "max_qa_iterations" in config

    def test_get_default_config_values(self):
        """Default config has expected values."""
        config = get_default_config()

        assert config["enabled"] is False
        assert config["max_coder_iterations"] == 100
        assert config["max_qa_iterations"] == 50
        assert config["completion_promise_timeout"] == 300
        assert config["retry_strategy"] == "adaptive"
        assert config["overnight_mode"] is False

    def test_get_default_config_returns_copy(self):
        """get_default_config returns a copy, not the original."""
        config1 = get_default_config()
        config2 = get_default_config()

        config1["enabled"] = True
        assert config2["enabled"] is False

    def test_valid_retry_strategies_set(self):
        """VALID_RETRY_STRATEGIES contains expected values."""
        assert "conservative" in VALID_RETRY_STRATEGIES
        assert "aggressive" in VALID_RETRY_STRATEGIES
        assert "adaptive" in VALID_RETRY_STRATEGIES
        assert len(VALID_RETRY_STRATEGIES) == 3


class TestLoadRalphConfigFromMetadata:
    """Tests for loading config from task_metadata.json."""

    def test_load_from_existing_metadata(self, spec_dir: Path):
        """Loads Ralph config from task_metadata.json."""
        metadata = {
            "ralphLoop": {
                "enabled": True,
                "max_coder_iterations": 200,
                "retry_strategy": "aggressive",
            }
        }
        (spec_dir / "task_metadata.json").write_text(json.dumps(metadata))

        config = load_ralph_config_from_metadata(spec_dir)

        assert config is not None
        assert config["enabled"] is True
        assert config["max_coder_iterations"] == 200
        assert config["retry_strategy"] == "aggressive"

    def test_load_missing_metadata_returns_none(self, spec_dir: Path):
        """Returns None when task_metadata.json doesn't exist."""
        config = load_ralph_config_from_metadata(spec_dir)
        assert config is None

    def test_load_invalid_json_returns_none(self, spec_dir: Path):
        """Returns None for invalid JSON."""
        (spec_dir / "task_metadata.json").write_text("{ invalid json }")

        config = load_ralph_config_from_metadata(spec_dir)
        assert config is None

    def test_load_metadata_without_ralph_loop_returns_none(self, spec_dir: Path):
        """Returns None when ralphLoop key is missing."""
        metadata = {"other_key": "value"}
        (spec_dir / "task_metadata.json").write_text(json.dumps(metadata))

        config = load_ralph_config_from_metadata(spec_dir)
        assert config is None


class TestNormalizeConfig:
    """Tests for configuration normalization."""

    def test_normalize_boolean_enabled(self):
        """Normalizes enabled to boolean."""
        config = _normalize_config({"enabled": 1})
        assert config["enabled"] is True

        config = _normalize_config({"enabled": 0})
        assert config["enabled"] is False

        config = _normalize_config({"enabled": "true"})
        assert config["enabled"] is True

    def test_normalize_valid_max_iterations(self):
        """Accepts valid positive integer for max iterations."""
        config = _normalize_config({"max_coder_iterations": 50})
        assert config["max_coder_iterations"] == 50

    def test_normalize_invalid_max_iterations_excluded(self):
        """Invalid max_iterations values are excluded."""
        config = _normalize_config({"max_coder_iterations": -5})
        assert "max_coder_iterations" not in config

        config = _normalize_config({"max_coder_iterations": 0})
        assert "max_coder_iterations" not in config

    def test_normalize_valid_retry_strategy(self):
        """Accepts valid retry strategy values."""
        for strategy in VALID_RETRY_STRATEGIES:
            config = _normalize_config({"retry_strategy": strategy})
            assert config["retry_strategy"] == strategy

    def test_normalize_invalid_retry_strategy_excluded(self):
        """Invalid retry_strategy values are excluded."""
        config = _normalize_config({"retry_strategy": "invalid"})
        assert "retry_strategy" not in config

    def test_normalize_overnight_mode(self):
        """Normalizes overnight_mode to boolean."""
        config = _normalize_config({"overnight_mode": True})
        assert config["overnight_mode"] is True


class TestLoadRalphConfig:
    """Tests for combined config loading with CLI overrides."""

    def test_load_defaults_only(self, spec_dir: Path):
        """Returns defaults when no metadata or CLI args."""
        config = load_ralph_config(spec_dir)

        assert config["enabled"] is False
        assert config["max_coder_iterations"] == 100

    def test_cli_override_enabled(self, spec_dir: Path):
        """CLI enabled flag overrides defaults."""
        config = load_ralph_config(spec_dir, cli_enabled=True)
        assert config["enabled"] is True

    def test_cli_override_max_iterations(self, spec_dir: Path):
        """CLI max_iterations overrides defaults."""
        config = load_ralph_config(spec_dir, cli_max_iterations=250)
        assert config["max_coder_iterations"] == 250

    def test_cli_override_overnight(self, spec_dir: Path):
        """CLI overnight flag enables ralph loop too."""
        config = load_ralph_config(spec_dir, cli_overnight=True)

        assert config["overnight_mode"] is True
        assert config["enabled"] is True  # Overnight implies enabled

    def test_cli_overrides_metadata(self, spec_dir: Path):
        """CLI values take precedence over metadata."""
        metadata = {"ralphLoop": {"enabled": True, "max_coder_iterations": 50}}
        (spec_dir / "task_metadata.json").write_text(json.dumps(metadata))

        config = load_ralph_config(
            spec_dir, cli_enabled=False, cli_max_iterations=300
        )

        assert config["enabled"] is False
        assert config["max_coder_iterations"] == 300

    def test_metadata_merges_with_defaults(self, spec_dir: Path):
        """Metadata values merge with defaults."""
        metadata = {"ralphLoop": {"enabled": True}}
        (spec_dir / "task_metadata.json").write_text(json.dumps(metadata))

        config = load_ralph_config(spec_dir)

        assert config["enabled"] is True
        assert config["max_coder_iterations"] == 100  # Default preserved

    def test_invalid_cli_max_iterations_ignored(self, spec_dir: Path):
        """Invalid CLI max_iterations is ignored."""
        config = load_ralph_config(spec_dir, cli_max_iterations=-10)
        assert config["max_coder_iterations"] == 100  # Default


class TestIsRalphLoopEnabled:
    """Tests for is_ralph_loop_enabled helper."""

    def test_returns_true_when_enabled(self):
        """Returns True when enabled is True."""
        config: RalphLoopConfig = {"enabled": True}
        assert is_ralph_loop_enabled(config) is True

    def test_returns_false_when_disabled(self):
        """Returns False when enabled is False."""
        config: RalphLoopConfig = {"enabled": False}
        assert is_ralph_loop_enabled(config) is False

    def test_returns_default_when_missing(self):
        """Returns default when enabled key is missing."""
        config: RalphLoopConfig = {}
        assert is_ralph_loop_enabled(config) is False


class TestGetMaxIterations:
    """Tests for get_max_iterations helper."""

    def test_get_coder_iterations(self):
        """Returns coder iterations for 'coder' phase."""
        config: RalphLoopConfig = {"max_coder_iterations": 75}
        assert get_max_iterations(config, "coder") == 75

    def test_get_qa_iterations(self):
        """Returns QA iterations for 'qa' phase."""
        config: RalphLoopConfig = {"max_qa_iterations": 25}
        assert get_max_iterations(config, "qa") == 25

    def test_unknown_phase_returns_coder_default(self):
        """Unknown phase returns coder iterations."""
        config: RalphLoopConfig = {"max_coder_iterations": 80}
        assert get_max_iterations(config, "unknown") == 80

    def test_missing_config_returns_default(self):
        """Returns default when config key is missing."""
        config: RalphLoopConfig = {}
        assert get_max_iterations(config, "coder") == 100


# =============================================================================
# PROMISES TESTS
# =============================================================================


class TestPromiseType:
    """Tests for PromiseType enum."""

    def test_all_promise_types_defined(self):
        """All expected promise types are defined."""
        assert PromiseType.TEST_PASS.value == "test_pass"
        assert PromiseType.BUILD_SUCCESS.value == "build_success"
        assert PromiseType.FILE_EXISTS.value == "file_exists"
        assert PromiseType.COMMAND_SUCCESS.value == "command_success"
        assert PromiseType.QA_SIGNOFF.value == "qa_signoff"
        assert PromiseType.SUBTASKS_COMPLETE.value == "subtasks_complete"
        assert PromiseType.CUSTOM.value == "custom"


class TestCompletionPromise:
    """Tests for CompletionPromise dataclass."""

    def test_create_promise(self):
        """Creates a CompletionPromise with all fields."""
        promise = CompletionPromise(
            name="Tests Pass",
            promise_type=PromiseType.TEST_PASS,
            check_params={"command": "pytest"},
            required=True,
            description="All tests must pass",
        )

        assert promise.name == "Tests Pass"
        assert promise.promise_type == PromiseType.TEST_PASS
        assert promise.check_params == {"command": "pytest"}
        assert promise.required is True
        assert promise.description == "All tests must pass"

    def test_promise_defaults(self):
        """CompletionPromise has sensible defaults."""
        promise = CompletionPromise(
            name="Test",
            promise_type=PromiseType.FILE_EXISTS,
        )

        assert promise.check_params == {}
        assert promise.required is True
        assert promise.description == ""

    def test_promise_to_dict(self):
        """to_dict serializes promise correctly."""
        promise = CompletionPromise(
            name="Tests Pass",
            promise_type=PromiseType.TEST_PASS,
            check_params={"timeout": 300},
            required=False,
        )

        data = promise.to_dict()

        assert data["name"] == "Tests Pass"
        assert data["promise_type"] == "test_pass"
        assert data["check_params"] == {"timeout": 300}
        assert data["required"] is False

    def test_promise_from_dict(self):
        """from_dict deserializes promise correctly."""
        data = {
            "name": "Build Success",
            "promise_type": "build_success",
            "check_params": {"command": "npm build"},
            "required": True,
            "description": "Build must complete",
        }

        promise = CompletionPromise.from_dict(data)

        assert promise.name == "Build Success"
        assert promise.promise_type == PromiseType.BUILD_SUCCESS
        assert promise.check_params == {"command": "npm build"}

    def test_promise_roundtrip(self):
        """Promise survives serialization roundtrip."""
        original = CompletionPromise(
            name="File Check",
            promise_type=PromiseType.FILE_EXISTS,
            check_params={"files": ["README.md"]},
            required=True,
        )

        data = original.to_dict()
        restored = CompletionPromise.from_dict(data)

        assert restored.name == original.name
        assert restored.promise_type == original.promise_type
        assert restored.check_params == original.check_params


class TestPromiseResult:
    """Tests for PromiseResult dataclass."""

    def test_create_result(self):
        """Creates a PromiseResult with all fields."""
        promise = CompletionPromise(
            name="Test", promise_type=PromiseType.TEST_PASS
        )
        result = PromiseResult(
            promise=promise,
            passed=True,
            message="All tests passed",
            details={"count": 42},
        )

        assert result.promise == promise
        assert result.passed is True
        assert result.message == "All tests passed"
        assert result.details == {"count": 42}

    def test_result_defaults(self):
        """PromiseResult has sensible defaults."""
        promise = CompletionPromise(
            name="Test", promise_type=PromiseType.TEST_PASS
        )
        result = PromiseResult(
            promise=promise,
            passed=False,
            message="Failed",
        )

        assert result.details == {}


class TestEvaluateFileExists:
    """Tests for file_exists promise evaluation."""

    def test_file_exists_single_file_found(self, spec_dir: Path, project_dir: Path):
        """File exists check passes when file is found."""
        (project_dir / "README.md").write_text("# Test")

        promise = CompletionPromise(
            name="README exists",
            promise_type=PromiseType.FILE_EXISTS,
            check_params={"files": ["README.md"]},
        )

        result = evaluate_promise(promise, spec_dir, project_dir)

        assert result.passed is True
        assert "README.md" in result.details["existing"]

    def test_file_exists_single_file_missing(self, spec_dir: Path, project_dir: Path):
        """File exists check fails when file is missing."""
        promise = CompletionPromise(
            name="Missing file",
            promise_type=PromiseType.FILE_EXISTS,
            check_params={"files": ["nonexistent.txt"]},
        )

        result = evaluate_promise(promise, spec_dir, project_dir)

        assert result.passed is False
        assert "nonexistent.txt" in result.details["missing"]

    def test_file_exists_all_required(self, spec_dir: Path, project_dir: Path):
        """All required mode requires all files to exist."""
        (project_dir / "file1.txt").write_text("1")
        # file2.txt is missing

        promise = CompletionPromise(
            name="All files",
            promise_type=PromiseType.FILE_EXISTS,
            check_params={
                "files": ["file1.txt", "file2.txt"],
                "all_required": True,
            },
        )

        result = evaluate_promise(promise, spec_dir, project_dir)

        assert result.passed is False
        assert "file2.txt" in result.details["missing"]

    def test_file_exists_any_required(self, spec_dir: Path, project_dir: Path):
        """Any required mode passes if any file exists."""
        (project_dir / "file1.txt").write_text("1")
        # file2.txt is missing

        promise = CompletionPromise(
            name="Any file",
            promise_type=PromiseType.FILE_EXISTS,
            check_params={
                "files": ["file1.txt", "file2.txt"],
                "all_required": False,
            },
        )

        result = evaluate_promise(promise, spec_dir, project_dir)

        assert result.passed is True

    def test_file_exists_no_files_fails(self, spec_dir: Path, project_dir: Path):
        """Empty files list fails."""
        promise = CompletionPromise(
            name="No files",
            promise_type=PromiseType.FILE_EXISTS,
            check_params={"files": []},
        )

        result = evaluate_promise(promise, spec_dir, project_dir)

        assert result.passed is False
        assert "No files" in result.message


class TestEvaluateQASignoff:
    """Tests for qa_signoff promise evaluation."""

    def test_qa_signoff_approved(self, spec_dir: Path, project_dir: Path):
        """QA signoff passes when status is approved."""
        plan = {"qa_signoff": {"status": "approved"}}
        (spec_dir / "implementation_plan.json").write_text(json.dumps(plan))

        promise = CompletionPromise(
            name="QA Approved",
            promise_type=PromiseType.QA_SIGNOFF,
        )

        result = evaluate_promise(promise, spec_dir, project_dir)

        assert result.passed is True

    def test_qa_signoff_rejected(self, spec_dir: Path, project_dir: Path):
        """QA signoff fails when status is rejected."""
        plan = {"qa_signoff": {"status": "rejected"}}
        (spec_dir / "implementation_plan.json").write_text(json.dumps(plan))

        promise = CompletionPromise(
            name="QA Check",
            promise_type=PromiseType.QA_SIGNOFF,
        )

        result = evaluate_promise(promise, spec_dir, project_dir)

        assert result.passed is False

    def test_qa_signoff_missing_plan(self, spec_dir: Path, project_dir: Path):
        """QA signoff fails when plan is missing."""
        promise = CompletionPromise(
            name="QA Check",
            promise_type=PromiseType.QA_SIGNOFF,
        )

        result = evaluate_promise(promise, spec_dir, project_dir)

        assert result.passed is False
        assert "not found" in result.message


class TestEvaluateSubtasksComplete:
    """Tests for subtasks_complete promise evaluation."""

    def test_subtasks_all_complete(self, spec_dir: Path, project_dir: Path):
        """Passes when all subtasks are completed."""
        plan = {
            "phases": [
                {
                    "id": "phase-1",
                    "subtasks": [
                        {"id": "s1", "status": "completed"},
                        {"id": "s2", "status": "completed"},
                    ],
                }
            ]
        }
        (spec_dir / "implementation_plan.json").write_text(json.dumps(plan))

        promise = CompletionPromise(
            name="Subtasks",
            promise_type=PromiseType.SUBTASKS_COMPLETE,
        )

        result = evaluate_promise(promise, spec_dir, project_dir)

        assert result.passed is True
        assert result.details["total"] == 2
        assert result.details["completed"] == 2

    def test_subtasks_incomplete(self, spec_dir: Path, project_dir: Path):
        """Fails when some subtasks are not completed."""
        plan = {
            "phases": [
                {
                    "id": "phase-1",
                    "subtasks": [
                        {"id": "s1", "status": "completed"},
                        {"id": "s2", "status": "pending"},
                    ],
                }
            ]
        }
        (spec_dir / "implementation_plan.json").write_text(json.dumps(plan))

        promise = CompletionPromise(
            name="Subtasks",
            promise_type=PromiseType.SUBTASKS_COMPLETE,
        )

        result = evaluate_promise(promise, spec_dir, project_dir)

        assert result.passed is False
        assert result.details["completed"] == 1
        assert len(result.details["incomplete"]) == 1


class TestEvaluateAllPromises:
    """Tests for evaluating multiple promises."""

    def test_all_required_pass(self, spec_dir: Path, project_dir: Path):
        """Returns True when all required promises pass."""
        (project_dir / "file1.txt").write_text("1")
        (project_dir / "file2.txt").write_text("2")

        promises = [
            CompletionPromise(
                name="File 1",
                promise_type=PromiseType.FILE_EXISTS,
                check_params={"files": ["file1.txt"]},
                required=True,
            ),
            CompletionPromise(
                name="File 2",
                promise_type=PromiseType.FILE_EXISTS,
                check_params={"files": ["file2.txt"]},
                required=True,
            ),
        ]

        all_passed, results = evaluate_all_promises(promises, spec_dir, project_dir)

        assert all_passed is True
        assert len(results) == 2
        assert all(r.passed for r in results)

    def test_required_failure_fails_all(self, spec_dir: Path, project_dir: Path):
        """Returns False when a required promise fails."""
        (project_dir / "file1.txt").write_text("1")

        promises = [
            CompletionPromise(
                name="File 1",
                promise_type=PromiseType.FILE_EXISTS,
                check_params={"files": ["file1.txt"]},
                required=True,
            ),
            CompletionPromise(
                name="File 2",
                promise_type=PromiseType.FILE_EXISTS,
                check_params={"files": ["missing.txt"]},
                required=True,
            ),
        ]

        all_passed, results = evaluate_all_promises(promises, spec_dir, project_dir)

        assert all_passed is False

    def test_optional_failure_does_not_fail_all(
        self, spec_dir: Path, project_dir: Path
    ):
        """Optional promise failure doesn't fail all."""
        (project_dir / "required.txt").write_text("1")

        promises = [
            CompletionPromise(
                name="Required",
                promise_type=PromiseType.FILE_EXISTS,
                check_params={"files": ["required.txt"]},
                required=True,
            ),
            CompletionPromise(
                name="Optional",
                promise_type=PromiseType.FILE_EXISTS,
                check_params={"files": ["optional.txt"]},
                required=False,
            ),
        ]

        all_passed, results = evaluate_all_promises(promises, spec_dir, project_dir)

        assert all_passed is True


class TestLoadPromisesFromPlan:
    """Tests for loading promises from implementation_plan.json."""

    def test_load_promises_from_plan(self, spec_dir: Path):
        """Loads promises from plan file."""
        plan = {
            "completion_promises": [
                {
                    "name": "Tests Pass",
                    "promise_type": "test_pass",
                    "check_params": {"command": "pytest"},
                    "required": True,
                }
            ]
        }
        (spec_dir / "implementation_plan.json").write_text(json.dumps(plan))

        promises = load_promises_from_plan(spec_dir)

        assert len(promises) == 1
        assert promises[0].name == "Tests Pass"
        assert promises[0].promise_type == PromiseType.TEST_PASS

    def test_load_empty_when_no_promises(self, spec_dir: Path):
        """Returns empty list when no promises in plan."""
        plan = {"phases": []}
        (spec_dir / "implementation_plan.json").write_text(json.dumps(plan))

        promises = load_promises_from_plan(spec_dir)

        assert promises == []

    def test_load_empty_when_no_plan(self, spec_dir: Path):
        """Returns empty list when plan doesn't exist."""
        promises = load_promises_from_plan(spec_dir)
        assert promises == []


class TestGetDefaultPromises:
    """Tests for default promise generation."""

    def test_get_default_promises(self):
        """Returns default promise list."""
        promises = get_default_promises()

        assert len(promises) >= 1
        assert promises[0].promise_type == PromiseType.SUBTASKS_COMPLETE
        assert promises[0].required is True


# =============================================================================
# STRATEGY TESTS
# =============================================================================


class TestRetryStrategyType:
    """Tests for RetryStrategyType enum."""

    def test_all_strategy_types_defined(self):
        """All expected strategy types are defined."""
        assert RetryStrategyType.CONSERVATIVE.value == "conservative"
        assert RetryStrategyType.AGGRESSIVE.value == "aggressive"
        assert RetryStrategyType.ADAPTIVE.value == "adaptive"


class TestApproachCategory:
    """Tests for ApproachCategory enum."""

    def test_all_approach_categories_defined(self):
        """All expected approach categories are defined."""
        assert ApproachCategory.SIMPLIFY.value == "simplify"
        assert ApproachCategory.ALTERNATIVE.value == "alternative"
        assert ApproachCategory.DECOMPOSE.value == "decompose"
        assert ApproachCategory.REFACTOR.value == "refactor"
        assert ApproachCategory.WORKAROUND.value == "workaround"
        assert ApproachCategory.DEBUG.value == "debug"


class TestApproachSuggestion:
    """Tests for ApproachSuggestion dataclass."""

    def test_create_suggestion(self):
        """Creates an ApproachSuggestion with all fields."""
        suggestion = ApproachSuggestion(
            category=ApproachCategory.SIMPLIFY,
            description="Try a simpler approach",
            hints=["Remove complexity", "Start minimal"],
            priority=2,
        )

        assert suggestion.category == ApproachCategory.SIMPLIFY
        assert suggestion.description == "Try a simpler approach"
        assert len(suggestion.hints) == 2
        assert suggestion.priority == 2

    def test_suggestion_defaults(self):
        """ApproachSuggestion has sensible defaults."""
        suggestion = ApproachSuggestion(
            category=ApproachCategory.DEBUG,
            description="Debug first",
        )

        assert suggestion.hints == []
        assert suggestion.priority == 5

    def test_suggestion_to_dict(self):
        """to_dict serializes suggestion correctly."""
        suggestion = ApproachSuggestion(
            category=ApproachCategory.ALTERNATIVE,
            description="Use different library",
            hints=["Try lodash"],
            priority=3,
        )

        data = suggestion.to_dict()

        assert data["category"] == "alternative"
        assert data["description"] == "Use different library"
        assert data["hints"] == ["Try lodash"]


class TestRetryDecision:
    """Tests for RetryDecision dataclass."""

    def test_create_decision_should_retry(self):
        """Creates a RetryDecision for retry."""
        suggestion = ApproachSuggestion(
            category=ApproachCategory.SIMPLIFY,
            description="Simplify",
        )
        decision = RetryDecision(
            should_retry=True,
            delay_seconds=5.0,
            approach=suggestion,
            reason="Retry attempt 1/3",
            attempt_number=1,
        )

        assert decision.should_retry is True
        assert decision.delay_seconds == 5.0
        assert decision.approach is not None
        assert decision.attempt_number == 1

    def test_create_decision_no_retry(self):
        """Creates a RetryDecision for no retry."""
        decision = RetryDecision(
            should_retry=False,
            delay_seconds=0,
            approach=None,
            reason="Max retries exceeded",
            attempt_number=4,
        )

        assert decision.should_retry is False
        assert decision.approach is None


class TestRetryStrategy:
    """Tests for RetryStrategy class."""

    def test_create_strategy_defaults(self):
        """Creates strategy with default adaptive type."""
        strategy = RetryStrategy()

        assert strategy.strategy_type == RetryStrategyType.ADAPTIVE
        assert strategy.max_retries == 4
        assert strategy.base_delay == 2.0

    def test_create_conservative_strategy(self):
        """Creates conservative strategy with correct limits."""
        strategy = RetryStrategy(strategy_type=RetryStrategyType.CONSERVATIVE)

        assert strategy.strategy_type == RetryStrategyType.CONSERVATIVE
        assert strategy.max_retries == 3
        assert strategy.base_delay == 5.0

    def test_create_aggressive_strategy(self):
        """Creates aggressive strategy with correct limits."""
        strategy = RetryStrategy(strategy_type=RetryStrategyType.AGGRESSIVE)

        assert strategy.strategy_type == RetryStrategyType.AGGRESSIVE
        assert strategy.max_retries == 5
        assert strategy.base_delay == 1.0

    def test_create_strategy_from_string(self):
        """Creates strategy from string type."""
        strategy = RetryStrategy(strategy_type="conservative")

        assert strategy.strategy_type == RetryStrategyType.CONSERVATIVE

    def test_create_strategy_invalid_string_falls_back(self):
        """Invalid string type falls back to adaptive."""
        strategy = RetryStrategy(strategy_type="invalid")

        assert strategy.strategy_type == RetryStrategyType.ADAPTIVE

    def test_create_strategy_with_overrides(self):
        """Creates strategy with custom overrides."""
        strategy = RetryStrategy(
            strategy_type="conservative",
            max_retries=10,
            base_delay=1.0,
        )

        assert strategy.max_retries == 10
        assert strategy.base_delay == 1.0

    def test_should_retry_under_max(self):
        """should_retry returns True under max retries."""
        strategy = RetryStrategy(max_retries=3)

        decision = strategy.should_retry(attempt_count=1)

        assert decision.should_retry is True
        assert decision.attempt_number == 2
        assert decision.approach is not None

    def test_should_retry_at_max(self):
        """should_retry returns False at max retries."""
        strategy = RetryStrategy(max_retries=3)

        decision = strategy.should_retry(attempt_count=3)

        assert decision.should_retry is False
        assert "exceeded" in decision.reason

    def test_delay_increases_with_attempts(self):
        """Delay increases with backoff factor."""
        strategy = RetryStrategy(base_delay=2.0)

        decision1 = strategy.should_retry(attempt_count=0)
        decision2 = strategy.should_retry(attempt_count=1)

        assert decision2.delay_seconds > decision1.delay_seconds

    def test_delay_capped_at_max(self):
        """Delay is capped at max_delay."""
        strategy = RetryStrategy(base_delay=100.0)

        decision = strategy.should_retry(attempt_count=5)

        assert decision.delay_seconds <= strategy.max_delay

    def test_reset_clears_used_approaches(self):
        """reset() clears the used approaches list."""
        strategy = RetryStrategy()

        # Generate some approaches
        strategy.should_retry(attempt_count=0)
        strategy.should_retry(attempt_count=1)

        assert len(strategy._used_approaches) > 0

        strategy.reset()

        assert len(strategy._used_approaches) == 0

    def test_get_strategy_info(self):
        """get_strategy_info returns correct information."""
        strategy = RetryStrategy(
            strategy_type="conservative",
            max_retries=5,
            base_delay=10.0,
        )

        info = strategy.get_strategy_info()

        assert info["type"] == "conservative"
        assert info["max_retries"] == 5
        assert info["base_delay"] == 10.0


class TestApproachSuggestions:
    """Tests for approach suggestion generation."""

    def test_first_attempt_suggests_debug(self):
        """First retry attempt suggests debug approach."""
        strategy = RetryStrategy()

        decision = strategy.should_retry(attempt_count=1)

        assert decision.approach.category == ApproachCategory.DEBUG

    def test_complexity_error_suggests_simplify(self):
        """Complexity-related error suggests simplify approach."""
        strategy = RetryStrategy()

        decision = strategy.should_retry(
            attempt_count=2,
            error="Token limit exceeded, context too large",
        )

        assert decision.approach.category == ApproachCategory.SIMPLIFY

    def test_import_error_suggests_alternative(self):
        """Import-related error suggests alternative approach."""
        strategy = RetryStrategy()

        decision = strategy.should_retry(
            attempt_count=2,
            error="ModuleNotFoundError: cannot find module 'xyz'",
        )

        assert decision.approach.category == ApproachCategory.ALTERNATIVE

    def test_syntax_error_suggests_refactor(self):
        """Syntax-related error suggests refactor approach."""
        strategy = RetryStrategy()

        decision = strategy.should_retry(
            attempt_count=2,
            error="SyntaxError: unexpected indentation",
        )

        assert decision.approach.category == ApproachCategory.REFACTOR


class TestAdaptiveStrategy:
    """Tests for adaptive strategy behavior."""

    def test_adaptive_increases_delay_for_consecutive_failures(self):
        """Adaptive strategy increases delay for many consecutive failures."""
        strategy = RetryStrategy(strategy_type="adaptive")

        decision1 = strategy.should_retry(attempt_count=1, consecutive_failures=1)
        decision2 = strategy.should_retry(attempt_count=1, consecutive_failures=5)

        assert decision2.delay_seconds > decision1.delay_seconds

    def test_adaptive_handles_rate_limit_error(self):
        """Adaptive strategy adds extra delay for rate limit errors."""
        strategy = RetryStrategy(strategy_type="adaptive")

        decision = strategy.should_retry(
            attempt_count=1,
            error="Rate limit exceeded, 429 Too Many Requests",
        )

        assert decision.delay_seconds >= 30.0


class TestConvenienceFunctions:
    """Tests for convenience functions."""

    def test_get_varied_approach(self):
        """get_varied_approach returns an ApproachSuggestion."""
        approach = get_varied_approach(
            attempt_count=2,
            error="Test failure",
            strategy="aggressive",
        )

        assert isinstance(approach, ApproachSuggestion)
        assert approach.category is not None
        assert approach.description != ""

    def test_get_varied_approach_with_previous(self):
        """get_varied_approach considers previous approaches."""
        approach = get_varied_approach(
            attempt_count=3,
            previous_approaches=["Simplified the code", "Used alternative library"],
            strategy="adaptive",
        )

        assert isinstance(approach, ApproachSuggestion)

    def test_get_retry_hints(self):
        """get_retry_hints returns list of hint strings."""
        hints = get_retry_hints(
            attempt_count=1,
            error="Connection failed",
            strategy="conservative",
        )

        assert isinstance(hints, list)
        assert len(hints) > 0
        assert all(isinstance(h, str) for h in hints)
        assert any("Suggested approach:" in h for h in hints)

    def test_create_retry_strategy(self):
        """create_retry_strategy factory creates configured strategy."""
        strategy = create_retry_strategy(
            strategy_type="aggressive",
            max_retries=10,
            base_delay=0.5,
        )

        assert isinstance(strategy, RetryStrategy)
        assert strategy.strategy_type == RetryStrategyType.AGGRESSIVE
        assert strategy.max_retries == 10
        assert strategy.base_delay == 0.5


class TestIntegration:
    """Integration tests for Ralph loop components."""

    def test_config_to_strategy_flow(self, spec_dir: Path):
        """Config settings flow to strategy creation."""
        metadata = {
            "ralphLoop": {
                "enabled": True,
                "retry_strategy": "aggressive",
            }
        }
        (spec_dir / "task_metadata.json").write_text(json.dumps(metadata))

        config = load_ralph_config(spec_dir)
        strategy = create_retry_strategy(strategy_type=config["retry_strategy"])

        assert is_ralph_loop_enabled(config) is True
        assert strategy.strategy_type == RetryStrategyType.AGGRESSIVE

    def test_promises_and_strategy_combined(
        self, spec_dir: Path, project_dir: Path
    ):
        """Promises evaluation and strategy work together."""
        # Set up a failing promise
        promise = CompletionPromise(
            name="Missing file",
            promise_type=PromiseType.FILE_EXISTS,
            check_params={"files": ["required.txt"]},
            required=True,
        )

        result = evaluate_promise(promise, spec_dir, project_dir)
        assert result.passed is False

        # Strategy should suggest retry
        strategy = create_retry_strategy("adaptive")
        decision = strategy.should_retry(
            attempt_count=0,
            error=result.message,
        )

        assert decision.should_retry is True
        assert decision.approach is not None
