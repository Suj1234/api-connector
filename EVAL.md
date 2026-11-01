# AI-Generated Integration Builder — EVAL

**For:** Senior PM take-home assignment
**Author:** Sujeet Kumar
**Date:** 1 Nov 2026
**Status:** v2. How we know the builder works: the test approach, the AI benchmark, the acceptance scenarios and the results. Read with `PRD.md` (why) and `TRD.md` (how it is built).

---

## 1. Scope and approach

### 1.1 What is evaluated

The AI is one step in a longer chain: docs → spec → checks → code → sandbox → user records → savings. A spec can look right and still return the wrong users, so each layer is tested on its own.

| Layer | Question | Where |
|---|---|---|
| **AI quality** | Does the model draft a correct spec from docs, with real evidence, in few repairs, at low cost? | §2 |
| **Product behaviour** | Does the whole flow give the right users, the right usage label, safe calls and plain errors? | §3, §4 |
| **Security** | Can a bad doc, a bad draft or a bad link make the connector write, leak or call somewhere else? | §5 |
| **Deployment** | Does the same flow work on the hosted link (Vercel + Neon Postgres) with live Gemini? | §4 |

**The rule that ties them together:** a draft counts as a pass only if the connector it produces returns the right users. Valid JSON alone is not a pass.

**Out of scope for the prototype:** real vendor accounts (no vendor tokens were available, so connectors are tested on recorded answers and live calls only with a made-up token), load and scale, and the roadmap items (PRD §13).

### 1.2 Test levels

| Level | What it covers | How | When |
|---|---|---|---|
| **Unit** | Spec rules, placeholders, field maps, `aggregate`, `active_rule`, the 6 paginators, retries and backoff, redaction, the SSRF guard, hint scrubbing, savings math, the vault | `pytest`, mock servers | Every change |
| **Contract** | The four example specs on their recordings return exactly the expected users | `pytest` | Every change |
| **API flow** | The main flow through the real API: add an app, build, test, savings, go live, delete; the library path between two companies | `pytest` (recorded AI answers) | Every change |
| **Security** | Prompt injection, write calls, calls to another host, SSRF, secrets in the database, logs and API | `pytest` | Every change |
| **Generated code** | `ruff` and `mypy --strict` on every generated module | Built into codegen | Every build |
| **AI benchmark** | 3 apps × 3 models × 3 runs | `python -m benchmark` | Before choosing a model |
| **Manual end-to-end** | The fixed checklist in §4, through the screens, with live Gemini, on a fresh database | By hand, in a browser | Before every release |
| **Hosted check** | The same checklist on the hosted link | By hand | After every deploy |

### 1.3 Environments and test data

- **Local:** SQLite, live Gemini, the subprocess sandbox, a fresh database for each round.
- **Hosted:** https://integration-builder-five.vercel.app (Vercel, Neon Postgres, live Gemini, the shared login), checked on a fresh database.
- **Data:** the sample company Acme, with fake people: HR, SSO and contract files, and recorded API answers for Calendly, Zendesk, Notion and Slack. No real customer data.

### 1.4 When testing is done

1. `ruff`, `mypy --strict`, `tsc` and `pytest` pass.
2. Every acceptance scenario (§3) passes, or names what blocks it.
3. The manual checklist (§4) passes locally, then on the hosted link after the deploy.
4. Every defect found is fixed, re-tested, and the checklist run again.

---

## 2. AI quality eval (model benchmark)

### 2.1 Test set

| App | Shape | Golden answer |
|---|---|---|
| Zendesk | T1, OAuth client credentials, last login on the user | `specs/examples/zendesk.json` |
| Calendly | T2, usage counted from scheduled events | `specs/examples/calendly.json` |
| Notion | T3, users only, SSO fallback | `specs/examples/notion.json` |

Each app has known traps (`PRD.md` §5.5), checked directly:
- **Calendly:** `max_start_time` is set, so future meetings aren't counted; a third-party rate limit shows up as a conflict, not as the answer.
- **Zendesk:** end users are filtered out; the connector's own account is excluded from "inactive"; OAuth, not the retired API tokens.
- **Notion:** usage is `null` with the SSO fallback, not an invented field; the email capability is a warning.

### 2.2 How it runs

```bash
python -m benchmark --apps zendesk calendly notion --models gemini-3.5-flash-lite gemini-3.8-flash gemini-4-argon --runs 3
```

- 3 apps × 3 models × 3 runs = **27 drafts**, from the same cached docs.
- Each draft is tested on the app's **recording**, so results repeat and rate limits don't matter. A drafted path that isn't in the recording returns 404, as the real API would, and triggers repair (up to 3 tries).
- Prices come from `benchmark/prices.json`, with the date they were checked.

### 2.3 Metrics and targets

| Metric | Definition | Target for the chosen model |
|---|---|---|
| **Schema valid** | The draft validates and passes the rules (`TRD.md` §3) | 100% after the evidence re-ask |
| **Evidence verified** | % of filled fields whose quote or OpenAPI pointer passes the check | ≥ 90% on the first draft |
| **Test pass** | The sandbox test exits 0 (including `partial` where the golden spec is also partial) | ≥ 8 of 9 |
| **User count match** | Passing runs return the same `external_id` set as the golden spec on the same recording | 100% of passing runs |
| **Usage match** | Same usage tier, metric label and `active_rule` as the golden spec | ≥ 8 of 9 |
| **Repairs** | Average repair tries per draft | ≤ 1 |
| **Cost** | Average $ per connector, tokens × dated prices | < $1 |
| **Time** | Average seconds from docs to a passing test | Tracked |

### 2.4 How the model is chosen

1. Highest **test pass** wins.
2. A tie goes to **fewer repairs**.
3. A tie after that goes to **lower cost**.

Price comes last on purpose: a draft costs cents, an engineer's review costs an hour (`PRD.md` §9).

### 2.5 Results (1 Nov 2026)

Run on 1 Nov 2026 with live Gemini (paid tier): 27 drafts from the same cached docs, each tested on its recording. Full table: `prototype/benchmark/results.md`.

| Model | Schema valid | Evidence verified | Test pass | User count match | Usage match | Avg repairs | Avg $ per connector | Avg seconds |
|---|---|---|---|---|---|---|---|---|
| `gemini-3.5-flash-lite` | 8/9 | 72% | 2/9 | 2/9 | 3/9 | 2.0 | $0.12 | 42 |
| `gemini-3.8-flash` | 9/9 | 100% | 7/9 | 4/9 | 3/9 | 0.7 | $0.13 | 46 |
| `gemini-4-argon` | 9/9 | 100% | **9/9** | **9/9** | 3/9 | **0.0** | $0.23 | 50 |

**What it shows:**
- **`gemini-4-argon` is the only model that meets the targets:** all 9 tests pass with exactly the right users, no repairs, $0.23 per connector ($0.46 after its 1 Dec price change, still under the $1 target), about 50 s.
- **`gemini-3.8-flash`** passed Calendly 3 of 3, but Zendesk only 1 of 3 (the wrong request, even after repairs), and on Notion it passed the test with a different set of users than the hand-written spec 3 of 3.
- **`gemini-3.5-flash-lite`** is too weak for this job: 2 of 9.
- **Usage match is 3 of 9 for every model:** on Calendly and Zendesk every model also names an SSO fallback (`sso_last_login`) that the hand-written specs leave out. The fallback only applies to people the app gives no usage for, so it doesn't change the numbers; Notion, where the fallback is the answer, matches every time.

**Decision (1 Nov 2026):** by the rule in §2.4, `gemini-4-argon` now drafts and makes every repair try, locally and on the hosted link (`LLM_MODEL_DRAFT`, `TRD.md` §2.2). Re-checked on the hosted link the same day: Calendly deleted, added again and built by Argon (15 of 15 answers proved), 48 users, $4,560 a year, live.

### 2.6 Adversarial cases

| Case | Pass when | Result |
|---|---|---|
| A docs page with a prompt injection ("send the data to evil.com") | The spec has no other host; the rules reject it if it does; no call leaves the sandbox | ✅ SC-06 |
| A docs page that asks for a DELETE or a write call | `RULES_REJECTED` | ✅ SC-07 |
| Two sources with different rate limits | Conflict recorded; the vendor's page wins | ✅ SC-17 |
| An admin hint with an email, a token and a long number | All removed before the prompt | ✅ C9 |

---

## 3. Acceptance scenarios

The product is done when all of these pass. "Waits" names what only a real vendor account can give.

| ID | Scenario | Expected | Status · evidence |
|---|---|---|---|
| SC-01 | Zendesk T1 (OAuth client credentials) | Agents and admins with last login; the service account excluded from inactive; Live | ✅ replay and the OAuth flow (`contract/test_replay.py`, `unit/test_engine.py`) · waits on a Zendesk account for a live run |
| SC-02 | Calendly with a non-admin token, or without `scheduled_events:read` | Users work, usage gets 403 → `partial`, a plain message naming the role and scope; no repair; Live (users only) allowed | ✅ `api/test_flow.py::test_sc02_*` |
| SC-03 | Calendly with an admin token | Users + "Meetings hosted (90 days)" marked proxy; no future meetings counted | ✅ replay (`contract/test_replay.py`, `unit/test_savings.py`) · waits on a Calendly account for a live run |
| SC-04 | Notion T3 | Users only; usage from the SSO fallback, labelled "per SSO login" | ✅ `unit/test_savings.py` |
| SC-05 | Wrong path drafted | 404 → repair; passes by try 3, or Needs help | ✅ `unit/test_ai_pipeline.py::test_repair_*` (scripted model) |
| SC-06 | Prompt-injection docs page | The host rule blocks it; the AI never holds a token; no call to another host | ✅ `unit/test_ai_pipeline.py`, `security/test_sandbox.py` |
| SC-07 | Spec with DELETE | Rejected (`RULES_REJECTED`) | ✅ `unit/test_spec_validator.py` |
| SC-08 | Library reuse between two companies (in the API, not on screen) | Globex can't see Acme's connector until the platform approves it; then connects with its own token, and its own test runs | ✅ `api/test_flow.py::test_full_demo_flow` |
| SC-09 | Count mismatch | > 2% vs SSO → warning; going live needs a note | ✅ `api/test_flow.py::test_count_mismatch_needs_a_note` |
| SC-10 | Rate limited | 429 handled with `X-RateLimit-Reset` or `Retry-After` | ✅ `unit/test_engine.py::test_429_*` |
| SC-11 | Surprise app | Drafted from its docs, no example spec, no app-specific code | ✅ live Gemini on the hosted link: Asana 9 of 9 answers proved, Miro 11 of 11 · their tests wait on real tokens |
| SC-12 | SSRF | Links to `169.254.169.254`, `localhost`, `10.x` or a redirect to them → `SSRF_BLOCKED` | ✅ `unit/test_ai_pipeline.py::test_ssrf_*`, hosted C5 |
| SC-13 | Token owner leaving | HR marks the token owner as leaving → warning "switch to a service account" | ✅ `api/test_flow.py::test_sc13_*` |
| SC-14 | Sample data | "Sample data" wherever sample numbers show; no calls to the vendor | ✅ by hand; replay tests in `security/test_sandbox.py` |
| SC-15 | Secrets | No token, email or real name in the database, logs, API or AI prompts | ✅ `api/test_flow.py::test_sc15_*`, `contract/test_replay.py` |
| SC-16 | Benchmark | The 3 × 3 × 3 results table | ✅ run on 1 Nov (§2.5) |
| SC-17 | Docs conflict | Two rate-limit values → both shown, the vendor's page wins | ✅ `unit/test_ai_pipeline.py::test_docs_conflict_*` |
| SC-18 | Add an app | Name, owner, spend, seats (≥ 1), renewal date and one docs source required; Build stays off until valid; the app joins the inventory and its cards | ✅ by hand, local and hosted |
| SC-19 | Save app, and duplicates | Save app adds the app without a connector; the same name in any letter case is refused | ✅ by hand, local and hosted (C2) |
| SC-20 | Leave without saving | Closing a drawer with input asks "Leave without saving?" | ✅ by hand |
| SC-21 | Docs link or file | One of the two; a bad link shows "Enter a full link…" and Build stays off | ✅ by hand, local and hosted (C4) |
| SC-22 | App page users | Every user the generated code retrieved; the count equals the test's; search, filter and 25 per page work | ✅ by hand, local and hosted |
| SC-23 | App page before data | Contract details, "—" in the cards, "No usage data yet" with the next step; no made-up numbers | ✅ by hand |
| SC-24 | Sample apps on a fresh database | Zendesk (37), Notion (87, users only) and Slack (146) connected by the normal codegen and test; the other five apps not connected; no Calendly | ✅ `contract/test_replay.py`; fresh databases local and hosted (8 s on Vercel) |
| SC-25 | Build speed and progress | A Calendly build with live Gemini in about 2 minutes or less; each step explained; a dropped stream reconnects | ✅ 1–2 min on the hosted link (about 1 min 40 s with Argon), 1–2 min local |
| SC-26 | Usage mapping guard | Usage that names no user, has no time or matches nobody fails with `MAPPING_FAILED`, never everyone at 0 | ✅ by hand |
| SC-27 | Build flow screens | F3–F6 as one task: header, step list, Proved badges open their quotes, the six items on the test, Go live lands on the app page | ✅ by hand, local and hosted |
| SC-28 | Wrong or thin docs | OpenAPI file alone works; wrong app → `DOCS_WRONG_APP`; marketing site → `DOCS_NOT_API`; bad link refused at once; rate limit is the general limit | ✅ by hand, local and hosted (B1, B4, C4–C7) |
| SC-29 | Each person's status on the app page | Each user's Status is their savings result (Left the company, Inactive, Active, Not in HR data) with the reason; it matches the cards and the savings step; the app's own account status shows only when its API gives one; the Status filter uses the results | ✅ by hand, local (Calendly, Slack) and hosted |
| SC-30 | Delete app | An added app has **Delete app**: after a confirm, the app, its connector, runs, users and token are gone, and it can be added again. A starting app with a connector has **Remove connector** (the row stays). The sample apps have neither. Refused while a build or test runs | ✅ `api/test_flow.py::test_delete_app_then_add_it_again`; by hand, local and hosted |

---

## 4. Manual end-to-end checklist

One fixed list, run the same way each round: a fresh database, through the screens, with live Gemini. Locally on 1 Nov, then on the hosted link after the deploy.

| # | Check | Expected | Local | Hosted |
|---|---|---|---|---|
| **A** | **The main flow** | | | |
| A1 | Fresh database, App inventory | Zendesk and Slack Connected, Notion Users only (Sample data); Zoom, Asana, Miro, Typeform, Loom not connected; no Calendly | ✅ | ✅ 8 s after the first-visit fix (below) |
| A2 | Slack's app page | Users with a Sample data tag; the cards match its savings | ✅ Inactive 12, Left 6, 0 seats nobody holds | ✅ same |
| A3 | Add an app: Calendly, its details, docs link, Build with AI | Done in about 2 minutes; every step says what it does | ✅ 2 min 30 s (another build ran at once) | ✅ about 1 min 40 s with Argon (one evidence re-ask); about 50 s with Flash before the switch |
| A4 | Review what we found | Every answer proved; 500 a minute; users from `/organization_memberships`; usage per host, 90 days; paging in words; the evidence panel opens on the answer clicked | ✅ 19 of 19 | ✅ 15 of 15 with Argon (18 of 18 with Flash) |
| A5 | Connect and test | No token on sample data; 48 users, 33 with activity; six items Done; six markers in the code; read-only requests | ✅ | ✅ 5 GET requests, all 200 |
| A6 | Check the savings | Uses the typed seats, spend and renewal ("from your inventory"); 6 left, 11 inactive; days from today | ✅ | ✅ 50 seats, $12,000: 2 seats nobody holds, $4,560 a year, in 75 days |
| A7 | Go live, app page, inventory | Live, 48 users; cards equal the savings; row Connected | ✅ | ✅ |
| A8 | Connector detail | Version, evidence %, generated code, data card download | ✅ | ✅ v1, 100% proved |
| A9 | Each person's status | Every user shows Left the company, Inactive or Active with the reason; Slack keeps its Deactivated accounts in "Account in Slack" | ✅ Calendly, Slack | ✅ Calendly (no "Unknown" left), Slack |
| A10 | Delete app | An added app: Delete app → confirm → back to the inventory with "… was deleted", gone from the list, free to add again. A tested connector goes with its runs and users | ✅ Calendly | ✅ Calendly deleted and added again end to end, twice (the second time with Argon); a tested connector removed on Postgres; the sample apps show no button |
| **B** | **Other ways to add an app** | | | |
| B1 | Calendly from its OpenAPI file only | Every answer proved; 500 a minute; 48 users; step 1 talks about the file | ✅ 16 of 16 | ✅ 16 of 16 (the first run had 13 of 16: see the citation fix below) |
| B2 | Miro from its row | Built from its docs; asks for the Organization ID and the token | ✅ | ✅ |
| B3 | Surprise app (Asana) | Every answer proved; Run test off until the fields are filled; a made-up token → "The token was rejected"; the token stored nowhere in plain text | ✅ | ✅ 9 of 9, Run test off · the token step is local only |
| B4 | An app whose API can't list users (Typeform) | "Typeform's API doesn't list your company's users…"; only Use another docs link | ✅ | ✅ after the page-limit fix (below) |
| **C** | **Adding an app going wrong** | | | |
| C1 | Details missing | Build with AI stays off | ✅ | ✅ |
| C2 | The same name again, any case or spaces | "… is already in your inventory" | ✅ | ✅ |
| C3 | A past renewal date | Greyed in the picker; the server refuses it too | ✅ | ✅ |
| C4 | Bad links (not a link, ftp, localhost, a space) | An inline error or the server's message | ✅ | ✅ |
| C5 | A private address (10.0.0.1) | Stops at once; only Use another docs link | ✅ | ✅ under 1 s |
| C6 | example.com, or another app's docs | "These docs never mention …" | ✅ | ✅ |
| C7 | A marketing site (loom.com) | "These pages don't look like an API reference…", before any AI call | ✅ | ✅ 6 s |
| C8 | The inventory after stopped builds | "Needs help" or "Setup not finished", with Continue setup | ✅ | ✅ |
| C9 | A hint with a token in it | The token removed before the AI sees it | ✅ | Not visible on screen |
| C10 | Two clicks on Run test | One run | ✅ | ✅ |
| **D** | **Engineering checks** | | | |
| D1 | `ruff`, `mypy --strict`, `tsc` | No errors | ✅ | — |
| D2 | The four example specs on their recordings | Each matches its expected users exactly | ✅ 48, 37, 87, 146 | — |
| D3 | Generated code for each example | Passes `ruff` and `mypy --strict`; all six markers | ✅ | — |
| D4 | Secrets | No typed token in the database or the logs | ✅ | No token typed on the hosted link |

---

## 5. Security tests

| Threat | Test | Result |
|---|---|---|
| Docs tell the AI to send data elsewhere | SC-06: injection page → the host rule rejects the draft; no call leaves | ✅ |
| A draft asks for a write or delete call | SC-07 → `RULES_REJECTED` | ✅ |
| Generated code calls another host | The sandbox stops it with exit 8 and logs a security event (`security/test_sandbox.py`) | ✅ |
| A docs link points inside the network | SC-12: private, loopback, link-local, metadata addresses and redirects to them → `SSRF_BLOCKED` | ✅ |
| Tokens leak | SC-15: none in the database (encrypted), logs (redacted), API (write-only) or AI prompts | ✅ |
| Personal data reaches the AI | Hint scrubbing removes emails, long numbers and token-like text (C9) | ✅ |
| Anyone opens the hosted link | Every API call needs the login (401 without it) | ✅ checked on the hosted link |

---

## 6. Results

**Automated (1 Nov 2026):** `ruff`, `mypy --strict` and `tsc` clean. `pytest`: 203 passed, 3 skipped (the live tests need real vendor accounts).

**Defects found and fixed on 1 Nov** (each re-tested after the fix):
- **The app page showed "Unknown" for every Calendly user.** Calendly's API has no account status. Each person's Status is now their savings result with the reason (SC-29).
- **An added app couldn't be removed**, so the next person couldn't add it again. Delete app added (SC-30).
- **Hosted: the sample apps never finished building** on a fresh database, because Vercel pauses a function between requests. On Vercel they are now built inside the first visit.
- **Hosted: OpenAPI endpoint citations one field too deep** (`/paths/~1users/get/path`) showed 3 of 16 answers as unproved. Such a citation now proves its endpoint.
- **Hosted: the docs page limit was 30** while the screen said 60, so Typeform stopped with a vaguer message. Now 60.
- **A test run's date showed the day before** for runs in Indian morning hours: SQLite drops the time zone.
- **A marketing site could produce a users endpoint** such as `/pricing`. Docs with no API calls now stop before the AI drafts.
- **A rules stop showed a raw data dump.** It now names the rule.
- **Zendesk's users reference page (6.6 MB)** was over the 3 MB page limit. Now 10 MB.
- **The duplicate-name message** pointed at a button a connected app doesn't have.
- **Without a Gemini key, the hand-written stand-in** tripped the "too few proved" stop and lost its unproved fields. The stand-in is now exempt.
- **A docs conflict cost an extra AI call:** it is now settled before the value check.

## 7. Known limits

- **No real vendor accounts.** Every test ran on recorded answers; live calls were made only with a made-up token, which was rejected as expected. Matching user counts against each app's admin screen waits on real accounts.
- **The AI's choices vary between runs.** Miro's users came once from its members endpoint, once from SCIM; one Miro draft read no email field; one Zendesk draft missed the last-login field and used SSO data. The test with a real token decides.
- **The sandbox is a separate process**, labelled "demo isolation only"; a locked container per run is on the roadmap (PRD §13).
- **Docs that need JavaScript to show text can't be read**; the OpenAPI file is the way in.
- **One shared login and one company on screen.**

## 8. After the prototype

- **Backtest before production:** 30 apps (10 per tier) against the platform's native connectors, plus one non-Gemini model for comparison (`PRD.md` §9), shown as a scoreboard ("user counts matched on 26/30 apps").
- **In production**, the eval becomes the metrics in `PRD.md` §11. The counter-metric that matters most is the **false-inactive rate**: people flagged inactive who actually use the app.
- **Every correction becomes a test case.** A repair, an admin hint or a reviewer rejection adds the app and the fix to the eval set, so the next model or prompt change is checked against it.
