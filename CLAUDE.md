# CLAUDE.md: "AI-Generated Integration Builder" prototype

## What this repo is

A take-home assignment for a Senior PM role.

- **Assignment:** `Using AI to generate the integration code(PM).docx`. **Local only: git-ignored, never committed.** Read only. Never edit, move or rename it.
- **PRD:** `PRD.md` (v4). Product thinking: what and why.
- **TRD:** `TRD.md`. The technical build spec (was PRD Appendix A). **Build from the TRD.**
- **DESIGN:** `DESIGN.md`. Colours, type, components, writing rules, screen layouts. **The UI uses only its tokens.**
- **EVAL:** `EVAL.md`. The AI quality eval (benchmark), acceptance scenarios SC-01 to SC-28, security tests, test plan.
- **README:** `README.md`. The panel's front page: reading order and the one-line idea.
- **GitHub:** https://github.com/Suj1234/api-connector

**Goal:** a working prototype for a 5-minute demo (PRD §15). **One generic engine. No app-specific code outside `specs/`.**
1. App inventory → **Connect usage data**, or **Add an app** for an app not in the list (owner, annual spend, seats, renewal date; **Save app** or **Build with AI**).
2. Library check: if the app is in the library, the admin only pastes a token (built; hidden from the screens for now).
3. Give the app's API docs link **or** its OpenAPI file.
4. AI (Gemini) fills a connector spec, with a docs quote as evidence for every field.
5. Templates generate the connector code covering the 6 assignment items: client, auth, users + usage, error handling, pagination, logging.
6. Sandboxed test run, in `live` (real API) or `replay` (recorded demo data) mode.
7. Savings preview from the sample HRIS / SSO / contract files, and the **app page** listing the users and usage the connector retrieved.
8. Submit to library → internal review → a second tenant connects with its own token (its own test still runs). Built in the engine; hidden from the screens for now (PRD §15).
9. A "surprise app" is pasted live to prove the engine is generic.

**Test apps:**
- Zendesk (T1, OAuth client credentials, because its API tokens are retired)
- Calendly (T2, usage = meetings hosted)
- Notion (T3, usage from SSO fallback)
- One surprise app, not on the platform's public integrations page

**AI model:**
- Google Gemini via `google-genai`, behind `LLMClient`.
- Draft: `gemini-3.8-flash`. Final repair: `gemini-4-argon`.
- The benchmark (`EVAL.md` §2) makes the final choice.

## How to work with Sujeet (important)

- **Before creating or changing files, tell him the plan in simple words and wait for his OK.** For each milestone, list the files you will create or change, then start.
- Keep explanations short and simple. No long theory.
- If anything is unclear, ask. Don't assume.
- **Never assume anything Sujeet didn't say** (for example how he'll use the prototype, who will see it, or how it will be shared). If in doubt, ask one short question first.
- **Sharing:** Sujeet will share a **link** to the running prototype with other people. It must work as a hosted link, behind a login he controls.
- Give one specific answer, not a list of options, unless he asks for options.

## Company name rule (important)

- This repo is shared on GitHub. **Never write the hiring company's name, website domain or product names** in any file, code comment, commit message, branch name or PR text.
- In product docs, say "the platform". In reviews, say "the company".
- The name exists only in the local `.docx`, which stays git-ignored.
- Before every commit, check the staged files for the name. A local pre-commit hook in `.git/hooks/` blocks it. Keep the hook, and don't bypass it with `--no-verify`.

## Secrets

- The Gemini key goes in `prototype/.env` as `GEMINI_API_KEY=...`. That file is git-ignored.
- Provide `prototype/.env.example` with the same keys and empty values.
- Don't set `GOOGLE_API_KEY`. If it is set, the SDK uses it instead of `GEMINI_API_KEY`.
- Use the Gemini API **paid tier**: free-tier prompts may be used to improve Google's products.
- Never print, log or commit API keys or tokens.

## Build order (one milestone at a time; show the result before moving on)

1. **Contracts**
   - Build:
     - `schemas/connector_spec.schema.json` (TRD §3), plus a flattened `schemas/draft_spec.schema.json` for the LLM
     - the canonical record model (TRD §5)
     - the SQLite tables (TRD §10)
     - spec rule checks: read-only, exact host, valid placeholders, variable patterns, no secrets in URLs
   - Done when:
     - the 3 specs in TRD §4 validate;
     - a spec with DELETE is rejected;
     - a spec that calls another host is rejected.
2. **Engine**
   - Build:
     - Jinja2 templates → generated module (TRD §6)
     - 6 paginators
     - `aggregate` and `active_rule`
     - retry/backoff with `Retry-After` and `X-RateLimit-Reset`
     - OAuth client-credentials token fetch
     - redaction
     - `AllowOnlyHost` and replay transports
   - Done when:
     - the Zendesk, Calendly and Notion specs run against replay recordings and produce golden canonical output;
     - `ruff` and `mypy --strict` pass on the generated code.
3. **Sandbox + vault**
   - Build:
     - Docker runner with a per-run egress proxy (TRD §2)
     - subprocess fallback, labelled "demo isolation only"
     - AES-GCM vault with per-tenant keys (HKDF)
   - Done when:
     - a call to a non-allowed host fails with exit code 8;
     - no secret appears in the logs.
4. **Live test**
   - Build:
     - live runs of Zendesk (OAuth), Calendly and Notion against real accounts from `.env`
     - replay recordings, made with the scrubber (fake names and emails)
   - Done when:
     - user counts match each app's admin screen.
5. **AI drafting**
   - Build:
     - docs fetcher with an SSRF guard (OpenAPI first, Playwright fallback)
     - ranker
     - Gemini `LLMClient` with schema-constrained output
     - evidence check and conflict detection
     - hint scrubbing
     - repair loop with JSON Patch (TRD §8)
   - Done when:
     - AI-drafted Zendesk, Calendly and Notion specs pass the same tests as the hand-written ones;
     - the surprise app drafts and tests end to end;
     - the benchmark (`EVAL.md` §2) produces its results table.
6. **UI**
   - Build:
     - screens F1–F9 (PRD §7, layouts in `DESIGN.md` §8) with SSE progress
     - every component copies the dashboard design reference's part of the same name (`DESIGN.md` §6); our own are only the logo, Log out, the footer and the font
     - styling only from the `DESIGN.md` tokens (blurple primary `#635BFF`, navy `#0A2540` only for dark brand surfaces, IBM Plex Sans); no raw hex in components
     - one company on screen (`acme`); the tenant switcher, library submit → approve → connect and the internal view are built but hidden for now
     - savings preview (TRD §11) from `fixtures/acme/`
     - Generated code tab
     - "Sample data" labels in replay mode
   - Done when:
     - the full §15 demo can be clicked through.
7. **Polish for demo**
   - Build:
     - README with run steps
     - screenshots of every screen (`scripts/demo-walkthrough.mjs`, which also checks the whole flow works)
     - SHOULD items, if time allows
   - Done when:
     - scenarios SC-01 to SC-28 (`EVAL.md` §3) pass.

## Build status (29 Oct 2026)

- Milestones 1, 2, 3, 5, 6 and 7 done. No backup video: the assignment doesn't ask for one (decided 31 Oct); the walkthrough script saves a screenshot of every screen instead.
- Hosted at https://integration-builder-five.vercel.app (Vercel, Postgres, login on). 29 Oct: the full flow passed there with real Gemini and real docs (Calendly, sample data): build → test → savings → go live → library → second tenant.
- 31 Oct (local, not yet deployed): UI rebuilt from the dashboard design reference; **Add an app** asks for the inventory details and can **Save app** without building; the **app page** (F9) shows the users and usage the connector retrieved; the tenant switcher and library are hidden; Slack and Zoom are no longer shown as "Connected (native)". SC-18 to SC-23 checked by hand, no automated tests yet.
- 31 Oct, later (local, not yet deployed):
  - **Sample apps:** a fresh database gets Zendesk, Notion and a new Slack sample connected on sample data, built by the engine from `specs/examples/`. Calendly is no longer seeded; the demo adds it with Add an app. Zoom isn't seeded (its token host differs from its API host).
  - **Speed:** a Calendly build now takes about 1.5–2 min instead of about 6 (parallel docs reading, Gemini thinking capped at low, the mypy cache). The progress screens reconnect instead of freezing.
  - **Correctness:** a usage mapping guard (no more silent zeros); the `$parent.` rule in the draft and repair prompts; recoverable seats count only seat holders.
  - **Screens:** the build flow (F3–F6) is one full-screen task built from the reference's FocusHeader, Stepper and Timeline. Connector detail is redone; Banner, Metric, Spinner, Toast and BreakdownBar now copy the reference.
  - **Checks:** SC-24 to SC-27 checked by hand and with live Gemini runs. pytest was not run.
- 1 Nov (local, not yet deployed): fixes from an end-to-end test round (SC-28). An OpenAPI file alone now works; wrong docs stop early (`DOCS_WRONG_APP`, `DOCS_NOT_API`); "Proved" also checks the host, paths and rate number; Calendly's rate limit reads 500 a minute (tables built from `<div>`s were dropped before); token-like text leaves hints; clearer messages for bad links, a past renewal date and a missing token.
- 1 Nov, final round (local, not yet deployed): every finding fixed and the fixed checklist (`EVAL.md` §7) passed through the screens with live Gemini, including the walkthrough script on the final code. Asana, Miro, Typeform and Loom are now in the sample inventory, not connected.
- Milestone 4 (live vendor APIs) and the real benchmark wait on test accounts (vendor tokens).
- Scenario status: `EVAL.md` §6. Run steps: `prototype/README.md`. Build decisions: `TRD.md` §15.

## Rules that must not be broken

- The LLM only sees public docs, masked samples and scrubbed admin hints. **Never** send tokens, real names, emails or counts to the LLM.
- Generated connectors make **read calls only**, to the spec's own host only.
- No free-form AI code runs in the sandbox. AI fills the spec; templates write the code.
- No app-specific code outside `specs/`.
- Nothing reaches another tenant's library without internal review. Each tenant's own test always runs.
- Never commit real customer or personal data. Replay recordings use fake people.
- Don't build anything marked LATER in TRD §1.

## Check at build time (full list: TRD §14)

- **Calendly:**
  - the `max_start_time` parameter on `/scheduled_events`;
  - the scope names and the token setup path;
  - `event_memberships[].user` and `pagination.next_page_token`.
- **Zendesk:**
  - the OAuth client path in Admin Center;
  - the `/oauth/tokens` body format (JSON vs form);
  - whether `scope: read` works with client credentials;
  - the `role[]` filter and cursor params.
- **Notion:**
  - `Notion-Version: 2026-03-11`;
  - the connections page path;
  - the capability name.
- **Gemini:**
  - the model IDs and prices;
  - the exact `google-genai` call for schema-constrained output.
