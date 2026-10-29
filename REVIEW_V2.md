# Review v2: AI-Generated Integration Builder

29 Oct 2026. Four independent agents reviewed `PRD.md` (v2) and `CLAUDE.md` against the raw assignment (`.docx`). None of them read `REVIEW_NOTES.md`, so the old reviews could not bias them. None changed any file.

| Agent | Angle |
|---|---|
| **A. Coverage** | Every ask in the assignment, line by line |
| **B. Interviewer** | Reads it as the company's hiring manager |
| **C. Fact-check** | 42 claims checked against live vendor docs |
| **D. CPO** | What a typical ChatGPT/Claude answer looks like, and how to beat it |

---

## 1. Bottom line

- **Does it match the requirement? Partly.** The PRD answers all 3 deliverables in writing, and the thinking is strong. But **2 of the 3 deliverables don't exist yet**: there is no Figma and no prototype. The PRD also never shows a single line of generated code, and generated code is the core ask.
- **Hire signal (Agent B): "Yes, conditional".** It drops to "Lean no" if you arrive at the panel with no frames and no running demo.
- **Three new facts change the plan.** None of them were in the old review:
  1. **Zendesk API tokens are being removed.** Since 27 Oct 2026 no account can create a new one, and accounts created on or after 28 Jul 2026 can't use them at all. Your Zendesk spec (basic auth + API token) and your "Zendesk trial" test-account plan will not work.
  2. **The company already lists native Calendly, Zendesk and Notion integrations.** Your demo opens with "Calendly: No usage data", and the panel knows that isn't true for their own product.
  3. **A shared connector library is not new.**
     - Josys and BetterCloud already review customer-built integrations and promote them to a catalog for all customers. Airbyte runs a marketplace too.
     - Lumos and Josys also have AI integration builders, alongside Torii.
     - So the PRD's claim that only the company can do a shared library is wrong.

---

## 2. Point 1: Does it match the requirement?

### By deliverable

| Assignment ask | Answered in PRD? | Actually exists? | Verdict |
|---|---|---|---|
| Use AI to generate integration code from API docs | **Partly.** The AI writes a JSON spec and templates write the code (§6). §0 never says this | No code anywhere | The choice is defensible but buried. Say it in §0 and show the code |
| The 6 code items: client, auth, users + usage, error handling, pagination, logging | Yes, described (§6, A3–A7) | **No.** Zero lines of generated code | Add one real generated Calendly module, or an excerpt that covers all 6 |
| The 4 differences: APIs, auth, rate limits, data structures | Yes (§1 table) | n/a | Fine. 3-legged OAuth is pushed to later. Notion and Zendesk rate limits are set to `null` even though both vendors publish them |
| **D1 Figma** | Partly. A 7-row text table (§7) | **No** Figma, link, image or mockup | **Missing** |
| **D2 Safeguards** | Yes. The strongest section (§8) | n/a | Good. Gaps: token risk, SSRF, PII retention, and some contradictions (see §5) |
| D2 "asking customers to be developers" | Yes. "Don't turn customers into developers" (§3) | n/a | A good reframe, and the interviewer agent liked it |
| D2 Sandbox first, then prod? | Yes. "Test mode first, then Live"; the sandbox reads real data, read-only (§8) | n/a | A clear answer, but the best line is buried inside a table cell |
| **D3 Prototype** | Partly. It's a build spec, not a prototype | **No code** | **Missing.** §0 says "The prototype runs ... end to end", which is false today |
| D3 AI model | Yes. Sonnet 5.5, escalating to Opus 5.5 (§9) | n/a | Named, but the reasons are generic and the cost isn't priced |

### Scorecard (Agent B, out of 5)

| Area | Score | Why |
|---|---|---|
| Answers the 3 deliverables directly | 2 | No Figma, no prototype; §0 claims a prototype runs |
| Product judgment | 4 | "Real risk = wrong seat cuts", renewal entry point, savings ending, "AI decides, templates write" |
| Understanding of the company's business | 4 | Spend coverage, renewals, cross-checks, access reviews. Misses usage the company already gets from SSO |
| Safeguards depth | 4 | Strongest section. No production metric for wrong cuts; missing PII, liability and vendor API terms |
| Prototype readiness | 1 | Nothing runs. Appendix A is far too big for a take-home |
| Clarity / length | 2 | §0 is good. The whole PRD is about 7,000 words, about 55% of it an engineering appendix, and it contradicts itself |
| Originality vs other AI-assisted candidates | 4 | The Torii finding, the wrong-cuts reframe, the cross-check, backtesting against native connectors, real API traps |

---

## 3. Fix list (all agents merged, ranked)

| # | Fix | Found by | Effort |
|---|---|---|---|
| 1 | **Build a thin working demo: Calendly only.** Real token → docs → spec with evidence → generated-code view → users + "meetings hosted" → savings screen → second tenant connects from the library. Record a 3-minute backup video. Make Zendesk (recorded data), Notion (static card), the Docker egress proxy, JSON Patch repair and the fleet view stretch goals. Until the demo exists, change §0 so it doesn't claim a prototype already runs | A, B, D | L |
| 2 | **Make the Figma real.** Draw at least frames F1–F5 and link them from §0 and §7. Replace "$X" with a real computed number | A, B, D | M |
| 3 | **Show the generated code.** Add one Calendly module excerpt that visibly covers all 6 assignment items. In §0, say plainly that the AI writes a checked spec, templates write the code, and why | A, B | S |
| 4 | **Fix Zendesk auth.** Switch to `oauth_client_credentials`: `token_url: https://{subdomain}.zendesk.com/oauth/tokens`, `grant_type: client_credentials`, scope `read`. The OAuth client should be owned by a dedicated service account. There is no refresh token, so the runner gets a new token each run. Re-check the test account plan | C | S (PRD) / M (prototype) |
| 5 | **Fix the demo premise.** The company already has Calendly, Zendesk and Notion connectors. Two options: (a) present these 3 as **backtest apps**, where the AI-built connector must match the company's own native one; (b) make F1 show an app the company doesn't list | C, D | S |
| 6 | **Rewrite the moat.** Drop "only the company can" and "a per-customer builder can't". Say instead: "Shared libraries exist (BetterCloud, Josys). Our edge is a library built on APIs that carries real usage, is cross-checked with HRIS/SSO/contract data, and is triggered by renewals." Add Lumos, Josys and Fivetran to §2. Rename "factory", or acknowledge it, because Lumos already uses "Integration Factory" | B, C, D | S |
| 7 | **De-risk the library.** The company rebuilds library specs itself from public docs (clean room). Customer contributions are opt-in only. Show "used by N" only when N ≥ 5. Roll repairs out to a few tenants first (canary) with auto-rollback, never fleet-wide in one go. Name the leak risk: repair inputs can carry tenant-specific custom field names into a shared spec | B, D | S |
| 8 | **Remove overclaims and internal traces.** Delete the status line "Fixes everything from two independent reviews (see `REVIEW_NOTES.md`)". Don't ship `REVIEW_NOTES.md`. Remove the "How to work with Sujeet" section from anything the panel sees | A, B | S |
| 9 | **Calendly spec fixes.** Add `"max_start_time": "{now}"`; today future meetings count as "hosted". Add the required scopes (`users:read`, `organizations:read`, `scheduled_events:read`). Update the setup path to Profile menu > Developer > Personal access tokens. Make the 403 message say "missing scope **or** Owner/Admin role" | A, C, D | S |
| 10 | **Cut the PRD to about 2,000 words.** Move Appendix A and CLAUDE.md into the prototype repo's README. Cut the 7-beat demo to what fits in 5 minutes | B | M |
| 11 | **Fix the numbers.** State a real $ cost per connector. Count customer value net of usage the company already gets from SSO. Add a counter-metric for false "inactive" flags (wrong cuts). Use one consistent time promise (today the "3 min" button conflicts with the "≤10 min" target). Give a baseline for "+15 points" | A, B | S |
| 12 | **Add a token-owner flow.** Long-tail apps are often owned outside IT; for example, marketing holds the Calendly Owner token. Add an "ask the app owner to connect" path | B, D | S |
| 13 | **Close the safeguard gaps.** SSRF protection on the docs fetcher (it fetches URLs customers supply). Retention rules for pulled user PII. Scrub the free-text admin hint before it reaches the LLM; today the claim "the LLM never sees customer data" isn't quite true | A, D | S |

---

## 4. Fact-check: what's wrong or risky (Agent C)

**42 claims checked: 32 confirmed, 3 wrong, 6 partly right, 1 can't verify.**

**Wrong**

| Claim | Where | What's true | Fix |
|---|---|---|---|
| Zendesk basic auth `{email}/token:{api_token}` | A4, A12 | API tokens announced for removal on 1 Jun 2026. Since 27 Oct 2026 no account can create new ones, and all stop working on 30 Apr 2027 ([Zendesk](https://support.zendesk.com/hc/en-us/articles/10851263566234), [OAuth migration](https://developer.zendesk.com/documentation/authentication/oauth-migration/)) | Fix #4 above |
| Shared library is something only the company can do | §0, §3, §10, §14 | Josys: "Josys may review and promote it to the App Catalog" ([Josys](https://www.josys.com/features/ai-powered-integration-builder)). BetterCloud has had shared integrations after a security review since Sept 2019 ([BetterCloud](https://www.bettercloud.com/releasenote/09-25-19/)) | Fix #6 above |
| Calendly / Zendesk / Notion have no native connector ("No usage data") | F1, §15 | The company markets native integrations for all three (on its public integration pages) | Fix #5 above |

**Partly right**

| Claim | What's true |
|---|---|
| Calendly token setup "Integrations > API & Webhooks", no scopes | The path is now Profile menu > Developer > Personal access tokens. New tokens must pick at least one scope ([scopes](https://developer.calendly.com/docs/authentication/scopes)) |
| Zendesk `requests_per_minute: null` | The limits are published per plan: Team 200, Growth/Professional 400, Enterprise 700, High Volume 2,500 per minute |
| Notion `Notion-Version: 2022-06-28` | Still accepted. The latest version is **2026-03-11**, and `/v1/users` didn't change. Notion's rate limit is 180/min, or 600 on Business/Enterprise |
| Notion setup at notion.so/my-integrations | Integrations are now called "connections" in the Developer portal |
| "Customers save 10–30%" (ServiceNow listing) | The ServiceNow URL returns 404. The figure is on the company's own website (llms.txt): cite that instead |
| Atlassian per-user last-active endpoint stopped after 30 Jun 2026 | JRACLOUD-97537 is a customer *suggestion* ticket. Atlassian's endpoint page shows no deprecation notice, and community answers say the endpoint is not on the retirement list. Soften the claim, or swap in another drift example |

**Can't verify:** Torii's "about 1–5 minutes" and "license rules". Torii's help page blocks automated reading (it returns 403). See §10.

**Confirmed and worth keeping:**
- Calendly rate limits (500/50) and the `X-RateLimit-*` headers.
- The Owner/Admin requirement for org-wide events.
- The activity log is Enterprise only. Cite Calendly's OpenAPI, not Nexla.
- The Zendesk `last_login_at` API-token trap.
- The Notion email capability, and that guests are not returned.
- Zoom's 15-minute cursor and JWT end-of-life.
- Copilot's 24-hour lag.
- Asana Enterprise+ audit log, and the HubSpot login API.
- Torii's core "Build with AI" inputs.
- Zluri, Airbyte and Nango as described.
- The company's "500+ connectors".

---

## 5. Contradictions inside the PRD (Agent A)

- **Prototype claim.** §0 says "The prototype runs … end to end". §13 lists "Phase 0 Prototype" as not yet done.
- **Library connect skips the test.** §6 step 1: "paste token → done (skip to step 7)". §0: "Every connector goes Test → checked → Live". §14: "per-customer test still runs".
- **Library publish skips review.** §3, §6 and §8 say an engineer reviews before promotion. §15, A1, A9 `POST /publish` and CLAUDE.md all promote right away, with no review step.
- **Time promises.** The "Connect in 3 min" button vs the "New build ≤ 10 min" target (§11). Library connect is "30 seconds" (§3, §15) vs "≤ 2 min" (§11).
- **Rollout.** §12 decides "Internal first", but §14 still lists it as an open question.
- **Backtest size.** 30 apps (§9, §13) vs a "/10 apps" scoreboard (§11, §15).
- **Differentiators.** §0 lists "four things"; §3 lists "five ideas", with different items.
- **Repair rules.** §6 repairs only wrong paths and fields (exit code 4). A8 says "never for exit codes 2 or 3", which implies codes 5, 6 and 7 get repaired.
- **Drift codes.** Drift detection uses 404/410, but A6 maps only 400 and 404 to "repairable".
- **Evidence.** A3 requires evidence on every field and says the 3 specs MUST validate, but A4 leaves evidence out of those specs.
- **Notion usage.** Notion "use SSO data for usage", but `sso.csv` has no activity column.
- **Demo numbers.** "48 users · 6 left · 11 inactive" can't come from the 2-user Calendly account in A12.
- **Rate limits.** "Paging is kept below documented rate limits", but Notion and Zendesk are set to `null`.
- **What the LLM sees.** "AI sees public docs only", yet the admin's free-text hint goes to the LLM.
- **Section count.** L9 says "Part 1 (sections 0–14)", but Part 1 runs to §15.
- **Test apps per milestone.** CLAUDE.md milestones 2 and 4 cover only Zendesk and Calendly; A1 needs all 3.

---

## 6. Build-spec gaps in Appendix A (Agent A)

1. There's no actual JSON Schema. `aggregate`, `bootstrap.extract`, `variables`, `rate_limit`, `usage_definition`, where evidence goes, and how array query values are encoded are all undefined.
2. `active_rule` has no syntax: one spec says "usage_metric_value >= 1", another "last_active_at within 30 days".
3. **The savings math is undefined.** What counts as recoverable? How are people who are both "left" and "inactive" de-duplicated? What is the $ per seat? Where does "never assigned" come from? How is the connector's own admin account excluded?
4. **No seed data.** Acme and Globex inventories aren't given. Fixture emails must match the live account's users, or the join finds nothing. It's unclear whether the demo runs on fixtures or live accounts.
5. The "host family" allowlist is undefined. Docs hosted on stoplight.io or readme.io break it.
6. The sandbox proxy plumbing isn't specified: which proxy, and how each run's allowlist reaches it.
7. **State machine gaps.** What happens on partial success? For example, users OK but usage returns 403 (scenario SC-02).
8. Plain error messages are missing for `PAGINATION_LOOP`, `CURSOR_EXPIRED`, `MAPPING_FAILED`, timeouts, 5xx errors and a blocked host.
9. Library review has no mechanism: no queue, no approval endpoint, no approval column.
10. The UI has no visual reference, so the coding agent will invent the layout.
11. There's no SSRF guard on the docs fetcher, and no validation on variables like `subdomain`.

---

## 7. Old review notes vs this review

| Old item (`REVIEW_NOTES.md`) | Old status | What this review found |
|---|---|---|
| Figma not delivered | Partly fixed / Open | **Still open.** All 3 judging agents (A, B, D) flagged it |
| Prototype not delivered | Open | **Still open**, and §0 now wrongly claims it runs |
| Answers buried; §0 one-pager added | Fixed | **Mostly fixed.** §0 is good. But "AI doesn't write the code" and "the real risk is wrong cuts" are still buried |
| Model choice weak | Fixed | **Not really fixed.** The reasons are still generic and unpriced: an opinion, not a measurement |
| Calendly spec checked against OpenAPI | Fixed | **Partly.** It's missing `max_start_time`, it has no scopes, and the setup path is out of date |
| Too much marked MUST | Fixed | **Not fixed.** The prototype scope is still far too big for a take-home (B, D) |
| Edge = shared library + cross-check + renewals + fleet repair | Fixed (new stance) | **Partly wrong.** A shared library already exists at Josys and BetterCloud, and it carries legal/consent risk. Cross-check, renewals and usage depth still hold |
| "Torii has Build with AI" | Key correction | Confirmed. But Lumos and Josys also have AI builders, and the old review missed them |
| Atlassian as drift example | Fixed (past tense) | **Disputed.** The source is a customer suggestion ticket, not an Atlassian notice |
| Missing demo moment → §15 | Fixed | **Partly.** 7 beats don't fit in 5 minutes, library publish skips review, and the demo numbers can't come from a 2-user account |
| Cut length for the panel | Partly | **Still open.** About 7,000 words |
| Accounts: Zendesk trial | Open | **Now broken:** new Zendesk accounts can't use API tokens |
| — | — | **New:** The company already has native Calendly/Zendesk/Notion connectors; ~16 internal contradictions; no generated code; token-owner gap; SSRF; admin hint goes to the LLM; ServiceNow link is a 404; the status line references the review notes |

---

## 8. Point 2: What extra can we do? (CPO, Agent D)

### 8.1 What everyone else will submit (the bar to beat)

- **Flow:** a 5–6 step wizard. Paste URL → "AI analyzing…" spinner → pick endpoints → view code in an editor → enter API key → "Run in sandbox" → "Deploy to production" → health dashboard.
- **Figma:** made with Figma Make, v0 or Lovable. An integrations grid with a purple-sparkle "+ Build with AI" card, a code split view, and a green "200 OK · 48 users" screen.
- **Safeguards:** a generic list. Sandbox → prod, "least privilege" (with no real scope names), human code review, vault, backoff, egress limits, RBAC, audit log, kill switch, "prompt-injection guard", SOC 2.
- **Sandbox answer:** "Yes, mandatory sandbox with mock data." Most won't notice that most vendors give customers no sandbox at all.
- **Prototype:** Streamlit or Next.js, plus one prompt: "generate a Python client for Calendly". Usage data is skipped or faked.
- **Model:** "Claude Sonnet or GPT-5 for codegen, Haiku for parsing, RAG + Pinecone, LangChain." An opinion, not a measurement.
- **Common Calendly mistakes:**
  - assume a `/users` endpoint exists
  - quote 60 req/min from a blog
  - use an unscoped token
  - miss that org-wide events need an Owner/Admin token

### 8.2 Top 3 must-dos

**1. Open with a "Calendly truth table" and a "doc conflict" moment.** (Effort: about half a day)
- **The table:** how each vendor defines an "active" Calendly user. Columns: auth, scopes, where users come from, what "active" means, when it breaks, plus a cited link per row.
  - **Zluri:** marks every member "Active", so there is no usage at all ([Zluri](https://help.zluri.com/docs/calendly-data-processing)).
  - **1Password SaaS Manager:** uses "last updated" as last login, and its connector breaks if the connecting user is deactivated ([1Password](https://support.1password.com/saas-manager-calendly/)).
  - **ServiceNow SAM:** uses scheduled events over 60 days ([ServiceNow](https://www.servicenow.com/docs/r/it-asset-management/saas-license-management/integrate-with-calendly.html)).
  - **Torii:** needs a users endpoint.
  - **Your builder:** meetings hosted in 90 days, labelled as a proxy, with cited docs.
- **Live:** the evidence drawer in F3 shows the builder finding 60 rpm in a third-party guide and 500 rpm on Calendly's own page, then picking the official one with a quote. Back it up with research showing LLMs invent endpoint URLs up to 39% of the time ([WAPIIBench](https://arxiv.org/abs/2509.20172)).
- **The message:** "On your own example, AI-built matches the best hand-built definition and beats 'everyone is Active'."
- **Don't** say the company's own Calendly page is weak. Frame it as an opportunity instead.

**2. Make "the connector token is our biggest liability" the spine of the safeguards answer.** (Effort: about 1 day)
- **Open with real incidents:** the Salesloft Drift OAuth tokens were used against 700+ orgs' Salesforce (Aug 2025), then Gainsight 200+ (Nov 2025). A SaaS-management platform that holds read tokens to hundreds of apps is exactly that target.
- **(a) Exact scopes at setup:** `users:read`, `organizations:read`, `scheduled_events:read`. Flag old unscoped Calendly tokens, which keep full access.
- **(b) Token-owner warning:** show who owns each token. In the demo, mark that admin as a leaver in `hris.csv`, and F6 shows "Connector breaks when Priya is offboarded on 3 Nov: rotate to a service account". 1Password documents this exact failure, and the company's own offboarding product can prevent it.
- **(c) Non-human identities:** every connector token appears in the company's non-human-identity view (age, scopes, last use, owner). This turns the company's own pitch on itself.
- **(d) Contain a breach:**
  - each tenant's credentials encrypted under its own key
  - published static egress IPs, so customers can IP-restrict tokens
  - an alert when call volume is far above normal
  - repairs rolled out to a few tenants first

**3. Answer "which AI model?" with measured numbers, not opinion.** (Effort: about 1 day, about $10–20 of API spend)
- **The test:** 3 apps (Calendly, Zendesk, Notion) × 3 setups (Haiku 5.5, Sonnet 5.5, Opus 5.5 at low effort) × 3 runs = 27 drafts.
- **Score each draft on:**
  - schema-valid
  - evidence quotes verified
  - sandbox test passes
  - user count equals the admin UI
  - repairs needed
  - $ and seconds
- **The slide:** one line: "We use X: N/9 passed, 0 repairs, $Y per connector."
- **The point to make:** model cost is tiny next to 30–60 minutes of engineer review, so choose on pass rate and repairs.

### 8.3 All differentiator ideas

Type A = product idea. Type B = how you present or prove it.

| # | Idea | Type | Effort | Impact | Already in PRD? |
|---|---|---|---|---|---|
| 1 | Calendly usage truth table vs competitors | B | S | High | New |
| 2 | Doc-conflict demo moment (evidence made visible) | B | S | High | Partly (§6, A3) |
| 3 | Connector tokens as governed non-human identities (scopes, owner, offboarding warning) | A | S–M | High | New |
| 4 | Blast-radius design anchored on Drift/Gainsight | A | S | Med-High | Partly (§8) |
| 5 | **MCP stance.** Vendor MCP servers don't give admin or usage data (Calendly's is per-user scheduling only), so the builder targets admin REST APIs. Its output then becomes queryable through the company's own MCP server (GA May 2026). Demo ending: "Ask Claude who hasn't hosted a Calendly meeting in 90 days" | A | S | Med-High | New |
| 6 | Clean-room library: the company rebuilds library specs; customer builds stay private; "used by N" only when N ≥ 5 | A | S | High | Partly (§3, §14) |
| 7 | Usage-signal grade (feature / login / event proxy / members only) + a fallback ladder (SSO logins → browser extension → admin CSV) | A | S–M | Med | Partly (§5, §8) |
| 8 | Auto-generated "connector data card" PDF for security review (endpoints, scopes, fields, retention, egress IPs) | A | S–M | Med | New |
| 9 | Measured model answer (27-draft benchmark) | B | M | High | Partly (§9 plans it for later) |
| 10 | 3–5 real buyer conversations (IT, procurement, security), quoted on 1 slide | B | M | High | New |
| 11 | Real clickable Figma + a 3-minute Loom of the live run | B | M | High (hygiene) | Partly (§7) |
| 12 | Backtest scoreboard on ~10 public APIs | B | L | High | Partly (§11, §15) |

**Ranked by impact for the effort:** 1 > 3 > 6 > 2 > 5 > 4 > 9 > 11 > 10 > 8 > 7 > 12. (#6 and #11 are really fixes to the current submission, not extras.)

### 8.4 Already distinctive in your PRD: push these harder

- **"AI decides, templates write."** No AI-written code ever runs. This is the cleanest answer to "we're asking customers to be developers". Make it slide 2.
- **The risk reframe:** wrong usage data → wrong seat cuts matters more than "code breaks prod". Lead with it, paired with the token risk.
- **The honest sandbox answer:** vendors rarely offer sandboxes, so the company's runner reads real data, read-only.
- **The T1–T4 usage tiers and the "Traps" table.** The Zendesk `last_login_at` trap and Zoom's cursor expiry are the strongest research in the PRD, and they deserve their own slide.
- **Company-only mechanics:** the HRIS/SSO/contract cross-check, the F5 savings ending, the F1 inventory/renewal entry, and renewal-triggered drafting.
- **"Read-only is checked on the operation, not the HTTP method."**
- **"Torii already ships Build with AI."** Say it in the first 60 seconds. Add Lumos and Josys too.

### 8.5 Still commodity in your PRD (looks like everyone else's)

- The core flow (§6) and frames F3, F4 and F6. Only F1 and F5 stand out.
- §8 "Also covered": vault, revoke, audit, prompt injection and kill switch, with no scope names.
- §9 model reasons ("reads long docs, strict JSON, available on clouds").
- The §10 business case built on standard assumptions.
- §4 personas, §11 metrics (except the "spend coverage" north star) and the §13 phased roadmap.
- The Appendix A stack. Keep it out of the slides.

### 8.6 Risky from a CPO's view

1. **A shared library built from customer builds, plus contribution credits.** Consent, IP and liability risk. Leak paths include free-text hints, custom field names, subdomains and small "used by" counts. Fix: clean-room rebuilds, opt-in only, N ≥ 5.
2. **"One fix repairs it for every customer."** One bad AI repair breaks every tenant at once. Add a canary rollout and auto-rollback.
3. **The word "Integration Factory"** is Lumos's published term.
4. **"Replace 5–10 engineer-days per connector"** may irritate the CTO and the integrations team on the panel. Reframe it as: "frees the integrations team to deepen the top connectors; the long tail is net-new coverage."
5. **Events-based Calendly usage is not unique.** ServiceNow already does it. It's only ahead of Torii and Zluri.
6. **The prototype scope** (7 milestones, Docker egress proxy, vault, 3 live apps, 2 tenants, fleet view) makes the demo fragile. Cut it as in fix #1.

---

## 9. Questions the panel will likely ask (Agent B)

1. What share of our long tail fits your spec format? Think GraphQL, SOAP, multi-step auth and custom fields. How is this different from Airbyte's low-code builder with an LLM in front?
2. Legal says customer-built specs can't be shared. What's left of your strategy?
3. Customer B cuts 12 Calendly seats based on a library spec, and 4 of those were real users. Who is accountable? Which of your metrics would have caught it?
4. The Calendly Owner token sits with someone in marketing, not IT. Walk me through "Connect in 3 min" in that company.
5. Net of the Okta/Entra login data we already have, how many of your "40 apps" are truly dark? Redo the $ math.
6. What did you actually run to pick Sonnet 5.5? If a rival model is 30% cheaper and 3 points worse, which one do you ship?
7. Sales needs an answer to Torii in 90 days. What do you ship, and what do you say no to?
8. A CISO hears "sandbox" and assumes we have no production access. Read-only is enforced by us, not by the token. What happens to their admin tokens if the company is breached?
9. (New, from the fact-check) We already have Calendly, Zendesk and Notion connectors. Why demo those?

---

## 10. Not verified, or where agents disagreed

- **Torii "about 1–5 minutes".** Agent D says it confirmed this on Torii's product-update page. Agent C couldn't open the help page (403). **Check it yourself in a browser before the panel.**
- **Torii "license rules"** at field level: unverified by both agents.
- **Model prices.** Agent D quoted Haiku 5.5 $0.10/$0.50, Sonnet 5.5 $2/$10 and Opus 5.5 $4/$20 per million tokens, which works out to about $0.28 per connector on Sonnet. **I have not verified these.** Check Anthropic's pricing page before using any $ figure.
- **A "universal integration builder" at the company** mentioned in one G2 search summary: no source found. Ask the company.
- **The "Senior PM, Integrations" job post** was seen on an aggregator. Verify it before quoting it.
- **The Atlassian endpoint deprecation** is disputed (see §4).
- **The hire signal and scores** are one AI agent's opinion, not the company's.

---

## 11. Key sources (added by this review)

- Zendesk API token removal: https://support.zendesk.com/hc/en-us/articles/10851263566234 · OAuth migration: https://developer.zendesk.com/documentation/authentication/oauth-migration/ · Rate limits: https://developer.zendesk.com/api-reference/introduction/rate-limits/
- The company's native connector pages, press page and MCP server post: on its public website (not linked, to keep this repo company-neutral)
- Shared libraries elsewhere: Josys https://www.josys.com/features/ai-powered-integration-builder · BetterCloud https://www.bettercloud.com/releasenote/09-25-19/ · Airbyte https://docs.airbyte.com/platform/connector-development/connector-builder-ui/overview
- AI builders elsewhere: Lumos https://www.lumos.com/blog/how-we-use-ai-to-build-integrations · Fivetran https://fivetran.com/docs/connectors/ai-connector-agent/setup-guide
- Calendly scopes: https://developer.calendly.com/docs/authentication/scopes · Personal tokens: https://developer.calendly.com/personal-access-tokens · MCP server: https://developer.calendly.com/calendly-mcp-server
- How others treat Calendly usage: Zluri https://help.zluri.com/docs/calendly-data-processing · 1Password https://support.1password.com/saas-manager-calendly/ · ServiceNow https://www.servicenow.com/docs/r/it-asset-management/saas-license-management/integrate-with-calendly.html
- Notion versioning: https://developers.notion.com/reference/versioning · Request limits: https://developers.notion.com/reference/request-limits
- LLM API hallucination study: https://arxiv.org/abs/2509.20172
- Token breaches: https://www.secureworld.io/industry-news/salesloft-drift-breach-salesforce-data · https://www.techradar.com/pro/security/google-security-experts-say-gainsight-hacks-may-have-left-hundreds-of-companies-affected
