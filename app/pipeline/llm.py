"""The AI that writes answers (D6). Provider chosen with LLM_PROVIDER: anthropic or mock.

- anthropic: Claude Haiku 5.5 (LLM_MODEL to change), needs ANTHROPIC_API_KEY in .env (never committed).
- mock:      no key, no network. Answers with the first sentence of the best passage. NOT AI:
             for trying the app and for tests only, never for evaluation results.
"""
from __future__ import annotations

import os
import re
from dataclasses import dataclass
from typing import Literal

from pydantic import BaseModel

try:  # load keys from a local .env file if present
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

DEFAULT_MODELS = {"anthropic": "claude-haiku-5-5", "mock": "mock-first-sentence"}


class Reply(BaseModel):
    """The fixed format the AI must reply in (D5). The API checks it against this schema."""
    status: Literal["found", "not_found"]
    answer: str
    source_ids: list[str]


@dataclass
class Usage:
    model: str
    input_tokens: int = 0
    output_tokens: int = 0


class LLMError(RuntimeError):
    """The AI could not be reached or gave no usable reply. Message is safe to show users."""


def provider() -> str:
    return os.getenv("LLM_PROVIDER", "mock").lower()


def model_name() -> str:
    return os.getenv("LLM_MODEL", DEFAULT_MODELS.get(provider(), "unknown"))


def complete(system: str, user: str) -> tuple[Reply | None, Usage]:
    """Send one question with its passages. Returns (reply, usage); reply is None if unusable."""
    p = provider()
    if p == "anthropic":
        return _anthropic(system, user)
    if p == "mock":
        return _mock(user), Usage(model_name())
    raise LLMError(f"Unknown LLM_PROVIDER '{p}'. Use anthropic or mock.")


def _anthropic(system: str, user: str) -> tuple[Reply | None, Usage]:
    import anthropic
    client = anthropic.Anthropic()
    try:
        # messages.parse checks the reply against Reply, so the answer always has the fixed fields.
        # Haiku 5.5 thinks before answering and its thinking counts towards max_tokens, so allow room.
        # Effort "low" keeps answers fast; the experiments can compare higher levels.
        response = client.messages.parse(
            model=model_name(), max_tokens=4000, system=system,
            messages=[{"role": "user", "content": user}],
            output_format=Reply,
            output_config={"effort": os.getenv("LLM_EFFORT", "low")},
        )
    except anthropic.AuthenticationError as exc:
        raise LLMError("The API key was rejected. Check ANTHROPIC_API_KEY in your .env file.") from exc
    except anthropic.RateLimitError as exc:
        raise LLMError("Too many requests to the AI just now. Please wait a moment and try again.") from exc
    except anthropic.APIConnectionError as exc:
        raise LLMError("Could not reach the AI service. Check the internet connection.") from exc
    except anthropic.APIStatusError as exc:
        raise LLMError(f"The AI service returned an error ({exc.status_code}). Please try again.") from exc
    usage = Usage(response.model, response.usage.input_tokens, response.usage.output_tokens)
    # A refusal or a reply cut off at max_tokens has no parsed output: treated as "not found" upstream.
    reply = response.parsed_output if response.stop_reason == "end_turn" else None
    return reply, usage


def _mock(user: str) -> Reply:
    m = re.search(r"\[(P\d+)\][^\n]*\n(.+?)(?:\n\n|$)", user, re.S)
    if not m:
        return Reply(status="not_found", answer="The passages do not cover this.", source_ids=[])
    first = re.split(r"(?<=[.!?])\s", m.group(2).strip(), maxsplit=1)[0]
    return Reply(status="found", answer=first, source_ids=[m.group(1)])
