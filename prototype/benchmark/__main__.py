"""Model benchmark (EVAL §2).

    python -m benchmark --apps zendesk calendly notion \
        --models gemini-3.5-flash-lite gemini-3.8-flash gemini-4-argon --runs 3

Each run drafts a spec from the app's public docs with one model, then tests it on the replay
recording (with repair), and scores it against the hand-written golden spec and expected users.
Docs are fetched once and cached in data/docs_cache/, so every model reads the same docs.
`--models oracle` scores the golden specs themselves: a check of the harness, no LLM needed.

Writes benchmark/results.csv and benchmark/results.md.
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from app.services.docs_fetcher import DocPage, DocsBundle, Fetcher  # noqa: E402
from app.services.draft_convert import spec_to_draft  # noqa: E402
from app.services.llm_client import GeminiClient, LLMResult  # noqa: E402
from app.services.pipeline import Pipeline, PipelineError, Settings  # noqa: E402

DOCS_URLS = {
    "calendly": "https://developer.calendly.com/api-docs",
    "zendesk": "https://developer.zendesk.com/api-reference/ticketing/users/users/",
    "notion": "https://developers.notion.com/reference/get-users",
}
CACHE = ROOT / "data" / "docs_cache"
OUT = ROOT / "benchmark"


@dataclass
class Row:
    app: str
    model: str
    run: int
    schema_valid: bool
    evidence_verified_pct: float
    test_pass: bool
    user_count_match: bool
    usage_match: bool
    repairs: int
    cost_usd: float
    seconds: float
    error: str = ""


class OracleLLM:
    """Answers with the golden spec: proves the harness, not a model."""

    def __init__(self, spec: dict[str, Any]) -> None:
        self.spec = spec

    def generate_json(self, *, model: str, system: str, prompt: str, schema: dict[str, Any]) -> LLMResult:
        if "users_stream" not in schema.get("properties", {}):
            return LLMResult({"diagnosis": "oracle", "patch": []}, model, 0, 0, 0, 0.0)
        data = spec_to_draft(self.spec)
        # One placeholder citation so the spec is well-formed; the evidence check rightly fails it.
        data["evidence"] = [
            {"field": "/base_url", "url": self.spec["app"]["docs_url"], "quote": "oracle", "openapi_pointer": None}
        ]
        return LLMResult(data, model, 0, 0, 0, 0.0)


def load_docs(app: str) -> DocsBundle:
    CACHE.mkdir(parents=True, exist_ok=True)
    cached = CACHE / f"{app}.json"
    if cached.exists():
        data = json.loads(cached.read_text())
        pages = [DocPage(**p) for p in data["pages"]]
        return DocsBundle(data["start_url"], pages, data.get("openapi"), data.get("openapi_url"))
    bundle = Fetcher().fetch(DOCS_URLS[app], max_pages=60)
    cached.write_text(
        json.dumps(
            {
                "start_url": bundle.start_url,
                "pages": [asdict(p) for p in bundle.pages],
                "openapi": bundle.openapi,
                "openapi_url": bundle.openapi_url,
            }
        )
    )
    return bundle


def score(app: str, model: str, run: int) -> Row:
    golden = json.loads((ROOT / "specs" / "examples" / f"{app}.json").read_text())
    expected = json.loads((ROOT / "fixtures" / "replay" / app / "expected.json").read_text())
    oracle = model == "oracle"
    llm: Any = OracleLLM(golden) if oracle else GeminiClient()
    bundle = DocsBundle(DOCS_URLS[app]) if oracle else load_docs(app)
    settings = Settings(
        draft_model=model if not oracle else "oracle", escalate_model="gemini-4-argon" if not oracle else "oracle"
    )
    settings.sandbox = "docker" if _docker() else "subprocess"
    pipe = Pipeline(llm, Fetcher(), lambda event: None, settings)
    start = time.monotonic()
    row = Row(app, model, run, False, 0.0, False, False, False, 0, 0.0, 0.0)
    try:
        drafted = pipe.draft(golden["app"]["name"], DOCS_URLS[app], bundle=bundle)
        row.schema_valid = True
        row.evidence_verified_pct = round(drafted.evidence.verified_pct, 1)
        payload = {"run_mode": "replay", "replay_file": str(ROOT / "fixtures" / "replay" / app / "recording.json")}
        tested = pipe.test(drafted.spec, payload, drafted.bundle)
        calls = drafted.llm_calls + tested.llm_calls
        row.cost_usd = round(sum(c.cost_usd for c in calls), 4)
        row.repairs = len(tested.repairs)
        row.test_pass = tested.result.exit_code == 0
        ids = {r["external_id"] for r in tested.result.records}
        row.user_count_match = row.test_pass and ids == set(expected)
        row.usage_match = _usage_match(tested.spec, golden)
        if not row.test_pass:
            row.error = str(tested.result.result.get("error_code"))
    except PipelineError as error:
        row.error = error.code
    row.seconds = round(time.monotonic() - start, 1)
    return row


def _usage_match(spec: dict[str, Any], golden: dict[str, Any]) -> bool:
    a, b = spec["usage_definition"], golden["usage_definition"]
    return (
        spec["app"]["tier"] == golden["app"]["tier"]
        and (spec["streams"]["usage"] is None) == (golden["streams"]["usage"] is None)
        and a.get("fallback") == b.get("fallback")
        and (a.get("active_rule") or {}).get("field") == (b.get("active_rule") or {}).get("field")
        and (a.get("active_rule") or {}).get("op") == (b.get("active_rule") or {}).get("op")
    )


def _docker() -> bool:
    from app.services.sandbox import docker_available

    return docker_available()


def summarise(rows: list[Row]) -> str:
    models = sorted({r.model for r in rows})
    lines = [
        "# Model benchmark results",
        "",
        f"{len(rows)} drafts. Test runs use replay recordings (EVAL §2.2). Cost from benchmark/prices.json.",
        "",
        "| Model | Schema valid | Evidence verified | Test pass | User count match | Usage match | Avg repairs | Avg $ | Avg s |",
        "|---|---|---|---|---|---|---|---|---|",
    ]
    best: tuple[Any, ...] | None = None
    for model in models:
        mine = [r for r in rows if r.model == model]
        n = len(mine)
        passed = sum(r.test_pass for r in mine)
        repairs = sum(r.repairs for r in mine) / n
        cost = sum(r.cost_usd for r in mine) / n
        lines.append(
            f"| `{model}` | {sum(r.schema_valid for r in mine)}/{n} | {sum(r.evidence_verified_pct for r in mine) / n:.0f}% "
            f"| {passed}/{n} | {sum(r.user_count_match for r in mine)}/{n} | {sum(r.usage_match for r in mine)}/{n} "
            f"| {repairs:.1f} | {cost:.3f} | {sum(r.seconds for r in mine) / n:.0f} |"
        )
        key = (-passed, repairs, cost)  # EVAL §2.4: pass rate, then repairs, then cost
        if model != "oracle" and (best is None or key < best[0]):
            best = (key, model, passed, n, repairs, cost)
    if best is not None:
        _, model, passed, n, repairs, cost = best
        lines += [
            "",
            f"**We use `{model}`: {passed}/{n} passed, {repairs:.1f} repairs on average, ${cost:.2f} per connector.**",
        ]
    failures = [r for r in rows if r.error]
    if failures:
        lines += ["", "Failures:", *(f"- {r.app} / {r.model} / run {r.run}: {r.error}" for r in failures)]
    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(prog="benchmark")
    parser.add_argument("--apps", nargs="+", default=list(DOCS_URLS))
    parser.add_argument("--models", nargs="+", default=["gemini-3.5-flash-lite", "gemini-3.8-flash", "gemini-4-argon"])
    parser.add_argument("--runs", type=int, default=3)
    parser.add_argument("--out", type=Path, default=OUT)
    args = parser.parse_args()
    rows = []
    for app in args.apps:
        for model in args.models:
            for run in range(1, args.runs + 1):
                row = score(app, model, run)
                print(f"{app:9} {model:22} run {run}: pass={row.test_pass} users={row.user_count_match} {row.error}")
                rows.append(row)
    args.out.mkdir(parents=True, exist_ok=True)
    with open(args.out / "results.csv", "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(asdict(rows[0])))
        writer.writeheader()
        writer.writerows(asdict(r) for r in rows)
    (args.out / "results.md").write_text(summarise(rows))
    print(f"Wrote {args.out / 'results.csv'} and {args.out / 'results.md'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
