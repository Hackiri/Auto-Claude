"""
Completion Promise Module
=========================

Defines completion promises (success criteria) for Ralph loop iterations.
A promise is a condition that must be met for the loop to exit successfully.

Completion promises allow the Ralph loop to determine when a build is truly
complete, going beyond simple subtask completion to check actual success criteria
like passing tests, successful builds, or file existence.

Key Features:
- Multiple promise types (test_pass, build_success, file_exists, custom)
- Type-based dispatching for evaluation
- Support for required vs optional promises
- Clear boolean evaluation results
"""

from __future__ import annotations

import json
import logging
import subprocess
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any


class PromiseType(Enum):
    """Types of completion promises that can be evaluated."""

    TEST_PASS = "test_pass"  # All tests pass
    BUILD_SUCCESS = "build_success"  # Build completes without errors
    FILE_EXISTS = "file_exists"  # Specific file(s) exist
    COMMAND_SUCCESS = "command_success"  # Arbitrary command exits with 0
    QA_SIGNOFF = "qa_signoff"  # QA has signed off
    SUBTASKS_COMPLETE = "subtasks_complete"  # All subtasks marked complete
    CUSTOM = "custom"  # Custom evaluation function


@dataclass
class CompletionPromise:
    """Definition of a completion promise (success criterion).

    A completion promise represents a condition that must be satisfied for
    the Ralph loop to consider the build complete. Multiple promises can
    be defined, with some marked as required and others optional.

    Attributes:
        name: Human-readable name for this promise
        promise_type: Type of check to perform
        check_params: Parameters specific to the check type
        required: Whether this promise must pass for completion
        description: Optional longer description of what this promise checks
    """

    name: str
    promise_type: PromiseType
    check_params: dict[str, Any] = field(default_factory=dict)
    required: bool = True
    description: str = ""

    def to_dict(self) -> dict[str, Any]:
        """Convert promise to dictionary for serialization."""
        return {
            "name": self.name,
            "promise_type": self.promise_type.value,
            "check_params": self.check_params,
            "required": self.required,
            "description": self.description,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> CompletionPromise:
        """Create promise from dictionary."""
        return cls(
            name=data["name"],
            promise_type=PromiseType(data["promise_type"]),
            check_params=data.get("check_params", {}),
            required=data.get("required", True),
            description=data.get("description", ""),
        )


@dataclass
class PromiseResult:
    """Result of evaluating a completion promise.

    Attributes:
        promise: The promise that was evaluated
        passed: Whether the promise was satisfied
        message: Human-readable message about the result
        details: Additional details about the evaluation
    """

    promise: CompletionPromise
    passed: bool
    message: str
    details: dict[str, Any] = field(default_factory=dict)


def evaluate_promise(
    promise: CompletionPromise,
    spec_dir: Path,
    project_dir: Path | None = None,
) -> PromiseResult:
    """
    Evaluate a single completion promise.

    Dispatches to the appropriate evaluator based on promise type.

    Args:
        promise: The promise to evaluate
        spec_dir: Path to the spec directory
        project_dir: Path to the project root (defaults to spec_dir parent)

    Returns:
        PromiseResult with pass/fail status and details
    """
    if project_dir is None:
        # Default to going up from spec_dir to find project root
        # Typical structure: project/.auto-claude/specs/XXX-name/
        project_dir = spec_dir.parent.parent.parent

    evaluators = {
        PromiseType.TEST_PASS: _evaluate_test_pass,
        PromiseType.BUILD_SUCCESS: _evaluate_build_success,
        PromiseType.FILE_EXISTS: _evaluate_file_exists,
        PromiseType.COMMAND_SUCCESS: _evaluate_command_success,
        PromiseType.QA_SIGNOFF: _evaluate_qa_signoff,
        PromiseType.SUBTASKS_COMPLETE: _evaluate_subtasks_complete,
        PromiseType.CUSTOM: _evaluate_custom,
    }

    evaluator = evaluators.get(promise.promise_type)
    if evaluator is None:
        return PromiseResult(
            promise=promise,
            passed=False,
            message=f"Unknown promise type: {promise.promise_type}",
        )

    try:
        return evaluator(promise, spec_dir, project_dir)
    except Exception as e:
        logging.error(f"Error evaluating promise '{promise.name}': {e}")
        return PromiseResult(
            promise=promise,
            passed=False,
            message=f"Evaluation error: {e}",
            details={"error": str(e)},
        )


def _evaluate_test_pass(
    promise: CompletionPromise,
    spec_dir: Path,
    project_dir: Path,
) -> PromiseResult:
    """Evaluate a test_pass promise by running tests.

    check_params:
        command: Test command to run (default: "pytest")
        path: Path to test directory or file (relative to project_dir)
        timeout: Timeout in seconds (default: 300)
    """
    params = promise.check_params
    command = params.get("command", "pytest")
    test_path = params.get("path", "tests/")
    timeout = params.get("timeout", 300)

    # Build full command
    if isinstance(command, str):
        full_command = f"{command} {test_path}"
    else:
        full_command = command

    try:
        result = subprocess.run(
            full_command,
            shell=True,
            cwd=project_dir,
            capture_output=True,
            text=True,
            timeout=timeout,
        )

        passed = result.returncode == 0
        return PromiseResult(
            promise=promise,
            passed=passed,
            message="Tests passed" if passed else "Tests failed",
            details={
                "returncode": result.returncode,
                "stdout": result.stdout[-1000:] if result.stdout else "",
                "stderr": result.stderr[-1000:] if result.stderr else "",
            },
        )
    except subprocess.TimeoutExpired:
        return PromiseResult(
            promise=promise,
            passed=False,
            message=f"Tests timed out after {timeout}s",
            details={"timeout": timeout},
        )
    except Exception as e:
        return PromiseResult(
            promise=promise,
            passed=False,
            message=f"Failed to run tests: {e}",
            details={"error": str(e)},
        )


def _evaluate_build_success(
    promise: CompletionPromise,
    spec_dir: Path,
    project_dir: Path,
) -> PromiseResult:
    """Evaluate a build_success promise by running build command.

    check_params:
        command: Build command to run (required)
        timeout: Timeout in seconds (default: 600)
    """
    params = promise.check_params
    command = params.get("command")

    if not command:
        return PromiseResult(
            promise=promise,
            passed=False,
            message="No build command specified in check_params",
        )

    timeout = params.get("timeout", 600)

    try:
        result = subprocess.run(
            command,
            shell=True,
            cwd=project_dir,
            capture_output=True,
            text=True,
            timeout=timeout,
        )

        passed = result.returncode == 0
        return PromiseResult(
            promise=promise,
            passed=passed,
            message="Build succeeded" if passed else "Build failed",
            details={
                "returncode": result.returncode,
                "stdout": result.stdout[-1000:] if result.stdout else "",
                "stderr": result.stderr[-1000:] if result.stderr else "",
            },
        )
    except subprocess.TimeoutExpired:
        return PromiseResult(
            promise=promise,
            passed=False,
            message=f"Build timed out after {timeout}s",
            details={"timeout": timeout},
        )
    except Exception as e:
        return PromiseResult(
            promise=promise,
            passed=False,
            message=f"Failed to run build: {e}",
            details={"error": str(e)},
        )


def _evaluate_file_exists(
    promise: CompletionPromise,
    spec_dir: Path,
    project_dir: Path,
) -> PromiseResult:
    """Evaluate a file_exists promise by checking for file(s).

    check_params:
        files: List of file paths to check (relative to project_dir)
        all_required: If True, all files must exist; if False, any one suffices
    """
    params = promise.check_params
    files = params.get("files", [])
    all_required = params.get("all_required", True)

    if not files:
        return PromiseResult(
            promise=promise,
            passed=False,
            message="No files specified in check_params",
        )

    existing = []
    missing = []

    for file_path in files:
        full_path = project_dir / file_path
        if full_path.exists():
            existing.append(file_path)
        else:
            missing.append(file_path)

    if all_required:
        passed = len(missing) == 0
        message = "All files exist" if passed else f"Missing files: {', '.join(missing)}"
    else:
        passed = len(existing) > 0
        message = (
            f"Found files: {', '.join(existing)}"
            if passed
            else "No required files found"
        )

    return PromiseResult(
        promise=promise,
        passed=passed,
        message=message,
        details={"existing": existing, "missing": missing},
    )


def _evaluate_command_success(
    promise: CompletionPromise,
    spec_dir: Path,
    project_dir: Path,
) -> PromiseResult:
    """Evaluate a command_success promise by running arbitrary command.

    check_params:
        command: Command to run (required)
        timeout: Timeout in seconds (default: 60)
        expected_output: Optional string that must appear in stdout
    """
    params = promise.check_params
    command = params.get("command")

    if not command:
        return PromiseResult(
            promise=promise,
            passed=False,
            message="No command specified in check_params",
        )

    timeout = params.get("timeout", 60)
    expected_output = params.get("expected_output")

    try:
        result = subprocess.run(
            command,
            shell=True,
            cwd=project_dir,
            capture_output=True,
            text=True,
            timeout=timeout,
        )

        passed = result.returncode == 0

        # Check for expected output if specified
        if passed and expected_output:
            passed = expected_output in result.stdout

        message = "Command succeeded" if passed else "Command failed"
        if expected_output and result.returncode == 0 and not passed:
            message = f"Command succeeded but expected output '{expected_output}' not found"

        return PromiseResult(
            promise=promise,
            passed=passed,
            message=message,
            details={
                "returncode": result.returncode,
                "stdout": result.stdout[-500:] if result.stdout else "",
                "stderr": result.stderr[-500:] if result.stderr else "",
            },
        )
    except subprocess.TimeoutExpired:
        return PromiseResult(
            promise=promise,
            passed=False,
            message=f"Command timed out after {timeout}s",
            details={"timeout": timeout},
        )
    except Exception as e:
        return PromiseResult(
            promise=promise,
            passed=False,
            message=f"Failed to run command: {e}",
            details={"error": str(e)},
        )


def _evaluate_qa_signoff(
    promise: CompletionPromise,
    spec_dir: Path,
    project_dir: Path,
) -> PromiseResult:
    """Evaluate a qa_signoff promise by checking implementation_plan.json.

    check_params: (none required)
    """
    plan_path = spec_dir / "implementation_plan.json"

    if not plan_path.exists():
        return PromiseResult(
            promise=promise,
            passed=False,
            message="implementation_plan.json not found",
        )

    try:
        with open(plan_path) as f:
            plan = json.load(f)
    except (json.JSONDecodeError, OSError) as e:
        return PromiseResult(
            promise=promise,
            passed=False,
            message=f"Failed to read implementation_plan.json: {e}",
        )

    qa_signoff = plan.get("qa_signoff")
    if qa_signoff is None:
        return PromiseResult(
            promise=promise,
            passed=False,
            message="QA has not reviewed yet",
            details={"qa_signoff": None},
        )

    # Check if QA approved
    status = qa_signoff.get("status", "pending")
    passed = status.lower() in ("approved", "passed", "completed")

    return PromiseResult(
        promise=promise,
        passed=passed,
        message=f"QA status: {status}",
        details={"qa_signoff": qa_signoff},
    )


def _evaluate_subtasks_complete(
    promise: CompletionPromise,
    spec_dir: Path,
    project_dir: Path,
) -> PromiseResult:
    """Evaluate a subtasks_complete promise by checking implementation_plan.json.

    check_params:
        phases: Optional list of phase IDs to check (if empty, check all)
    """
    plan_path = spec_dir / "implementation_plan.json"

    if not plan_path.exists():
        return PromiseResult(
            promise=promise,
            passed=False,
            message="implementation_plan.json not found",
        )

    try:
        with open(plan_path) as f:
            plan = json.load(f)
    except (json.JSONDecodeError, OSError) as e:
        return PromiseResult(
            promise=promise,
            passed=False,
            message=f"Failed to read implementation_plan.json: {e}",
        )

    params = promise.check_params
    phase_filter = params.get("phases", [])

    total_subtasks = 0
    completed_subtasks = 0
    incomplete_subtasks = []

    for phase in plan.get("phases", []):
        # Skip phases not in filter (if filter provided)
        if phase_filter and phase["id"] not in phase_filter:
            continue

        for subtask in phase.get("subtasks", []):
            total_subtasks += 1
            status = subtask.get("status", "pending")

            if status == "completed":
                completed_subtasks += 1
            else:
                incomplete_subtasks.append(
                    {"id": subtask["id"], "status": status, "phase": phase["id"]}
                )

    passed = len(incomplete_subtasks) == 0 and total_subtasks > 0

    return PromiseResult(
        promise=promise,
        passed=passed,
        message=f"{completed_subtasks}/{total_subtasks} subtasks completed",
        details={
            "total": total_subtasks,
            "completed": completed_subtasks,
            "incomplete": incomplete_subtasks[:10],  # Limit to first 10
        },
    )


def _evaluate_custom(
    promise: CompletionPromise,
    spec_dir: Path,
    project_dir: Path,
) -> PromiseResult:
    """Evaluate a custom promise using a Python expression.

    check_params:
        expression: Python expression to evaluate (must return bool)
        Note: Expression has access to spec_dir and project_dir as Path objects

    Security note: This evaluates arbitrary Python code. Use with caution
    and only with trusted input.
    """
    params = promise.check_params
    expression = params.get("expression")

    if not expression:
        return PromiseResult(
            promise=promise,
            passed=False,
            message="No expression specified in check_params",
        )

    # Create a limited evaluation context
    eval_context = {
        "spec_dir": spec_dir,
        "project_dir": project_dir,
        "Path": Path,
    }

    try:
        # Evaluate the expression
        result = eval(expression, {"__builtins__": {}}, eval_context)
        passed = bool(result)

        return PromiseResult(
            promise=promise,
            passed=passed,
            message="Custom check passed" if passed else "Custom check failed",
            details={"expression": expression, "result": result},
        )
    except Exception as e:
        return PromiseResult(
            promise=promise,
            passed=False,
            message=f"Custom check error: {e}",
            details={"expression": expression, "error": str(e)},
        )


def evaluate_all_promises(
    promises: list[CompletionPromise],
    spec_dir: Path,
    project_dir: Path | None = None,
) -> tuple[bool, list[PromiseResult]]:
    """
    Evaluate all completion promises.

    Args:
        promises: List of promises to evaluate
        spec_dir: Path to the spec directory
        project_dir: Path to the project root (optional)

    Returns:
        Tuple of (all_required_passed, list of results)
    """
    results = []
    all_required_passed = True

    for promise in promises:
        result = evaluate_promise(promise, spec_dir, project_dir)
        results.append(result)

        if promise.required and not result.passed:
            all_required_passed = False

    return all_required_passed, results


def load_promises_from_plan(spec_dir: Path) -> list[CompletionPromise]:
    """
    Load completion promises from implementation_plan.json.

    Looks for a 'completion_promises' key in the plan.

    Args:
        spec_dir: Path to the spec directory

    Returns:
        List of CompletionPromise objects
    """
    plan_path = spec_dir / "implementation_plan.json"

    if not plan_path.exists():
        return []

    try:
        with open(plan_path) as f:
            plan = json.load(f)
    except (json.JSONDecodeError, OSError):
        return []

    promise_data = plan.get("completion_promises", [])
    promises = []

    for data in promise_data:
        try:
            promise = CompletionPromise.from_dict(data)
            promises.append(promise)
        except (KeyError, ValueError) as e:
            logging.warning(f"Invalid promise definition: {e}")

    return promises


def get_default_promises() -> list[CompletionPromise]:
    """
    Get the default set of completion promises for Ralph loop.

    Returns:
        List of default CompletionPromise objects
    """
    return [
        CompletionPromise(
            name="All subtasks completed",
            promise_type=PromiseType.SUBTASKS_COMPLETE,
            check_params={},
            required=True,
            description="All subtasks in implementation_plan.json are marked completed",
        ),
    ]
