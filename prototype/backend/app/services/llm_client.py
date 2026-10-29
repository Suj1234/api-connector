"""LLMClient (TRD §2, §8): one interface, swappable provider. Gemini first.

Schema-constrained JSON output. The prompt only ever holds public docs, masked samples and
scrubbed hints. Cost and timing are returned for llm_calls; prompt text is never stored.
"""

from __future__ import annotations

import json
import time
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol

from app.config import PROTOTYPE, get

PRICES_FILE = PROTOTYPE / "benchmark" / "prices.json"


class LLMError(Exception):
    pass


@dataclass(frozen=True)
class LLMResult:
    data: dict[str, Any]
    model: str
    input_tokens: int
    output_tokens: int
    ms: int
    cost_usd: float


class LLMClient(Protocol):
    def generate_json(self, *, model: str, system: str, prompt: str, schema: dict[str, Any]) -> LLMResult: ...


def price(model: str, input_tokens: int, output_tokens: int, prices_file: Path = PRICES_FILE) -> float:
    try:
        table = json.loads(prices_file.read_text())["models"]
    except (OSError, KeyError, ValueError):
        return 0.0
    rate = table.get(model)
    if not rate:
        return 0.0
    cost = input_tokens / 1e6 * float(rate["input_per_m"]) + output_tokens / 1e6 * float(rate["output_per_m"])
    return round(cost, 6)


class GeminiClient:
    """Google Gen AI SDK (google-genai). Uses the paid-tier key in GEMINI_API_KEY only."""

    def __init__(self, api_key: str | None = None) -> None:
        from google import genai

        key = api_key or get("GEMINI_API_KEY")
        if not key:
            raise LLMError("GEMINI_API_KEY is not set")
        # Pass the key explicitly so a stray GOOGLE_API_KEY in the environment is never used.
        self._client = genai.Client(api_key=key)

    def generate_json(self, *, model: str, system: str, prompt: str, schema: dict[str, Any]) -> LLMResult:
        from google.genai import types

        config = types.GenerateContentConfig(
            system_instruction=system,
            response_mime_type="application/json",
            response_json_schema=schema,
            temperature=0.1,
        )
        start = time.monotonic()
        try:
            response = self._client.models.generate_content(model=model, contents=prompt, config=config)
        except Exception as error:  # noqa: BLE001 - the SDK raises many types; the message has no prompt text
            raise LLMError(f"{type(error).__name__}: {str(error)[:300]}") from None
        ms = int((time.monotonic() - start) * 1000)
        try:
            data = json.loads(response.text or "")
        except ValueError as error:
            raise LLMError("the model did not return JSON") from error
        usage = response.usage_metadata
        input_tokens = int(getattr(usage, "prompt_token_count", 0) or 0)
        output_tokens = int(getattr(usage, "candidates_token_count", 0) or 0)
        output_tokens += int(getattr(usage, "thoughts_token_count", 0) or 0)  # thinking is billed as output
        return LLMResult(data, model, input_tokens, output_tokens, ms, price(model, input_tokens, output_tokens))


class ScriptedLLM:
    """Test double: returns prepared answers in order and records what it was asked (for leak checks)."""

    def __init__(self, answers: list[dict[str, Any] | Callable[[str], dict[str, Any]]]) -> None:
        self.answers = list(answers)
        self.prompts: list[str] = []
        self.models: list[str] = []

    def generate_json(self, *, model: str, system: str, prompt: str, schema: dict[str, Any]) -> LLMResult:
        self.prompts.append(system + "\n" + prompt)
        self.models.append(model)
        if not self.answers:
            raise LLMError("no scripted answer left")
        answer = self.answers.pop(0)
        data = answer(prompt) if callable(answer) else answer
        return LLMResult(json.loads(json.dumps(data)), model, len(prompt) // 4, 2000, 5, 0.0)
