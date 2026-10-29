# CLAUDE.md: "AI-Generated Integration Builder" prototype

## What this repo is

A take-home assignment for a Senior PM role.

- **Assignment:** `Using AI to generate the integration code(PM).docx`. **Local only: git-ignored, never committed.** Read only. Never edit, move or rename it.
- **PRD:** `PRD.md` (v4). Product thinking: what and why.
- **TRD:** `TRD.md`. The technical build spec (was PRD Appendix A). **Build from the TRD.**
- **DESIGN:** `DESIGN.md`. Colours, type, components, writing rules, screen layouts. **The UI uses only its tokens.**
- **EVAL:** `EVAL.md`. The AI quality eval (benchmark), acceptance scenarios SC-01 to SC-17, security tests, test plan.
- **README:** `README.md`. The panel's front page: reading order and the one-line idea.
- **GitHub:** https://github.com/Suj1234/api-connector

**Goal:** a working prototype for a 5-minute demo (PRD §15). **One generic engine. No app-specific code outside `specs/`.**
1. App inventory → **Connect usage data**.
2. Library check: if the app is in the library, the admin only pastes a token.
3. Paste the app's API docs.
4. AI (Gemini) fills a connector spec, with a docs quote as evidence for every field.
5. Templates generate the connector code covering the 6 assignment items: client, auth, users + usage, error handling, pagination, logging.
6. Sandboxed test run, in `live` (real API) or `replay` (recorded demo data) mode.
7. Savings preview from the sample HRIS / SSO / contract files.
8. Submit to library → internal review → a second tenant connects with its own token (its own test still runs).
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
     - screens F1–F8 (PRD §7, layouts in `DESIGN.md` §8) with SSE progress
     - styling only from the `DESIGN.md` tokens (navy primary `#0A2540`, IBM Plex Sans); no raw hex in components
     - tenant switcher (`acme`, `globex`, `internal`)
     - library submit → approve → connect
     - savings preview (TRD §11) from `fixtures/acme/`
     - Generated code tab
     - "Demo data" labels in replay mode
   - Done when:
     - the full §15 demo can be clicked through.
7. **Polish for demo**
   - Build:
     - README with run steps
     - backup video
     - SHOULD items, if time allows
   - Done when:
     - scenarios SC-01 to SC-17 (`EVAL.md` §3) pass.

## Build status (29 Oct 2026)

- Milestones 1, 2, 3, 5, 6 done; 7 done except the final video, which is recorded on Sujeet's Mac with Gemini on.
- Milestone 4 (live) and the real benchmark wait on: Gemini key, test accounts, and network access to the vendor hosts.
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
