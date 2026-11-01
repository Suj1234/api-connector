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
| Acme · Sample data | Recorded responses, fake people (`fixtures/`) | The savings story: 48 users, 6 left, 11 inactive, $6,960 a year |
| Globex · Live | The real vendor APIs, with your own tokens | Proving the code works on a real account |
| Platform team | — | Library review queue (approve before any other tenant sees a connector) |

To start again from a clean slate, stop the server and delete `data/app.db`. The next start builds the three sample apps (Zendesk, Notion, Slack) in the background, in about a minute; `SAMPLE_APPS=0` turns that off.

## The 5-minute demo (PRD §15)

1. **App inventory**: Zendesk, Notion and Slack are connected on sample data; open Slack's page to show the users.
2. **+ Add an app**: Calendly, Marketing Ops, $14,400, 60 seats, renews 26 Dec 2026, docs link `https://developer.calendly.com/api-docs` → **Build with AI** (about 1.5 minutes with live Gemini).
3. **Review what we found**: click a **Proved** badge to show its quote.
4. **Looks right** → **Run test** → the **Generated code** tab (the six items are highlighted) → **Continue**.
5. **Check the savings** → **Go live** → Calendly's page with its 48 users.
6. Surprise app: **+ Add an app** with any app's public docs.

The tenant switcher, the library and the platform review steps are built but hidden for now (PRD §15).

Screenshots of every screen, and a check that the whole flow works: a script clicks through the same steps and stops at the first one that breaks.

```bash
npm i -g playwright   # it uses your installed Google Chrome if Playwright's own browser isn't downloaded
rm -f data/app.db     # then restart the server: the script needs a fresh database (no Calendly yet)
NODE_PATH=$(npm root -g) node scripts/demo-walkthrough.mjs   # → data/demo-shots/
```

When the app asks to log in, add `DEMO_USERNAME=… DEMO_PASSWORD=…` in front of the last command.

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
specs/examples/     hand-written golden specs (Zendesk, Calendly, Notion, and the Slack sample)
schemas/            the connector spec schema and the flattened schema the AI fills
fixtures/           fake Acme data, replay recordings, docs fixtures for tests
docker/             runner and egress-proxy images
frontend/           React UI (screens F1–F8)
benchmark/          model benchmark and dated prices
tests/              unit, contract, security, api, live
```
