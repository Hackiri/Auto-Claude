"""
Ralph Loop Configuration Module
================================

Handles configuration for the Ralph Wiggum iterative AI development technique.
Reads configuration from task_metadata.json and provides resolved settings
with CLI override support.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any, Literal, TypedDict

# Retry strategy type
RetryStrategyType = Literal["conservative", "aggressive", "adaptive"]


class RalphLoopConfig(TypedDict, total=False):
    """Ralph loop configuration from task_metadata.json or CLI flags.

    Attributes:
        enabled: Whether Ralph loop mode is active
        max_coder_iterations: Maximum iterations for coder phase
        max_qa_iterations: Maximum iterations for QA phase
        completion_promise_timeout: Timeout in seconds for promise evaluation
        retry_strategy: Strategy for retries ("conservative", "aggressive", "adaptive")
        overnight_mode: Extended timeouts and reduced logging for overnight runs
    """

    enabled: bool
    max_coder_iterations: int
    max_qa_iterations: int
    completion_promise_timeout: int
    retry_strategy: str
    overnight_mode: bool


# Default configuration values
DEFAULT_RALPH_CONFIG: RalphLoopConfig = {
    "enabled": False,
    "max_coder_iterations": 100,
    "max_qa_iterations": 50,
    "completion_promise_timeout": 300,  # 5 minutes
    "retry_strategy": "adaptive",
    "overnight_mode": False,
}

# Valid retry strategy values
VALID_RETRY_STRATEGIES = {"conservative", "aggressive", "adaptive"}


def get_default_config() -> RalphLoopConfig:
    """
    Get the default Ralph loop configuration.

    Returns:
        Default RalphLoopConfig with all fields populated
    """
    return DEFAULT_RALPH_CONFIG.copy()


def load_ralph_config_from_metadata(spec_dir: Path) -> RalphLoopConfig | None:
    """
    Load Ralph loop configuration from task_metadata.json.

    Args:
        spec_dir: Path to the spec directory

    Returns:
        Parsed Ralph loop config or None if not found
    """
    metadata_path = spec_dir / "task_metadata.json"
    if not metadata_path.exists():
        return None

    try:
        with open(metadata_path) as f:
            metadata = json.load(f)
    except (json.JSONDecodeError, OSError) as e:
        logging.warning(f"Failed to load task_metadata.json: {e}")
        return None

    # Look for ralphLoop key in metadata
    ralph_config = metadata.get("ralphLoop")
    if ralph_config is None:
        return None

    # Validate and normalize the config
    return _normalize_config(ralph_config)


def _normalize_config(raw_config: dict[str, Any]) -> RalphLoopConfig:
    """
    Normalize and validate raw configuration from JSON.

    Args:
        raw_config: Raw dictionary from task_metadata.json

    Returns:
        Normalized RalphLoopConfig
    """
    config: RalphLoopConfig = {}

    # enabled - boolean
    if "enabled" in raw_config:
        config["enabled"] = bool(raw_config["enabled"])

    # max_coder_iterations - positive integer
    if "max_coder_iterations" in raw_config:
        value = raw_config["max_coder_iterations"]
        if isinstance(value, int) and value > 0:
            config["max_coder_iterations"] = value
        else:
            logging.warning(
                f"Invalid max_coder_iterations value: {value}. Using default."
            )

    # max_qa_iterations - positive integer
    if "max_qa_iterations" in raw_config:
        value = raw_config["max_qa_iterations"]
        if isinstance(value, int) and value > 0:
            config["max_qa_iterations"] = value
        else:
            logging.warning(f"Invalid max_qa_iterations value: {value}. Using default.")

    # completion_promise_timeout - positive integer (seconds)
    if "completion_promise_timeout" in raw_config:
        value = raw_config["completion_promise_timeout"]
        if isinstance(value, int) and value > 0:
            config["completion_promise_timeout"] = value
        else:
            logging.warning(
                f"Invalid completion_promise_timeout value: {value}. Using default."
            )

    # retry_strategy - validated string
    if "retry_strategy" in raw_config:
        value = raw_config["retry_strategy"]
        if value in VALID_RETRY_STRATEGIES:
            config["retry_strategy"] = value
        else:
            logging.warning(
                f"Invalid retry_strategy '{value}'. "
                f"Valid values: {', '.join(VALID_RETRY_STRATEGIES)}. Using default."
            )

    # overnight_mode - boolean
    if "overnight_mode" in raw_config:
        config["overnight_mode"] = bool(raw_config["overnight_mode"])

    return config


def load_ralph_config(
    spec_dir: Path,
    cli_enabled: bool | None = None,
    cli_max_iterations: int | None = None,
    cli_overnight: bool | None = None,
) -> RalphLoopConfig:
    """
    Load Ralph loop configuration with CLI override support.

    Priority:
    1. CLI arguments (if provided)
    2. task_metadata.json ralphLoop settings
    3. Default configuration

    Args:
        spec_dir: Path to the spec directory
        cli_enabled: --ralph-loop flag from CLI (optional)
        cli_max_iterations: --ralph-max-iterations from CLI (optional)
        cli_overnight: --overnight flag from CLI (optional)

    Returns:
        Merged RalphLoopConfig with all settings resolved
    """
    # Start with defaults
    config = get_default_config()

    # Load from task_metadata.json if available
    metadata_config = load_ralph_config_from_metadata(spec_dir)
    if metadata_config:
        config.update(metadata_config)

    # CLI arguments take precedence
    if cli_enabled is not None:
        config["enabled"] = cli_enabled

    if cli_max_iterations is not None:
        if cli_max_iterations > 0:
            config["max_coder_iterations"] = cli_max_iterations
        else:
            logging.warning(
                f"Invalid CLI max_iterations value: {cli_max_iterations}. Ignoring."
            )

    if cli_overnight is not None:
        config["overnight_mode"] = cli_overnight
        # Overnight mode implies ralph loop is enabled
        if cli_overnight:
            config["enabled"] = True

    return config


def is_ralph_loop_enabled(config: RalphLoopConfig) -> bool:
    """
    Check if Ralph loop mode is enabled in the given configuration.

    Args:
        config: RalphLoopConfig to check

    Returns:
        True if Ralph loop is enabled
    """
    return config.get("enabled", DEFAULT_RALPH_CONFIG["enabled"])


def get_max_iterations(config: RalphLoopConfig, phase: str) -> int:
    """
    Get the maximum iterations for a specific phase.

    Args:
        config: RalphLoopConfig to read from
        phase: Phase name ("coder" or "qa")

    Returns:
        Maximum iterations for the phase
    """
    if phase == "coder":
        return config.get(
            "max_coder_iterations", DEFAULT_RALPH_CONFIG["max_coder_iterations"]
        )
    elif phase == "qa":
        return config.get(
            "max_qa_iterations", DEFAULT_RALPH_CONFIG["max_qa_iterations"]
        )
    else:
        logging.warning(f"Unknown phase '{phase}'. Using coder max iterations.")
        return config.get(
            "max_coder_iterations", DEFAULT_RALPH_CONFIG["max_coder_iterations"]
        )
