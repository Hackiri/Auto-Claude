"""
AST-based Bash Command Validation

This module provides security validation for bash commands using AST parsing
instead of regex pattern matching. It detects and blocks dangerous constructs
like redirects, command substitution, process substitution, and background execution.

Inspired by Craft Agents OSS bash-validator.ts
"""

import re
from dataclasses import dataclass
from enum import Enum

# Try to import bashlex for AST parsing
try:
    import bashlex

    BASHLEX_AVAILABLE = True
except ImportError:
    BASHLEX_AVAILABLE = False


class ValidationReasonType(Enum):
    """Types of validation failures."""

    PIPELINE = "pipeline"
    REDIRECT = "redirect"
    COMMAND_EXPANSION = "command_expansion"
    PROCESS_SUBSTITUTION = "process_substitution"
    UNSAFE_COMMAND = "unsafe_command"
    PARSE_ERROR = "parse_error"
    BACKGROUND_EXECUTION = "background_execution"
    CONTROL_CHARACTERS = "control_characters"


@dataclass
class ValidationReason:
    """Details about why a command was rejected."""

    type: ValidationReasonType
    message: str
    details: str | None = None


@dataclass
class SubcommandResult:
    """Result for an individual subcommand in a compound command."""

    command: str
    allowed: bool
    reason: str | None = None


@dataclass
class BashValidationResult:
    """Result of bash command validation."""

    allowed: bool
    reason: ValidationReason | None = None
    subcommand_results: list[SubcommandResult] | None = None


@dataclass
class CompiledPattern:
    """A pre-compiled allowlist pattern."""

    pattern: re.Pattern
    original: str
    comment: str | None = None


def compile_patterns(patterns: list[str]) -> list[CompiledPattern]:
    """
    Compile glob-style patterns into regex patterns.

    Args:
        patterns: List of glob patterns like "git *", "npm test*"

    Returns:
        List of compiled patterns
    """
    compiled = []
    for pattern in patterns:
        # Convert glob to regex
        # Escape special regex chars except * and ?
        regex_pattern = re.escape(pattern)
        # Convert * to .* and ? to .
        regex_pattern = regex_pattern.replace(r"\*", ".*").replace(r"\?", ".")
        # Anchor the pattern
        regex_pattern = f"^{regex_pattern}$"
        compiled.append(
            CompiledPattern(pattern=re.compile(regex_pattern), original=pattern)
        )
    return compiled


def check_control_characters(command: str) -> ValidationReason | None:
    """
    Check for control characters that could manipulate parsing.

    Blocks: newlines, carriage returns, null bytes, and other control chars
    """
    # Check for dangerous control characters
    dangerous_chars = {
        "\n": "newline",
        "\r": "carriage return",
        "\x00": "null byte",
        "\x1b": "escape sequence",
    }

    for char, name in dangerous_chars.items():
        if char in command:
            return ValidationReason(
                type=ValidationReasonType.CONTROL_CHARACTERS,
                message=f"Command contains forbidden control character: {name}",
                details=f"Found {name} which could manipulate command parsing",
            )

    return None


def check_command_against_patterns(
    command: str, patterns: list[CompiledPattern]
) -> bool:
    """
    Check if a command matches any allowed pattern.

    Args:
        command: The command string to check
        patterns: List of compiled allowlist patterns

    Returns:
        True if command matches at least one pattern
    """
    for pattern in patterns:
        if pattern.pattern.match(command):
            return True
    return False


def _validate_node_ast(
    node, patterns: list[CompiledPattern], results: list[SubcommandResult]
) -> ValidationReason | None:
    """
    Recursively validate an AST node.

    Args:
        node: bashlex AST node
        patterns: Compiled allowlist patterns
        results: List to collect subcommand results

    Returns:
        ValidationReason if validation fails, None if ok
    """
    if not BASHLEX_AVAILABLE:
        return None

    kind = node.kind

    # Check for redirects
    if kind == "redirect":
        return ValidationReason(
            type=ValidationReasonType.REDIRECT,
            message="Redirects are not allowed for security",
            details="Found redirect operator",
        )

    # Check for background execution
    if kind == "operator" and hasattr(node, "op") and node.op == "&":
        return ValidationReason(
            type=ValidationReasonType.BACKGROUND_EXECUTION,
            message="Background execution (&) is not allowed",
            details="Background processes could hide malicious activity",
        )

    # Check for command substitution $(...) or `...`
    if kind == "commandsubstitution":
        return ValidationReason(
            type=ValidationReasonType.COMMAND_EXPANSION,
            message="Command substitution $() is not allowed",
            details="Could execute arbitrary commands",
        )

    # Check for process substitution <(...) or >(...)
    if kind == "processsubstitution":
        return ValidationReason(
            type=ValidationReasonType.PROCESS_SUBSTITUTION,
            message="Process substitution <() or >() is not allowed",
            details="Could create dynamic process pipes",
        )

    # For command nodes, check against allowlist
    if kind == "command":
        # Extract the command string
        cmd_parts = []
        for part in node.parts:
            if hasattr(part, "word"):
                cmd_parts.append(part.word)
            elif part.kind == "parameter":
                # Skip parameter expansion for now, treat as variable
                cmd_parts.append("$VAR")

        cmd_str = " ".join(cmd_parts)
        allowed = check_command_against_patterns(cmd_str, patterns)
        results.append(
            SubcommandResult(
                command=cmd_str,
                allowed=allowed,
                reason=None if allowed else "Command not in allowlist",
            )
        )

        if not allowed:
            return ValidationReason(
                type=ValidationReasonType.UNSAFE_COMMAND,
                message=f"Command not in allowlist: {cmd_str}",
                details="Add pattern to security.py allowlist to enable",
            )

    # Recurse into child nodes
    if hasattr(node, "parts"):
        for part in node.parts:
            reason = _validate_node_ast(part, patterns, results)
            if reason:
                return reason

    if hasattr(node, "list"):
        for item in node.list:
            reason = _validate_node_ast(item, patterns, results)
            if reason:
                return reason

    return None


def _validate_with_regex_fallback(
    command: str, patterns: list[CompiledPattern]
) -> BashValidationResult:
    """
    Fallback regex-based validation when bashlex is not available.

    This is less secure than AST parsing but provides basic protection.
    """
    # Check for redirects
    if re.search(r"[^\\]?[<>|]", command):
        # Check for pipe specifically
        if "|" in command and "||" not in command:
            # Pipes are allowed in some contexts, check each side
            pass
        elif re.search(r"[<>]", command):
            return BashValidationResult(
                allowed=False,
                reason=ValidationReason(
                    type=ValidationReasonType.REDIRECT,
                    message="Redirects detected (>, <, >>)",
                    details="Use dedicated file tools instead",
                ),
            )

    # Check for command substitution
    if re.search(r"\$\(|\`", command):
        return BashValidationResult(
            allowed=False,
            reason=ValidationReason(
                type=ValidationReasonType.COMMAND_EXPANSION,
                message="Command substitution detected ($() or ``)",
                details="Could execute arbitrary commands",
            ),
        )

    # Check for process substitution
    if re.search(r"[<>]\(", command):
        return BashValidationResult(
            allowed=False,
            reason=ValidationReason(
                type=ValidationReasonType.PROCESS_SUBSTITUTION,
                message="Process substitution detected (<() or >())",
                details="Could create dynamic process pipes",
            ),
        )

    # Check for background execution (but not && or ||)
    if re.search(r"(?<![&|])&(?![&|])", command):
        return BashValidationResult(
            allowed=False,
            reason=ValidationReason(
                type=ValidationReasonType.BACKGROUND_EXECUTION,
                message="Background execution detected (&)",
                details="Could hide malicious processes",
            ),
        )

    # Split by && and || to check individual commands
    # This is a simplified split - real parsing is more complex
    parts = re.split(r"\s*(?:&&|\|\||;)\s*", command)
    results = []

    for part in parts:
        part = part.strip()
        if not part:
            continue

        allowed = check_command_against_patterns(part, patterns)
        results.append(
            SubcommandResult(
                command=part,
                allowed=allowed,
                reason=None if allowed else "Command not in allowlist",
            )
        )

        if not allowed:
            return BashValidationResult(
                allowed=False,
                reason=ValidationReason(
                    type=ValidationReasonType.UNSAFE_COMMAND,
                    message=f"Command not in allowlist: {part}",
                    details="Add pattern to security allowlist",
                ),
                subcommand_results=results,
            )

    return BashValidationResult(allowed=True, subcommand_results=results)


def validate_bash_command(
    command: str, patterns: list[CompiledPattern], allow_pipes: bool = True
) -> BashValidationResult:
    """
    Validate a bash command using AST analysis.

    Args:
        command: The bash command to validate
        patterns: List of compiled allowlist patterns
        allow_pipes: Whether to allow pipe (|) operators

    Returns:
        BashValidationResult with allowed status and reason if rejected
    """
    # First check for control characters (no parsing needed)
    ctrl_reason = check_control_characters(command)
    if ctrl_reason:
        return BashValidationResult(allowed=False, reason=ctrl_reason)

    # Try AST-based validation if bashlex is available
    if BASHLEX_AVAILABLE:
        try:
            ast = bashlex.parse(command)
            results: list[SubcommandResult] = []

            for node in ast:
                reason = _validate_node_ast(node, patterns, results)
                if reason:
                    return BashValidationResult(
                        allowed=False,
                        reason=reason,
                        subcommand_results=results if results else None,
                    )

            return BashValidationResult(
                allowed=True, subcommand_results=results if results else None
            )
        except Exception as e:
            # Parse error - could be syntax error or complex construct
            return BashValidationResult(
                allowed=False,
                reason=ValidationReason(
                    type=ValidationReasonType.PARSE_ERROR,
                    message=f"Failed to parse command: {str(e)}",
                    details="Command may have invalid syntax or use unsupported features",
                ),
            )

    # Fallback to regex-based validation
    return _validate_with_regex_fallback(command, patterns)


# Default safe patterns that are always allowed
DEFAULT_SAFE_PATTERNS = [
    "echo *",
    "printf *",
    "true",
    "false",
    ": *",  # Bash no-op
]


def create_validator(
    allowed_patterns: list[str], include_defaults: bool = True
) -> callable:
    """
    Create a validator function with pre-compiled patterns.

    Args:
        allowed_patterns: List of glob patterns to allow
        include_defaults: Whether to include default safe patterns

    Returns:
        A validator function that takes a command string
    """
    patterns = allowed_patterns.copy()
    if include_defaults:
        patterns.extend(DEFAULT_SAFE_PATTERNS)

    compiled = compile_patterns(patterns)

    def validator(command: str, allow_pipes: bool = True) -> BashValidationResult:
        return validate_bash_command(command, compiled, allow_pipes)

    return validator
