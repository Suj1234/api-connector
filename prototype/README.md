# Prototype

The working prototype of the AI-generated integration builder. Product: [`../PRD.md`](../PRD.md). How it is built: [`../TRD.md`](../TRD.md). Design: [`../DESIGN.md`](../DESIGN.md). Tests: [`../EVAL.md`](../EVAL.md).

**Live:** https://integration-builder-five.vercel.app (login by invite).

## Run it locally

You need Python 3.12 or newer, Node 20 or newer, and a Gemini API key with billing on (paid tier). Without a key, the app drafts from saved answers and says so on every screen.

```bash
cd prototype
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
(cd frontend && npm install && npm run build)

cp .env.example .env        # then set GEMINI_API_KEY in .env
```

Never set `GOOGLE_API_KEY` (the SDK would use it instead of `GEMINI_API_KEY`), and never commit `.env`.

```bash
cd backend
PYTHONPATH=.:.. ../.venv/bin/python -m uvicorn app.api:app --port 8000
```

Open http://localhost:8000. The first start fills a sample company (Acme, fake people) and builds Zendesk, Notion and Slack on sample data, in about a minute. To start again, stop the server and delete `data/app.db`. Leave `DEMO_USERNAME` and `DEMO_PASSWORD` empty locally to skip the login.

## Test it

```bash
cd prototype && source .venv/bin/activate
pytest                                   # unit, contract, API flow and security tests
ruff check . && mypy                     # lint and strict types
(cd frontend && npx tsc --noEmit -p .)   # frontend types
```

| What | Command |
|---|---|
| Model benchmark (`EVAL.md` §2) | `python -m benchmark --apps zendesk calendly notion --models gemini-3.5-flash-lite gemini-3.8-flash gemini-4-argon --runs 3` |
| Benchmark harness check, no model | `python -m benchmark --models oracle --runs 1` |
| Live tests with real accounts | Fill the `CALENDLY_*`, `ZENDESK_*`, `NOTION_*` keys in `.env`, then `pytest tests/live` |
| Record a live run, scrubbed | `PYTHONPATH=backend:. python -m app.tools.record calendly` |
| Regenerate the example connectors | `PYTHONPATH=backend python -m app.services.codegen` |
| Regenerate the sample data | `python fixtures/make_demo_data.py` |

## Deploy

A push to `main` on GitHub deploys to Vercel (project `integration-builder`) in about a minute. The database is Neon Postgres, connected through Vercel's Neon integration. Settings, limits and how to reset the hosted data: `TRD.md` §2.1.

## Where things are

```
api/index.py        the Vercel entry point
backend/app/        API (api.py), seed data (db.py), tables, services: docs reader, SSRF guard,
                    ranker, Gemini client, AI pipeline, evidence and rule checks, codegen,
                    sandbox, vault, savings
backend/runner/     the sandbox entry point
backend/runtime/    what generated connectors import: transports, helpers, errors
connectors/examples generated code for the four example specs (read these)
specs/examples/     hand-written specs: Calendly, Zendesk, Notion, Slack
schemas/            the connector spec schema and the draft schema the AI fills
prompts/            the draft and repair prompts
fixtures/           Acme's HR, SSO and contract files, replay recordings, docs fixtures for tests
frontend/           the React app
benchmark/          the model benchmark and dated prices
tests/              unit, contract, api, security, live
```
