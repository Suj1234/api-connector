"""Which "AI" answers a draft: Gemini (live), or a recorded answer for offline demos and tests.

recorded mode never pretends to be a model call. The UI labels it:
- "Recorded AI answer": a real Gemini draft saved earlier to data/ai_recordings/<app>.json.
- "Hand-written spec": no AI answer was ever recorded for this app; the golden spec stands in.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from app.config import PROTOTYPE, get
from app.services.codegen import slug_for
from app.services.draft_convert import spec_to_draft
from app.services.llm_client import GeminiClient, LLMClient, LLMError, LLMResult
from app.services.repair import PATCH_SCHEMA

RECORDINGS = PROTOTYPE / "data" / "ai_recordings"
EXAMPLES = PROTOTYPE / "specs" / "examples"


def provider() -> str:
    configured = get("LLM_PROVIDER", "gemini")
    if configured == "gemini" and not get("GEMINI_API_KEY"):
        return "recorded"
    return configured


class RecordedLLM:
    def __init__(self, app_name: str) -> None:
        self.app_name = app_name
        slug = slug_for(app_name)
        recorded = RECORDINGS / f"{slug}.json"
        golden = EXAMPLES / f"{slug}.json"
        self.draft: dict[str, Any] | None = None
        self.label = "No AI available"
        if recorded.exists():
            self.draft = json.loads(recorded.read_text())
            self.label = "Recorded AI answer (no live model call)"
        elif golden.exists():
            spec = json.loads(golden.read_text())
            self.draft = spec_to_draft(spec)
            # Points at the docs without a quote: the evidence check rightly marks every field unproved.
            self.draft["evidence"] = [
                {"field": "/base_url", "url": spec["app"]["docs_url"], "quote": "hand-written", "openapi_pointer": None}
            ]
            self.label = "Hand-written spec (no AI in this run)"

    def generate_json(self, *, model: str, system: str, prompt: str, schema: dict[str, Any]) -> LLMResult:
        if schema is PATCH_SCHEMA or "patch" in schema.get("properties", {}):
            raise LLMError("Repairs need a live model (set GEMINI_API_KEY)")
        if self.draft is None:
            raise LLMError(f"No AI is configured and nothing is recorded for {self.app_name}: set GEMINI_API_KEY")
        return LLMResult(json.loads(json.dumps(self.draft)), "recorded", 0, 0, 0, 0.0)


def llm_for(app_name: str) -> tuple[LLMClient, str]:
    if provider() == "gemini":
        return GeminiClient(), "Gemini"
    recorded = RecordedLLM(app_name)
    return recorded, recorded.label


def save_recording(app_name: str, draft: dict[str, Any]) -> Path:
    """Keep each live Gemini draft so the demo can run offline later, honestly labelled."""
    RECORDINGS.mkdir(parents=True, exist_ok=True)
    path = RECORDINGS / f"{slug_for(app_name)}.json"
    path.write_text(json.dumps(draft, indent=1))
    return path
