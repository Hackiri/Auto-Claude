"""
Large Response Summarization

This module provides automatic summarization for large tool responses
using Claude Haiku, with graceful fallback to truncation.

Inspired by Craft Agents OSS summarize.ts
"""

import asyncio
import logging
from dataclasses import dataclass

logger = logging.getLogger(__name__)

# Token thresholds
TOKEN_LIMIT = 15000  # ~60KB trigger threshold (4 chars per token)
MAX_SUMMARIZATION_INPUT = 100000  # ~400KB max to Haiku
MAX_TRUNCATION_CHARS = 40000  # Fallback truncation size

# Haiku model for summarization
SUMMARIZATION_MODEL = "claude-3-5-haiku-20241022"
MAX_SUMMARY_TOKENS = 4096


@dataclass
class SummarizationContext:
    """
    Context for summarization to help Haiku extract relevant info.

    Attributes:
        tool_name: Name of the tool that produced the result
        path: Optional endpoint/file path context
        input_params: Optional input parameters used
        model_intent: The AI's stated goal (most specific context)
        user_request: The user's original request (fallback context)
    """

    tool_name: str
    path: str | None = None
    input_params: dict | None = None
    model_intent: str | None = None
    user_request: str | None = None


def estimate_tokens(text: str) -> int:
    """
    Rough token count estimation.

    Uses ~4 characters per token as approximation.
    This is intentionally conservative for safety.

    Args:
        text: The text to estimate tokens for

    Returns:
        Estimated token count
    """
    return len(text) // 4


def needs_summarization(response: str, threshold: int = TOKEN_LIMIT) -> bool:
    """
    Check if a response exceeds the summarization threshold.

    Args:
        response: The response text to check
        threshold: Token threshold (default TOKEN_LIMIT)

    Returns:
        True if response should be summarized
    """
    return estimate_tokens(response) > threshold


def truncate_response(response: str, max_chars: int = MAX_TRUNCATION_CHARS) -> str:
    """
    Simple truncation fallback for when summarization fails.

    Args:
        response: The response to truncate
        max_chars: Maximum characters to keep

    Returns:
        Truncated response with indicator
    """
    if len(response) <= max_chars:
        return response

    return response[:max_chars] + "\n\n[Result truncated due to size]"


def _build_summarization_prompt(response: str, context: SummarizationContext) -> str:
    """
    Build the prompt for Haiku summarization.

    Args:
        response: The response to summarize
        context: Context about the tool and intent

    Returns:
        Formatted prompt string
    """
    prompt_parts = [
        "Summarize this tool result. Extract the MOST RELEVANT information for the task at hand.",
        "",
        f"Tool: {context.tool_name}",
    ]

    if context.path:
        prompt_parts.append(f"Endpoint/Path: {context.path}")

    if context.model_intent:
        # Truncate intent to last 500 chars to fit in context
        intent = (
            context.model_intent[-500:]
            if len(context.model_intent) > 500
            else context.model_intent
        )
        prompt_parts.append(f"Goal: {intent}")
    elif context.user_request:
        request = (
            context.user_request[-300:]
            if len(context.user_request) > 300
            else context.user_request
        )
        prompt_parts.append(f"User Request: {request}")

    prompt_parts.extend(
        [
            "",
            "Guidelines:",
            "- Focus on information directly relevant to the stated goal",
            "- Preserve important data, identifiers, and error messages",
            "- Omit verbose output, logs, and repetitive content",
            "- Keep the summary concise but complete for the task",
            "",
            "Result to summarize:",
            response,
        ]
    )

    return "\n".join(prompt_parts)


async def summarize_large_result(
    response: str, context: SummarizationContext, force: bool = False
) -> str:
    """
    Summarize a large tool result using Claude Haiku.

    This function will:
    1. Check if summarization is needed (unless force=True)
    2. Truncate input if necessary for Haiku
    3. Call Haiku for summarization
    4. Gracefully fallback to truncation on error

    Args:
        response: The response to potentially summarize
        context: Context about the tool and intent
        force: Force summarization even if under threshold

    Returns:
        Original response, summary, or truncated response
    """
    # Check if summarization is needed
    if not force and not needs_summarization(response):
        return response

    # Truncate for Haiku input if needed
    max_input_chars = MAX_SUMMARIZATION_INPUT * 4
    truncated_input = (
        response[:max_input_chars] if len(response) > max_input_chars else response
    )

    try:
        # Lazy import to avoid circular dependencies and startup cost
        import anthropic

        client = anthropic.Anthropic()
        prompt = _build_summarization_prompt(truncated_input, context)

        result = client.messages.create(
            model=SUMMARIZATION_MODEL,
            max_tokens=MAX_SUMMARY_TOKENS,
            messages=[{"role": "user", "content": prompt}],
        )

        # Extract text from response
        if result.content and len(result.content) > 0:
            summary = result.content[0].text
            logger.debug(
                f"Summarized {estimate_tokens(response)} tokens to {estimate_tokens(summary)} tokens"
            )
            return summary

        # Unexpected response format, fall back to truncation
        logger.warning("Unexpected Haiku response format, falling back to truncation")
        return truncate_response(response)

    except ImportError:
        logger.warning("anthropic package not available, falling back to truncation")
        return truncate_response(response)
    except Exception as e:
        logger.warning(
            f"Summarization failed ({type(e).__name__}: {e}), falling back to truncation"
        )
        return truncate_response(response)


def summarize_large_result_sync(
    response: str, context: SummarizationContext, force: bool = False
) -> str:
    """
    Synchronous wrapper for summarize_large_result.

    Args:
        response: The response to potentially summarize
        context: Context about the tool and intent
        force: Force summarization even if under threshold

    Returns:
        Original response, summary, or truncated response
    """
    # Check if summarization is needed before async overhead
    if not force and not needs_summarization(response):
        return response

    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            # We're in an async context, need to use a new loop
            import concurrent.futures

            with concurrent.futures.ThreadPoolExecutor() as executor:
                future = executor.submit(
                    asyncio.run, summarize_large_result(response, context, force)
                )
                return future.result(timeout=30)
        else:
            return loop.run_until_complete(
                summarize_large_result(response, context, force)
            )
    except RuntimeError:
        # No event loop, create one
        return asyncio.run(summarize_large_result(response, context, force))


class ResponseSummarizer:
    """
    Stateful summarizer with caching and lazy client initialization.

    Usage:
        summarizer = ResponseSummarizer()
        result = summarizer.maybe_summarize(large_response, context)
    """

    def __init__(self):
        self._client = None

    def _get_client(self):
        """Lazy client initialization."""
        if self._client is None:
            try:
                import anthropic

                self._client = anthropic.Anthropic()
            except ImportError:
                pass
        return self._client

    def reset_client(self):
        """Reset client (useful for credential changes)."""
        self._client = None

    def maybe_summarize(
        self, response: str, context: SummarizationContext, force: bool = False
    ) -> str:
        """
        Summarize if needed, with client reuse.

        Args:
            response: The response to potentially summarize
            context: Context about the tool and intent
            force: Force summarization even if under threshold

        Returns:
            Original response, summary, or truncated response
        """
        if not force and not needs_summarization(response):
            return response

        client = self._get_client()
        if client is None:
            return truncate_response(response)

        # Truncate for input
        max_input_chars = MAX_SUMMARIZATION_INPUT * 4
        truncated_input = (
            response[:max_input_chars] if len(response) > max_input_chars else response
        )

        try:
            prompt = _build_summarization_prompt(truncated_input, context)
            result = client.messages.create(
                model=SUMMARIZATION_MODEL,
                max_tokens=MAX_SUMMARY_TOKENS,
                messages=[{"role": "user", "content": prompt}],
            )

            if result.content and len(result.content) > 0:
                return result.content[0].text

            return truncate_response(response)

        except Exception as e:
            logger.warning(f"Summarization failed: {e}")
            return truncate_response(response)


# Global instance for convenience
_default_summarizer: ResponseSummarizer | None = None


def get_summarizer() -> ResponseSummarizer:
    """Get or create the default summarizer instance."""
    global _default_summarizer
    if _default_summarizer is None:
        _default_summarizer = ResponseSummarizer()
    return _default_summarizer
