"""
Swarm Mode Configuration Module
================================

Handles configuration for swarm mode parallel execution.
Reads configuration from task_metadata.json and provides resolved settings
with CLI override support.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import TypedDict

logger = logging.getLogger(__name__)


class SwarmConfig(TypedDict, total=False):
    """Swarm mode configuration from task_metadata.json or CLI flags.

    Attributes:
        enabled: Whether swarm mode is active
        max_workers: Maximum number of concurrent worker agents (default 3)
    """

    enabled: bool
    max_workers: int


DEFAULT_SWARM_CONFIG: SwarmConfig = {
    "enabled": False,
    "max_workers": 3,
}


def load_swarm_config(
    spec_dir: Path,
    cli_enabled: bool | None = None,
    cli_max_workers: int | None = None,
) -> SwarmConfig:
    """
    Load swarm mode configuration with CLI override support.

    Priority:
    1. CLI arguments (if provided)
    2. task_metadata.json swarmMode settings
    3. Default configuration

    Args:
        spec_dir: Path to the spec directory
        cli_enabled: --swarm flag from CLI (optional)
        cli_max_workers: --swarm-workers from CLI (optional)

    Returns:
        Merged SwarmConfig with all settings resolved
    """
    config: SwarmConfig = DEFAULT_SWARM_CONFIG.copy()

    # Load from task_metadata.json if available
    metadata_path = spec_dir / "task_metadata.json"
    if metadata_path.exists():
        try:
            with open(metadata_path) as f:
                metadata = json.load(f)
            swarm_meta = metadata.get("swarmMode")
            if swarm_meta and isinstance(swarm_meta, dict):
                if "enabled" in swarm_meta:
                    config["enabled"] = bool(swarm_meta["enabled"])
                if "maxWorkers" in swarm_meta:
                    value = swarm_meta["maxWorkers"]
                    if isinstance(value, int) and value > 0:
                        config["max_workers"] = value
        except (json.JSONDecodeError, OSError) as e:
            logger.warning(f"Failed to load task_metadata.json for swarm config: {e}")

    # CLI arguments take precedence
    if cli_enabled is not None:
        config["enabled"] = cli_enabled

    if cli_max_workers is not None and cli_max_workers > 0:
        config["max_workers"] = cli_max_workers

    return config


def is_swarm_mode_enabled(config: SwarmConfig) -> bool:
    """Check if swarm mode is enabled in the given configuration."""
    return config.get("enabled", False)
