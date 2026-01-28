"""
Base Module for Agent System
=============================

Shared imports, types, and constants used across agent modules.
"""

import logging

# Configure logging
logger = logging.getLogger(__name__)

# Configuration constants
AUTO_CONTINUE_DELAY_SECONDS = 3
HUMAN_INTERVENTION_FILE = "PAUSE"

# Ralph loop configuration constants
# Maximum iterations for Ralph loop mode in coder phase (safety net)
RALPH_MAX_CODER_ITERATIONS = 100
# Maximum consecutive failures before stopping (prevents infinite loops on stuck issues)
RALPH_CONSECUTIVE_FAILURE_LIMIT = 3
