"""
Shell Interpreter Validators
=============================

Validators for shell interpreter commands (bash, sh, zsh) that execute
inline commands via the -c flag.

This closes a security bypass where `bash -c "npm test"` could execute
arbitrary commands since `bash` is in BASE_COMMANDS but the commands
inside -c were not being validated.

Now enhanced with AST-based validation from bash_validator.py for:
- Detection of dangerous constructs (redirects, command substitution, etc.)
- Process substitution blocking (<(...) and >(...))
- Background execution prevention (&)
- Control character detection
"""

import os
import shlex
from pathlib import Path

from core.bash_validator import (
    BASHLEX_AVAILABLE,
    CompiledPattern,
    check_control_characters,
    compile_patterns,
)

# Import AST-based bash validator
from core.bash_validator import (
    validate_bash_command as ast_validate_bash_command,
)
from project_analyzer import is_command_allowed

from .parser import _cross_platform_basename, extract_commands, split_command_segments
from .profile import get_security_profile
from .validation_models import ValidationResult

# Shell interpreters that can execute nested commands
SHELL_INTERPRETERS = {"bash", "sh", "zsh"}

# Cache for compiled patterns per project
_pattern_cache: dict[str, list[CompiledPattern]] = {}


def _get_compiled_patterns_for_project(project_dir: str) -> list[CompiledPattern]:
    """
    Get compiled allowlist patterns for a project, with caching.

    Args:
        project_dir: Path to the project directory

    Returns:
        List of compiled patterns for the project's security profile
    """
    global _pattern_cache

    if project_dir in _pattern_cache:
        return _pattern_cache[project_dir]

    try:
        profile = get_security_profile(Path(project_dir))
        # Convert security profile commands to glob patterns
        all_commands = profile.get_all_allowed_commands()
        # Create patterns: exact command name or command followed by anything
        patterns = [f"{cmd}" for cmd in all_commands]
        patterns.extend([f"{cmd} *" for cmd in all_commands])
        compiled = compile_patterns(patterns)
        _pattern_cache[project_dir] = compiled
        return compiled
    except Exception:
        # Return empty list on error - validation will fall back to allowlist checking
        return []


def clear_pattern_cache(project_dir: str | None = None) -> None:
    """
    Clear the compiled pattern cache.

    Args:
        project_dir: Specific project to clear, or None to clear all
    """
    global _pattern_cache
    if project_dir is None:
        _pattern_cache.clear()
    elif project_dir in _pattern_cache:
        del _pattern_cache[project_dir]


def _validate_with_ast(command_string: str, project_dir: str) -> tuple[bool, str]:
    """
    Validate a command using AST-based analysis.

    This is the primary validation method when bashlex is available.
    It detects dangerous shell constructs that could bypass security.

    Args:
        command_string: The command to validate
        project_dir: Project directory for allowlist lookup

    Returns:
        Tuple of (is_valid, error_message)
    """
    # First check for control characters (no parsing needed)
    ctrl_reason = check_control_characters(command_string)
    if ctrl_reason:
        return False, ctrl_reason.message

    # Get compiled patterns for this project
    patterns = _get_compiled_patterns_for_project(project_dir)

    # If no patterns (profile load failed), skip AST validation
    # and let the allowlist checker handle it
    if not patterns:
        return True, ""

    # Perform AST-based validation
    result = ast_validate_bash_command(command_string, patterns)

    if not result.allowed:
        if result.reason:
            return False, result.reason.message
        return False, "Command rejected by AST validator"

    return True, ""


def _extract_c_argument(command_string: str) -> str | None:
    """
    Extract the command string from a shell -c invocation.

    Handles various formats:
    - bash -c 'command'
    - bash -c "command"
    - sh -c 'cmd1 && cmd2'
    - zsh -c "complex command"

    Args:
        command_string: The full shell command (e.g., "bash -c 'npm test'")

    Returns:
        The command string after -c, or None if not a -c invocation
    """
    try:
        tokens = shlex.split(command_string)
    except ValueError:
        # Malformed command - let it fail safely
        return None

    if len(tokens) < 3:
        return None

    # Look for -c flag (standalone or combined with other flags like -xc, -ec, -ic)
    for i, token in enumerate(tokens):
        # Check for standalone -c or combined flags containing 'c'
        # Combined flags: -xc, -ec, -ic, -exc, etc. (short options bundled together)
        is_c_flag = token == "-c" or (
            token.startswith("-") and not token.startswith("--") and "c" in token[1:]
        )
        if is_c_flag and i + 1 < len(tokens):
            # The next token is the command to execute
            return tokens[i + 1]

    return None


def validate_shell_c_command(command_string: str) -> ValidationResult:
    """
    Validate commands inside bash/sh/zsh -c '...' strings.

    This prevents using shell interpreters to bypass the security allowlist.
    All commands inside the -c string must also be allowed by the profile.

    Now uses AST-based validation (when bashlex is available) for enhanced security:
    - Detects redirects, command substitution, process substitution
    - Blocks background execution (&)
    - Validates control characters

    Args:
        command_string: The full shell command (e.g., "bash -c 'npm test'")

    Returns:
        Tuple of (is_valid, error_message)
    """
    # Get the security profile for the current project
    # Use PROJECT_DIR_ENV_VAR if set, otherwise use cwd
    from .constants import PROJECT_DIR_ENV_VAR

    project_dir = os.environ.get(PROJECT_DIR_ENV_VAR)
    if not project_dir:
        project_dir = os.getcwd()

    # First, apply AST-based validation if available
    # This catches dangerous constructs before we even look at specific commands
    if BASHLEX_AVAILABLE:
        ast_valid, ast_error = _validate_with_ast(command_string, project_dir)
        if not ast_valid:
            return False, f"AST validation failed: {ast_error}"

    # Extract the command after -c
    inner_command = _extract_c_argument(command_string)

    if inner_command is None:
        # Not a -c invocation (e.g., "bash script.sh")
        # Block dangerous shell constructs that could bypass sandbox restrictions:
        # - Process substitution: <(...) or >(...)
        # - Command substitution in dangerous contexts: $(...)
        dangerous_patterns = ["<(", ">("]
        for pattern in dangerous_patterns:
            if pattern in command_string:
                return (
                    False,
                    f"Process substitution '{pattern}' not allowed in shell commands",
                )
        # Allow simple shell invocations (e.g., "bash script.sh")
        # The script itself would need to be in allowed commands
        return True, ""

    # Handle empty commands early - they're harmless (e.g., bash -c "")
    # This check must come before AST validation since empty strings fail parsing
    if not inner_command.strip():
        return True, ""

    # Apply AST validation to the inner command as well
    if BASHLEX_AVAILABLE:
        ast_valid, ast_error = _validate_with_ast(inner_command, project_dir)
        if not ast_valid:
            return False, f"Inner command AST validation failed: {ast_error}"

    try:
        profile = get_security_profile(Path(project_dir))
    except Exception:
        # If we can't get the profile, fail safe by blocking
        return False, "Could not load security profile to validate shell -c command"

    # Extract command names for allowlist validation
    inner_command_names = extract_commands(inner_command)

    if not inner_command_names:
        # Could not parse - fail safe for non-empty commands
        return False, f"Could not parse commands inside shell -c: {inner_command}"

    # Validate each command name against the security profile
    for cmd_name in inner_command_names:
        is_allowed, reason = is_command_allowed(cmd_name, profile)
        if not is_allowed:
            return (
                False,
                f"Command '{cmd_name}' inside shell -c is not allowed: {reason}",
            )

    # Get full command segments for recursive shell validation
    # (split_command_segments gives us full commands, not just names)
    inner_segments = split_command_segments(inner_command)

    for segment in inner_segments:
        # Check if this segment is a shell invocation that needs recursive validation
        segment_commands = extract_commands(segment)
        if segment_commands:
            first_cmd = segment_commands[0]
            # Handle paths like /bin/bash or C:\Windows\System32\bash.exe
            base_cmd = _cross_platform_basename(first_cmd)
            if base_cmd in SHELL_INTERPRETERS:
                valid, err = validate_shell_c_command(segment)
                if not valid:
                    return False, f"Nested shell command not allowed: {err}"

    return True, ""


# Alias for common shell interpreters - they all use the same validation
validate_bash_command = validate_shell_c_command
validate_sh_command = validate_shell_c_command
validate_zsh_command = validate_shell_c_command
