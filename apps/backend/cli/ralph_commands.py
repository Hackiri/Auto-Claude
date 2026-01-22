"""
Ralph Commands
==============

CLI commands for Ralph Wiggum iterative loop status checking.
"""

import sys
from pathlib import Path

# Ensure parent directory is in path for imports (before other imports)
_PARENT_DIR = Path(__file__).parent.parent
if str(_PARENT_DIR) not in sys.path:
    sys.path.insert(0, str(_PARENT_DIR))

from progress import count_subtasks
from ralph_loop.config import (
    DEFAULT_RALPH_CONFIG,
    is_ralph_loop_enabled,
    load_ralph_config,
)
from ui import (
    Icons,
    bold,
    box,
    highlight,
    icon,
    info,
    muted,
    success,
)

from .utils import print_banner


def handle_ralph_status_command(spec_dir: Path) -> None:
    """
    Handle the --ralph-status command.

    Displays the current Ralph loop configuration and status for a spec.

    Args:
        spec_dir: Spec directory path
    """
    print_banner()
    print(f"\nSpec: {spec_dir.name}\n")
    print_ralph_status(spec_dir)


def print_ralph_status(spec_dir: Path) -> None:
    """
    Print Ralph loop status and configuration.

    Args:
        spec_dir: Spec directory path
    """
    # Load configuration (will merge defaults with any task_metadata.json settings)
    config = load_ralph_config(spec_dir)

    # Determine if Ralph loop is enabled
    enabled = is_ralph_loop_enabled(config)

    # Build status display
    content = [
        bold(f"{icon(Icons.LOOP)} RALPH LOOP STATUS"),
        "",
    ]

    # Enabled status
    if enabled:
        content.append(success(f"{icon(Icons.SUCCESS)} Mode: ENABLED"))
    else:
        content.append(info(f"{icon(Icons.INFO)} Mode: DISABLED"))
        content.append("")
        content.append(muted("Enable with: --ralph-loop flag"))

    content.append("")

    # Configuration details
    content.append(bold("Configuration:"))

    # Max iterations
    max_coder = config.get(
        "max_coder_iterations", DEFAULT_RALPH_CONFIG["max_coder_iterations"]
    )
    max_qa = config.get("max_qa_iterations", DEFAULT_RALPH_CONFIG["max_qa_iterations"])
    content.append(f"  Coder max iterations: {highlight(str(max_coder))}")
    content.append(f"  QA max iterations: {highlight(str(max_qa))}")

    # Retry strategy
    retry_strategy = config.get(
        "retry_strategy", DEFAULT_RALPH_CONFIG["retry_strategy"]
    )
    content.append(f"  Retry strategy: {highlight(retry_strategy)}")

    # Overnight mode
    overnight_mode = config.get(
        "overnight_mode", DEFAULT_RALPH_CONFIG["overnight_mode"]
    )
    if overnight_mode:
        content.append(f"  Overnight mode: {success('ACTIVE')}")
    else:
        content.append(f"  Overnight mode: {muted('inactive')}")

    # Promise timeout
    timeout = config.get(
        "completion_promise_timeout", DEFAULT_RALPH_CONFIG["completion_promise_timeout"]
    )
    content.append(f"  Promise timeout: {timeout}s")

    content.append("")

    # Build progress
    content.append(bold("Build Progress:"))
    completed, total = count_subtasks(spec_dir)
    if total > 0:
        percentage = (completed / total) * 100
        content.append(f"  Subtasks: {completed}/{total} ({percentage:.0f}%)")
    else:
        content.append("  Subtasks: No implementation plan found")

    # Check for ralph_loop_report.md
    report_file = spec_dir / "ralph_loop_report.md"
    if report_file.exists():
        content.append("")
        content.append(f"  {icon(Icons.DOCUMENT)} Report available: {report_file.name}")

    print(box(content, width=70, style="heavy"))
    print()

    # Show configuration source
    metadata_file = spec_dir / "task_metadata.json"
    if metadata_file.exists():
        print(muted(f"Config source: {metadata_file.name} (with defaults)"))
    else:
        print(muted("Config source: Defaults (no task_metadata.json found)"))
    print()
