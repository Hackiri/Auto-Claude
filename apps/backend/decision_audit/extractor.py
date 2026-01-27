"""
Decision Extractor
==================

Automatically extracts structured decisions from agent responses.
Uses Claude Haiku for fast, cheap extraction of decision points.

Decision extraction identifies:
- What was decided (approach, tool, file, etc.)
- Why it was decided (reasoning)
- What alternatives were considered
- What context influenced the decision

Uses the Claude Agent SDK (same as the rest of the system) for extraction.
Falls back gracefully if extraction fails (never blocks the build).
"""

from __future__ import annotations

import json
import logging
import os
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

# Check for Claude SDK availability
try:
    from claude_agent_sdk import ClaudeAgentOptions, ClaudeSDKClient

    SDK_AVAILABLE = True
except ImportError:
    SDK_AVAILABLE = False
    ClaudeAgentOptions = None
    ClaudeSDKClient = None

from core.auth import ensure_claude_code_oauth_token, get_auth_token

from .models import (
    ConfidenceLevel,
    DecisionContext,
    DecisionEntry,
    DecisionType,
)

# Default model for decision extraction (fast and cheap)
# Note: Using Haiku 4.5 for fast, cheap extraction. Haiku does not support
# extended thinking, so thinking_default is set to "none" in models.py
DEFAULT_EXTRACTION_MODEL = "claude-haiku-4-5-20251001"

# Maximum response text to send to the LLM (avoid context limits)
MAX_RESPONSE_CHARS = 20000

# Maximum decisions to extract per response
MAX_DECISIONS_PER_RESPONSE = 10


def is_decision_extraction_enabled() -> bool:
    """Check if decision extraction is enabled."""
    # Extraction requires Claude SDK and authentication token
    if not SDK_AVAILABLE:
        return False
    if not get_auth_token():
        return False
    enabled_str = os.environ.get("DECISION_EXTRACTION_ENABLED", "true").lower()
    return enabled_str in ("true", "1", "yes")


def get_extraction_model() -> str:
    """Get the model to use for decision extraction."""
    return os.environ.get("DECISION_EXTRACTOR_MODEL", DEFAULT_EXTRACTION_MODEL)


# =============================================================================
# Prompt Building
# =============================================================================


def _get_extraction_prompt() -> str:
    """Load the extraction prompt from file or use fallback."""
    prompt_file = Path(__file__).parent.parent / "prompts" / "decision_extractor.md"

    if prompt_file.exists():
        return prompt_file.read_text(encoding="utf-8")

    # Fallback if prompt file missing
    return """You are an expert at analyzing AI agent conversations to extract key decisions.

Analyze the provided agent response text and extract any decisions the agent made.

For each decision found, identify:
1. **type**: One of: approach_chosen, alternative_rejected, context_used, pattern_followed, file_selected, tool_selected, error_recovery
2. **description**: What was decided (brief, clear statement)
3. **reasoning**: Why this decision was made
4. **alternatives_considered**: What other options were considered (if mentioned)
5. **context_used**: What context influenced the decision (files read, patterns referenced, etc.)
6. **confidence**: high, medium, or low based on how certain the agent seemed

Output ONLY valid JSON in this format:
{
  "decisions": [
    {
      "type": "approach_chosen",
      "description": "Brief description of what was decided",
      "reasoning": "Why this was chosen",
      "alternatives_considered": ["option1", "option2"],
      "context_used": [
        {"source": "file_read", "content": "path/to/file.py"}
      ],
      "confidence": "high"
    }
  ]
}

If no clear decisions are found, return: {"decisions": []}

Focus on extracting meaningful decisions, not routine operations. Look for:
- Explicit choices between alternatives
- Reasoning about why one approach is better
- References to patterns or conventions being followed
- File or tool selection with justification
- Error handling and recovery decisions
"""


def _build_extraction_prompt(response_text: str, subtask_id: str | None = None) -> str:
    """Build the full extraction prompt with response text."""
    base_prompt = _get_extraction_prompt()

    # Truncate response if too long
    if len(response_text) > MAX_RESPONSE_CHARS:
        response_text = (
            response_text[:MAX_RESPONSE_CHARS]
            + f"\n\n... (truncated, {len(response_text)} chars total)"
        )

    context_info = ""
    if subtask_id:
        context_info = f"\n\n**Current Subtask**: {subtask_id}"

    return f"""{base_prompt}

---

## AGENT RESPONSE TO ANALYZE
{context_info}

```
{response_text}
```

---

Now analyze this response and output ONLY the JSON object with extracted decisions.
"""


# =============================================================================
# LLM Extraction
# =============================================================================


async def _run_extraction(
    prompt: str, project_dir: Path | None = None
) -> dict | None:
    """
    Run the decision extraction using Claude Agent SDK.

    Args:
        prompt: The extraction prompt
        project_dir: Project directory for SDK context (optional)

    Returns:
        Extracted decisions dict or None if failed
    """
    if not SDK_AVAILABLE:
        logger.warning("Claude SDK not available, skipping decision extraction")
        return None

    if not get_auth_token():
        logger.warning("No authentication token found, skipping decision extraction")
        return None

    # Ensure SDK can find the token
    ensure_claude_code_oauth_token()

    model = get_extraction_model()

    # Use current directory if project_dir not specified
    cwd = str(project_dir.resolve()) if project_dir else os.getcwd()

    try:
        from core.simple_client import create_simple_client

        client = create_simple_client(
            agent_type="insights",  # Use insights config (read tools only, no thinking)
            model=model,
            system_prompt=(
                "You are an expert at analyzing AI agent conversations. "
                "Extract structured decisions from agent responses. "
                "Always respond with valid JSON only, no markdown formatting or explanations."
            ),
            cwd=Path(cwd) if cwd else None,
        )

        # Use async context manager
        async with client:
            await client.query(prompt)

            # Collect the response
            response_text = ""
            message_count = 0
            text_blocks_found = 0

            async for msg in client.receive_response():
                msg_type = type(msg).__name__
                message_count += 1

                if msg_type == "AssistantMessage" and hasattr(msg, "content"):
                    for block in msg.content:
                        # Must check block type - only TextBlock has .text attribute
                        block_type = type(block).__name__
                        if block_type == "TextBlock" and hasattr(block, "text"):
                            text_blocks_found += 1
                            if block.text:  # Only add non-empty text
                                response_text += block.text
                            else:
                                logger.debug(
                                    f"Found empty TextBlock in response (block #{text_blocks_found})"
                                )

            # Log response collection summary
            logger.debug(
                f"Decision extraction response: {message_count} messages, "
                f"{text_blocks_found} text blocks, {len(response_text)} chars collected"
            )

            # Validate we received content before parsing
            if not response_text.strip():
                logger.warning(
                    f"Decision extraction returned empty response. "
                    f"Messages received: {message_count}, TextBlocks found: {text_blocks_found}. "
                    f"This may indicate the AI model did not respond with text content."
                )
                return None

        # Parse JSON from response
        return _parse_extraction_response(response_text)

    except Exception as e:
        logger.warning(f"Decision extraction failed: {e}")
        return None


def _parse_extraction_response(response_text: str) -> dict | None:
    """
    Parse the LLM response into structured decisions.

    Args:
        response_text: Raw LLM response

    Returns:
        Parsed dict with decisions list or None if parsing failed
    """
    text = response_text.strip()

    # Early validation - check for empty response
    if not text:
        logger.warning("Cannot parse decisions: response text is empty")
        return None

    # Handle markdown code blocks
    if text.startswith("```"):
        lines = text.split("\n")
        # Remove first line (```json or ```)
        if lines[0].startswith("```"):
            lines = lines[1:]
        # Remove last line if it's ```
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        text = "\n".join(lines).strip()

        if not text:
            logger.warning(
                "Cannot parse decisions: response contained only markdown code block markers"
            )
            return None

    try:
        result = json.loads(text)

        if not isinstance(result, dict):
            logger.warning(
                f"Decisions response is not a dict, got type: {type(result).__name__}"
            )
            return None

        # Ensure decisions key exists
        result.setdefault("decisions", [])

        # Limit number of decisions
        if len(result["decisions"]) > MAX_DECISIONS_PER_RESPONSE:
            result["decisions"] = result["decisions"][:MAX_DECISIONS_PER_RESPONSE]

        return result

    except json.JSONDecodeError as e:
        logger.warning(f"Failed to parse decisions JSON: {e}")
        preview_length = min(500, len(text))
        logger.warning(
            f"Response text preview (first {preview_length} chars): {text[:preview_length]}"
        )
        return None


# =============================================================================
# Decision Entry Conversion
# =============================================================================


def _convert_to_decision_entries(
    raw_decisions: list[dict],
    subtask_id: str | None = None,
    phase: str | None = None,
) -> list[DecisionEntry]:
    """
    Convert raw extracted decisions to DecisionEntry objects.

    Args:
        raw_decisions: List of raw decision dicts from LLM
        subtask_id: Current subtask ID
        phase: Current phase

    Returns:
        List of DecisionEntry objects
    """
    import uuid
    from datetime import datetime, timezone

    entries = []

    for raw in raw_decisions:
        try:
            # Map decision type string to valid enum value
            type_str = raw.get("type", "approach_chosen")
            valid_types = {t.value for t in DecisionType}
            if type_str not in valid_types:
                type_str = DecisionType.APPROACH_CHOSEN.value

            # Build context list
            context_list = []
            for ctx in raw.get("context_used", []):
                if isinstance(ctx, dict):
                    context_list.append(
                        DecisionContext(
                            source=ctx.get("source", "extracted"),
                            content=ctx.get("content", ""),
                            metadata=ctx.get("metadata", {}),
                        )
                    )

            # Map confidence
            confidence_str = raw.get("confidence", "medium")
            valid_confidences = {c.value for c in ConfidenceLevel}
            if confidence_str not in valid_confidences:
                confidence_str = ConfidenceLevel.MEDIUM.value

            entry = DecisionEntry(
                id=f"dec-{uuid.uuid4().hex[:12]}",
                timestamp=datetime.now(timezone.utc).isoformat(),
                decision_type=type_str,
                description=raw.get("description", "Extracted decision"),
                reasoning=raw.get("reasoning", ""),
                alternatives_considered=raw.get("alternatives_considered", []),
                context_used=context_list,
                subtask_id=subtask_id,
                phase=phase,
                confidence_level=confidence_str,
            )
            entries.append(entry)

        except Exception as e:
            logger.warning(f"Failed to convert raw decision to entry: {e}")
            continue

    return entries


# =============================================================================
# Main Entry Point
# =============================================================================


async def extract_decisions_from_response(
    response_text: str,
    subtask_id: str | None = None,
    phase: str | None = None,
    project_dir: Path | None = None,
) -> list[DecisionEntry]:
    """
    Extract decisions from an agent response.

    This is the main entry point for decision extraction. It analyzes agent
    response text and extracts structured decisions with reasoning.

    Args:
        response_text: The agent's response text to analyze
        subtask_id: Current subtask ID (for context)
        phase: Current phase (for context)
        project_dir: Project directory (optional)

    Returns:
        List of DecisionEntry objects (empty if extraction fails or disabled)
    """
    # Check if extraction is enabled
    if not is_decision_extraction_enabled():
        logger.debug("Decision extraction disabled")
        return []

    # Skip empty responses
    if not response_text or not response_text.strip():
        logger.debug("No response text to extract decisions from")
        return []

    # Skip very short responses (unlikely to contain decisions)
    if len(response_text.strip()) < 100:
        logger.debug("Response too short for meaningful decision extraction")
        return []

    try:
        # Build prompt
        prompt = _build_extraction_prompt(response_text, subtask_id)

        # Run extraction
        result = await _run_extraction(prompt, project_dir)

        if not result:
            logger.debug("Extraction returned no results")
            return []

        raw_decisions = result.get("decisions", [])

        if not raw_decisions:
            logger.debug("No decisions found in response")
            return []

        # Convert to DecisionEntry objects
        entries = _convert_to_decision_entries(raw_decisions, subtask_id, phase)

        logger.info(
            f"Extracted {len(entries)} decisions from response "
            f"(subtask={subtask_id}, phase={phase})"
        )

        return entries

    except Exception as e:
        logger.warning(f"Decision extraction failed: {e}")
        return []


# =============================================================================
# Synchronous Wrapper (for compatibility)
# =============================================================================


def extract_decisions_sync(
    response_text: str,
    subtask_id: str | None = None,
    phase: str | None = None,
    project_dir: Path | None = None,
) -> list[DecisionEntry]:
    """
    Synchronous wrapper for extract_decisions_from_response.

    Use this in synchronous contexts. For async contexts, prefer the
    async version directly.
    """
    import asyncio

    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            # If we're in an async context, create a new task
            import concurrent.futures

            with concurrent.futures.ThreadPoolExecutor() as executor:
                future = executor.submit(
                    asyncio.run,
                    extract_decisions_from_response(
                        response_text, subtask_id, phase, project_dir
                    ),
                )
                return future.result(timeout=60)
        else:
            return loop.run_until_complete(
                extract_decisions_from_response(
                    response_text, subtask_id, phase, project_dir
                )
            )
    except Exception:
        # If there's no event loop, create one
        return asyncio.run(
            extract_decisions_from_response(
                response_text, subtask_id, phase, project_dir
            )
        )


# =============================================================================
# CLI for Testing
# =============================================================================

if __name__ == "__main__":
    import argparse
    import asyncio

    parser = argparse.ArgumentParser(description="Test decision extraction")
    parser.add_argument(
        "--response-file",
        type=Path,
        help="File containing agent response to analyze",
    )
    parser.add_argument(
        "--response-text",
        type=str,
        help="Direct response text to analyze",
    )
    parser.add_argument(
        "--subtask-id",
        type=str,
        default="test-subtask",
        help="Subtask ID for context",
    )
    parser.add_argument(
        "--phase",
        type=str,
        default="test-phase",
        help="Phase for context",
    )

    args = parser.parse_args()

    async def main():
        if args.response_file:
            response_text = args.response_file.read_text(encoding="utf-8")
        elif args.response_text:
            response_text = args.response_text
        else:
            # Example response for testing
            response_text = """
I've decided to use the existing UserModel class for authentication rather than
creating a new one. This follows the established patterns in the codebase.

I considered:
1. Creating a new AuthUser class - rejected because it duplicates functionality
2. Using a third-party library - rejected due to dependency concerns

The existing patterns in models/user.py show how to handle authentication tokens,
so I'll follow that approach.
"""

        decisions = await extract_decisions_from_response(
            response_text=response_text,
            subtask_id=args.subtask_id,
            phase=args.phase,
        )

        print(f"\nExtracted {len(decisions)} decisions:\n")
        for dec in decisions:
            print(json.dumps(dec.to_dict(), indent=2))
            print()

    asyncio.run(main())
