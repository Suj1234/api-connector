# CLAUDE.md: AI-Generated Integration Builder

Guide for AI coding assistants working in this repo.

## What this repo is

A prototype that turns any SaaS app's public API docs into a tested, read-only connector for users and usage data. The AI fills a connector spec with a docs quote for every answer; fixed templates write the code; a sandbox tests it; the users are cross-checked with HR, SSO and contract data before going live.

- **Live:** https://integration-builder-five.vercel.app (login by invite)
- **Code:** https://github.com/Suj1234/api-connector, branch `main` (a push deploys to Vercel)
- **Docs:** `PRD.md` (what and why, roadmap), `TRD.md` (how it is built; **build from the TRD**), `DESIGN.md` (the UI uses only its tokens), `EVAL.md` (test approach, acceptance scenarios, results). `README.md` is the front page.

## Rules that must not be broken

- **One generic engine.** No app-specific code outside `specs/`.
- **The AI only sees public docs, masked samples and scrubbed admin hints.** Never send tokens, real names, emails or counts to it.
- **No AI-written code runs.** The AI fills the spec; the templates write the code; every generated module passes `ruff` and `mypy --strict`.
- **Generated connectors make read calls only, to the spec's own host only.**
- **Never commit real customer or personal data.** Recordings use fake people.
- **The UI uses only `DESIGN.md`'s tokens and components.** No raw hex values in components.
- Features not on the screens today are on the roadmap (`PRD.md` §13); don't add them unless asked.

## Secrets

- The Gemini key goes in `prototype/.env` as `GEMINI_API_KEY=...` (git-ignored). `prototype/.env.example` lists every setting with empty values.
- Don't set `GOOGLE_API_KEY`: the SDK would use it instead of `GEMINI_API_KEY`.
- Use the Gemini API's paid tier: free-tier prompts may be used to improve Google's products.
- Never print, log or commit API keys, tokens or the login.

## Commands (from `prototype/`)

```bash
# run locally (http://localhost:8000)
cd backend && PYTHONPATH=.:.. ../.venv/bin/python -m uvicorn app.api:app --port 8000

# checks and tests
.venv/bin/ruff check . && .venv/bin/mypy && (cd frontend && npx tsc --noEmit -p .)
.venv/bin/python -m pytest

# frontend build, model benchmark, example connectors
(cd frontend && npm run build)
.venv/bin/python -m benchmark
PYTHONPATH=backend .venv/bin/python -m app.services.codegen
```

- **Deploy:** push to `main`; Vercel builds and deploys in about a minute (`TRD.md` §2.1).
- **Fresh local data:** stop the server and delete `data/app.db`. **Fresh hosted data:** the SQL in `TRD.md` §2.1, then open the site.

## Where things are

The folder map is in `TRD.md` §13. Scenario status and test results: `EVAL.md` §3–§6.
