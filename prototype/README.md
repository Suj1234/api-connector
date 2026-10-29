# Prototype: run it

The working prototype of the AI-generated integration builder. Product: [`../PRD.md`](../PRD.md). Build spec: [`../TRD.md`](../TRD.md). Design: [`../DESIGN.md`](../DESIGN.md). Tests: [`../EVAL.md`](../EVAL.md).

## What you need

- Python 3.12 or newer
- Node 20 or newer (for the UI)
- Docker Desktop (for the real sandbox; without it, runs fall back to a subprocess labelled "demo isolation only")
- A Gemini API key with billing on (paid tier). Without one, the app runs on recorded answers and says so on every screen.

## First-time setup (Mac)

```bash
cd prototype
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

cp .env.example .env
# In .env: set GEMINI_API_KEY, and a vault key:
python -c "import base64, os; print('VAULT_KEY=' + base64.b64encode(os.urandom(32)).decode())" >> .env

./docker/build.sh                      # the two sandbox images (runner + egress proxy)
(cd frontend && npm install && npm run build)
```

Never set `GOOGLE_API_KEY`: the SDK would use it instead of `GEMINI_API_KEY`. Never commit `.env`.

## Run

```bash
cd prototype/backend
PYTHONPATH=.:.. ../.venv/bin/python -m uvicorn app.api:app --port 8000
```

Open http://localhost:8000. Switch tenants top left:

| Tenant | Runs on | Use it for |
|---|---|---|
| Acme · Demo data | Recorded responses, fake people (`fixtures/`) | The savings story: 48 users, 6 left, 11 inactive, $6,960 a year |
| Globex · Live | The real vendor APIs, with your own tokens | Proving the code works on a real account |
| Platform team | — | Library review queue (approve before any other tenant sees a connector) |

To start again from a clean slate, stop the server and delete `data/app.db`.

## The 5-minute demo (PRD §15)

1. Acme → App inventory → Calendly → **Connect usage data** → **Build with AI** (docs link is pre-filled).
2. **What we found**: open **View evidence** and show the quotes and the rate-limit conflict chip.
3. **Looks right** → **Run test** → open **Generated code** (the six items are highlighted).
4. **See the savings** → **Go live** → **Submit to library**.
5. Switch to **Platform team** → open Calendly → **Approve to library**.
6. Switch to **Globex** → Calendly shows **In library** → paste Globex's own token → its own test runs.
7. Surprise app: back in Acme, build any app from its public docs.

Backup: the same flow, clicked by a script, recorded as a video:

```bash
npm i -g playwright && npx playwright install chromium
rm -f data/app.db   # then restart the server
RECORD_VIDEO=1 NODE_PATH=$(npm root -g) node scripts/demo-walkthrough.mjs   # → data/demo-video/
```

## Tests

```bash
cd prototype && source .venv/bin/activate
pytest                      # all tests; Docker tests skip if the images aren't built
ruff check . && mypy        # lint and strict types
```

| What | Command |
|---|---|
| Model benchmark (EVAL §2) | `python -m benchmark --apps zendesk calendly notion --models gemini-3.5-flash-lite gemini-3.8-flash gemini-4-argon --runs 3` |
| Harness check without any model | `python -m benchmark --models oracle --runs 1` |
| Live tests (real accounts) | Fill the `CALENDLY_*`, `ZENDESK_*`, `NOTION_*` keys in `.env`, then `pytest tests/live` |
| Record a live run, scrubbed | `PYTHONPATH=backend:. python -m app.tools.record calendly` |
| Regenerate the example connectors | `PYTHONPATH=backend python -m app.services.codegen` |
| Regenerate the demo data | `python fixtures/make_demo_data.py` |

## Where things are

```
backend/app/        API (api.py), models, services: spec_validator, codegen (+ template),
                    docs_fetcher, ssrf_guard, ranker, llm_client, evidence_check, repair,
                    pipeline, sandbox, vault, savings
backend/runtime/    what generated connectors import: transports, helpers, logging, errors
backend/runner/     the sandbox entry point (TRD §6)
connectors/examples generated code for the three example specs (read these)
specs/examples/     hand-written golden specs (Zendesk, Calendly, Notion)
schemas/            the connector spec schema and the flattened schema the AI fills
fixtures/           fake Acme data, replay recordings, docs fixtures for tests
docker/             runner and egress-proxy images
frontend/           React UI (screens F1–F8)
benchmark/          model benchmark and dated prices
tests/              unit, contract, security, api, live
```
