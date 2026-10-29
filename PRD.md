# AI-Generated Integration Builder — PRD

**For:** Senior PM take-home assignment
**Author:** Sujeet Kumar
**Date:** 29 Oct 2026
**Status:** v4. Generic builder, Gemini as the AI model. The technical build spec moved to `TRD.md`.

How the documents fit together:

| Document | Answers |
|---|---|
| **`PRD.md`** (this file) | What we build and why: problem, customer, approach, safeguards, model choice, metrics, demo |
| `TRD.md` | How the prototype is built: spec format, engine, sandbox, AI pipeline, API, tables, savings math |
| `DESIGN.md` | How it looks: colours, type, spacing, components, writing rules, screen layouts |
| `EVAL.md` | How we know it works: the AI quality eval, acceptance scenarios, security tests, test plan |

---

## 0. Answers to the assignment (one page)

**What we build.** A **generic** builder. An admin points the platform at **any** app's API docs. AI reads the docs and fills in a **connector spec**, which is a structured form that says:
- how to log in;
- where the list of users is;
- where usage data is;
- what the limits are;
- how the app's fields map to the platform's user record.

Every answer carries a quote from the docs as proof. Fixed templates then turn the spec into code, the same templates for every app. The platform test-runs that code in a locked sandbox and cross-checks the numbers against data it already holds. It then shows the savings before the connector goes live.

**How "AI generates the code".** The AI writes the spec, and the templates write the code. The generated code covers all six items the assignment asks for: API client, auth setup, users and usage, error handling, pagination and logging (§6.4). We split it this way for three reasons:
- every connector behaves the same way;
- no AI-written code ever runs;
- the thing to check is small, a spec instead of a program.

| Deliverable | Our answer | Where |
|---|---|---|
| **1. Figma** | We answer with a **clickable prototype** instead of static Figma frames, so the panel can click through the real flow. 8 screens (F1–F8). The flow starts **inside the app inventory and the renewal flow** and ends on a **savings screen**, not on a code screen. | §7 |
| **2. Safeguards / sandbox then prod** | **Yes, Test → checked → Live.** But the sandbox is **the platform's own isolated runner**. It reads the customer's real data with read-only calls, because most vendors don't give customers a test account. The two real risks are: (1) **wrong usage data that leads to cutting seats people use**, and (2) **the connector token itself** (see the Drift breach, §8). And we stop asking customers to be developers: nobody writes or edits code, ever. | §8 |
| **3. Prototype + AI model** | **One generic engine**, proven on three different app shapes and one "surprise" app pasted live (§5.4). **Model:** Google Gemini. `gemini-3.8-flash` drafts and repairs; `gemini-4-argon` handles the final repair attempt. Both sit behind a swappable interface, and **the choice is made by a measured benchmark**, not opinion. | §9, `TRD.md`, `EVAL.md` |

**What makes this different.** AI-built connectors already exist in our market (Torii, Lumos, Josys), and so do shared integration catalogs (BetterCloud, Josys). So neither one is an edge on its own. The platform can win on five things, and this list is used everywhere in this document:

1. **Real usage, clearly labelled.** Not just a user list. Every usage number says what it measures.
2. **Automatic cross-check** with HRIS, SSO and contract data the platform already holds.
3. **Starts from renewals and inventory**, where the money decision happens.
4. **The connector token is governed like any other identity**: exact scopes, a known owner, and a warning before that owner leaves.
5. **A checked library run by the platform team.** Build once, review, share. Repairs roll out to a few customers first, then to everyone.

---

## 1. Problem

**One line:** The platform can only save money on apps it has a connector for. Every connector is hand-built by an engineer, so a lot of a customer's long tail has no seat-level usage data.

- The platform shows a company its SaaS apps, who has a seat and who uses it, so unused seats can be cut. It markets 500+ pre-built connectors across SSO, HRIS, finance, help desk, CLM and SaaS apps (company website).
- The assignment names four things that differ per app:

  | What differs per app | Example | What breaks if wrong |
  |---|---|---|
  | API endpoints | Calendly lists users at `/organization_memberships`; other apps use `/users` | Missing users |
  | Auth model | Personal token, email + token, OAuth client credentials | Can't connect, or too much access |
  | Rate limits | Calendly: 500 requests/user/minute on paid plans, 50 on free ([Calendly](https://developer.calendly.com/api-docs/overview/rate-limits)) | Sync blocked (429) |
  | Data structures | `last_login_at` vs `last_activity_at` vs no usage field at all | Wrong "inactive" flags |

- **Without a connector,** the platform relies on SSO and finance data. SSO shows logins, not real use, and it doesn't see apps used with personal logins (company blog). The customer sees spend but not who really uses the app, so they can't act before a renewal.

**Problem statement:** The platform needs a way to get users, seats and usage for any app with a public API in minutes, without engineering time per customer. It must also be safe and correct enough that a customer can cut seats based on it.

---

## 2. What already exists, and what that means

**Finding: AI-built connectors and shared integration catalogs both already exist.** The platform can't win by having them. It can win on what the connector measures, how it is checked, and where it is used.

| Company | What they offer for apps without a connector | AI from docs? | Shared with other customers? |
|---|---|---|---|
| **Torii** | Integration Builder with "Build with AI". Input is a docs link, pasted docs, a sample API response or hints. It drafts auth, the users endpoint with paging, and field mappings (incl. last visit time); a test call validates the draft. Enabled per account; the app needs a users endpoint ([Torii](https://support.toriihq.com/hc/en-us/articles/48261770863771-Integration-Builder-Build-Your-Own-Integration)) | Yes | Per customer |
| **Lumos** | "AI-Powered Integration Builder" plus a Connector SDK ([Lumos](https://www.lumos.com/integrations), [blog](https://www.lumos.com/blog/how-we-use-ai-to-build-integrations)) | Yes | Not stated |
| **Josys** | An AI integration builder that records actions in the app's admin console (no API docs). Broadly useful builds may be reviewed and promoted to its App Catalog for all customers ([Josys](https://www.josys.com/features/ai-powered-integration-builder)) | Browser, not API | **Yes, after review** |
| **BetterCloud** | Customers can share an integration; after a security review it is listed for other customers (since 2019) ([BetterCloud](https://www.bettercloud.com/releasenote/09-25-19/)) | No | **Yes, after review** |
| Zluri | An SDK to push users and usage, plus AI browser automation for apps with no API ([SDK](https://developers.zluri.com/docs/custom-integrations), [AI integrations](https://help.zluri.com/docs/ai-powered-integrations)) | Browser, not API | Vendor-built catalog |
| Airbyte (data integration) | AI Assist reads docs or OpenAPI and fills in auth, paging and streams. Builders can submit connectors to a reviewed marketplace ([Airbyte](https://docs.airbyte.com/platform/connector-development/connector-builder-ui/ai-assist)) | Yes, as config | Marketplace |
| Fivetran (data integration) | AI Connector Agent (beta), REST + JSON only. Fivetran itself says the output "won't be production-ready" and AI doesn't change who gets paged ([setup](https://fivetran.com/docs/connectors/ai-connector-agent/setup-guide), [blog](https://www.fivetran.com/blog/ai-can-build-your-data-connector-heres-what-it-cant-do)) | Yes | — |
| Nango (integration platform) | AI writes TypeScript integration functions, then dry-runs them against a real connection ([Nango](https://github.com/nangohq/nango)) | Yes, as code | — |

**What we did not find in any competitor material:**
- API-based connectors that bring real usage depth;
- automatic cross-checks against HRIS, SSO and contract data;
- connector drafts triggered by renewals;
- repairs rolled out in stages across customers.

Not finding them is not proof that nobody does them, but these are the edges this PRD builds on.

### 2.1 The assignment's own example: what "active" means for Calendly

| Product | Where users come from | What "active" means | Known catch |
|---|---|---|---|
| Zluri | Org members | Every member is marked "Active", so there is no usage at all ([Zluri](https://help.zluri.com/docs/calendly-data-processing)) | No signal for seat cuts |
| 1Password SaaS Manager | Org members, via OAuth | "Last login" is really Calendly's "last updated" field | The integration stops if the connecting user is deactivated ([1Password](https://support.1password.com/saas-manager-calendly/)) |
| ServiceNow SAM | Org members | Scheduled events in the last 60 days (default) ([ServiceNow](https://www.servicenow.com/docs/r/it-asset-management/saas-license-management/integrate-with-calendly.html)) | Hand-built by ServiceNow |
| Torii Build with AI | Needs a users endpoint | Depends on the fields drafted | Built per customer |
| **This builder** | Org members | **Meetings hosted in the last 90 days, labelled "proxy"**, with every field quoted from Calendly's docs | People who only attend meetings show 0; the label says so |

**What this shows:** AI-built doesn't mean shallower. On the assignment's own example, an AI-built connector can match the best hand-built definition and beat "everyone is Active". (The platform already has its own native Calendly connector. This table is about definitions, not about the platform's connector.)

### 2.2 Why not just use vendor MCP servers?

Vendors are shipping MCP servers, but these are built for one person's own data, not for an admin's view of the whole company. For example, Calendly's official MCP server:
- uses OAuth with dynamic client registration only, so personal tokens don't work;
- only offers scheduling scopes for the signed-in user;
- gives no org membership list and no usage data ([Calendly MCP](https://developer.calendly.com/calendly-mcp-server)).

**So the builder targets admin REST APIs.** Its output then becomes something people can ask about through **the platform's own MCP server** (GA May 2026). For example: "Who hasn't hosted a Calendly meeting in 90 days?"

---

## 3. Our approach: build once, check, share, run by the platform team

**Stance (this challenges the assignment's premise):** don't turn customers into developers, not even "safe" ones. The unit of work is the **app**, not the customer. The platform's own team builds and checks each app's connector once, from public docs, and puts it in a shared library. Customers can self-serve for apps the library doesn't have yet. **Their builds stay private** unless they opt in.

**How it works over time:**
1. **Pick the apps.** The **Opportunity Map** ranks apps that have no connector by total spend × number of customers. The platform team builds the top ones first.
2. **Build and check.** The platform team builds the connector with AI from public docs. It passes the sandbox test and the cross-check on a design-partner tenant. A platform engineer reviews it and publishes it to the library.
3. **Connect.** Every customer sees "App X: in the platform library", pastes their own token, and goes live. **Their own test always runs first.**
4. **Watch the fleet.** Every run is a health signal. If an app changes its API, failures show up across customers before anyone files a ticket. Each repair is reviewed, rolled out to a few customers first (a **canary**), then to everyone, and rolled back automatically if the canary fails.
5. **Learn.** Every correction becomes a test case, so the AI does better on the next app.

**What is shared and what is never shared**

| Shared across customers | Never shared |
|---|---|
| The connector spec (endpoints, paging, field mapping, usage rule) with customer-specific values removed; generated code; health stats, aggregated, with "used by N" shown only when N ≥ 5 | Tokens, user data, counts, company names, subdomains, custom field names, admin hints |

**Customer-built connectors.** They are private by default. If a customer opts in to share, the platform team **rebuilds the connector from public docs** (a "clean room" rebuild) instead of copying the customer's spec. That way no customer-specific detail leaks into the library. Consent terms are an open question (§14).

**The five edges**

| # | Edge | Why the platform is well placed | What it looks like |
|---|---|---|---|
| 1 | **Real usage, clearly labelled** | It sells "feature-level usage, not just logins" (company website) | Usage tiers T1–T3 (§5.2); labels like "Meetings hosted (90 days) · proxy" |
| 2 | **Automatic cross-check** | It already holds HRIS (who left), SSO (who is assigned) and contract (seats bought) data | "48 users · 6 left the company · 60 seats bought, 12 never assigned" |
| 3 | **Starts from renewals** | It already tracks renewal dates | 90 days before a renewal on an app with no usage data, the owner is nudged and a draft is prepared |
| 4 | **Token governed like an identity** | It sells identity governance and offboarding | Exact scopes, a named owner, "Token owner leaves on 3 Nov: switch to a service account" |
| 5 | **A checked library with staged repairs** | Many customers on one platform; a spec carries no customer data | "In the platform library · checked · healthy"; repairs roll out to a canary group first |

---

## 4. Customer

| Person | Role here | Needs | Must never have to |
|---|---|---|---|
| **IT admin (primary)** | Connects apps | Usage for apps with no connector, before the renewal | Read, write or debug code |
| **App owner** (e.g. marketing ops holds the Calendly owner account) | Holds the admin token for a long-tail app | A simple, safe way to hand over a scoped token | Share a password or a full-access token |
| SaaS / procurement manager | Uses the data | Trustworthy unused-seat numbers in $ | Wonder if the data is wrong |
| Security / IT governance | Approves the connection | Read-only access, exact scopes, an audit trail, and a data card for security review | Accept unknown code with admin tokens |
| Platform integrations engineer (internal) | Builds and reviews library connectors | Readable code, a test report, fleet health | Build every long-tail connector by hand |
| Platform CSM (internal) | Helps when something fails | Plain error reasons and run logs | Guess |

**Job to be done:** "Our renewal for App X is in 60 days and the platform shows no usage for it. I want to see who actually uses it, today, without asking engineering."

---

## 5. What "generic" means, and which apps

### 5.1 The five questions the AI answers for every app

For any app, the AI reads the docs and answers the same five questions. The answers are the spec:

1. **How do we log in?** Bearer token, basic auth, API key header, or OAuth client credentials. Which role and scopes are needed?
2. **Where is the list of users?** Which URL, how pages are split, which records are real seats (not end customers or guests)?
3. **Where is usage?** See the tiers below.
4. **What are the limits?** Rate limits, plan requirements, roles.
5. **How do the fields map** to the platform's standard user record (`TRD.md` §5)?

Only the spec is different for each app. Every other step is the same for every app.

### 5.2 Usage tiers (users are easy; usage decides the value)

| Tier | What the API gives | Examples | If usage is weak or missing |
|---|---|---|---|
| **T1** | The user list includes a last-login or last-activity field | Zendesk (`last_login_at`), Zoom (`last_login_time`), GitHub Copilot seats (`last_activity_at`) | — |
| **T2** | Users, plus a separate events/log endpoint; usage is counted per user | Calendly (meetings hosted), HubSpot (login activity) | Label it as a **proxy** |
| **T3** | Users only; no usage on most plans | Notion public API, Asana (activity only via the Enterprise+ audit log) | **Fall back** to SSO last login, labelled "from SSO, not from the app" |
| **Not supported yet** | No public API; docs behind a login; SOAP/XML; on-prem software; OAuth that needs a platform-registered app (e.g. Slack) | Many niche apps; Slack | Built by the platform team, or on the roadmap |

**Fallback ladder when an app has no usage data:** SSO last login (data the platform already holds), then the platform's browser-extension signal, then an admin CSV upload (later).

### 5.3 What the spec format covers today (honest limits)

| Covered in v1 | Not yet covered |
|---|---|
| REST APIs that return JSON | GraphQL, SOAP/XML |
| Login: bearer token, basic auth, API key header, OAuth client credentials | OAuth that needs the platform to register an app with the vendor (Slack, Google, Microsoft) |
| Paging: none, cursor, next URL, Link header, offset/limit, page number | POST-based search endpoints |
| Read calls only (GET; POST only to get a login token) | Usage APIs that need one call per user |
| Usage from a field on the user, or by counting records from an events endpoint | Async report/CSV export APIs; apps with no API (browser automation) |

**How much of the long tail fits?** We don't know yet. Phase 1 measures it on 30 apps (§13).

### 5.4 Test apps for the prototype, and why

| App | Shape it proves | Why this app |
|---|---|---|
| **Zendesk** | T1: a last-login field on the user list; OAuth client credentials | A common help-desk app with a known trap (below) |
| **Calendly** | T2: usage counted from separate event records | The assignment's own example |
| **Notion** | T3: users only, with usage from the SSO fallback | Shows honest handling of "no usage data" |
| **Surprise app** | Any app with no example spec and no app-specific code | Proves the engine is generic. Chosen from apps **not** listed on the platform's public integrations page, pasted live |

The platform already has native connectors for Zendesk, Calendly and Notion. That makes them useful here: they double as an **answer key**. The AI-built connector must match the user counts on each app's admin screen (and the platform's native connector, if the company can share those counts).

### 5.5 Traps the AI must catch (each one is a test case)

| App | Trap |
|---|---|
| Calendly | Org-wide scheduled events need an **Owner or Admin** token **and** the `scheduled_events:read` scope, so a 403 can mean either one is missing. New tokens must pick scopes; tokens made before scopes existed have full access. The activity log is Enterprise only. Rate-limit info comes in `X-RateLimit-*` headers, and no `Retry-After` is documented. `min_start_time` has no upper bound, so without `max_start_time` future meetings get counted ([OpenAPI](https://calendly.stoplight.io/api/v1/projects/calendly/api-docs/nodes/reference%2Fcalendly-api%2Fopenapi.yaml), [scopes](https://developer.calendly.com/docs/authentication/scopes), [rate limits](https://developer.calendly.com/api-docs/overview/rate-limits)) |
| Calendly docs | A third-party guide quotes 60 requests/min and a `Retry-After` header. Calendly's own page says 500/min on paid plans and 50 on free. The builder must prefer the vendor's page and show the conflict (§6.3) |
| Zendesk | End users are customers, not seats, so filter to agents and admins. `last_login_at` also updates on API-token calls, so the connector's own account always looks active. **API tokens are being retired:** no new tokens since 27 Oct 2026, and all of them stop on 30 Apr 2027, so use OAuth client credentials ([Users API](https://developer.zendesk.com/api-reference/ticketing/users/users/), [token removal](https://support.zendesk.com/hc/en-us/articles/10851263566234)) |
| Zoom | `next_page_token` expires in 15 minutes. JWT apps are end-of-life; use Server-to-Server OAuth with `grant_type=account_credentials` ([Zoom](https://developers.zoom.us/blog/why-use-server-to-server-oauth.md)) |
| GitHub Copilot | `last_activity_at` can lag about 24 hours and needs IDE telemetry ([GitHub](https://docs.github.com/copilot/managing-copilot/managing-github-copilot-in-your-organization/reviewing-activity-related-to-github-copilot-in-your-organization/reviewing-user-activity-data-for-copilot-in-your-organization)) |
| Notion | No usage in the public API. Email comes back only with the "User information with email addresses" capability. Guests are not returned ([Notion](https://developers.notion.com/reference/get-users)) |
| Atlassian | Atlassian is retiring many v1 org-admin APIs. A public suggestion ticket says the per-user last-active API is affected, and community answers dispute it ([JRACLOUD-97537](https://jira.atlassian.com/browse/JRACLOUD-97537)). Either way, vendors change usage APIs, which is why drift detection matters |

---

## 6. How it works

**Design rule: AI decides, templates write.**

| Layer | Who | Output | Why |
|---|---|---|---|
| Brain | LLM reads the docs | A **connector spec** (JSON). Every field has a docs quote, or an OpenAPI pointer, as evidence | Small, checkable, testable |
| Checks | Code (no AI) | Pass/fail on evidence, read-only calls, the app's own host, no secrets in URLs | Rules the AI can't talk its way around |
| Hands | Templates (no AI) | Readable Python: API client, auth, users, usage, error handling, paging, logging | The six assignment items behave the same in every connector |
| Run | Locked sandbox | Users + usage in the platform's standard format, plus a test report | Code can only make read calls to one host |
| Cross-check | Code (no AI) | Joins the users with HRIS, SSO and contract data | Catches wrong data before anyone cuts a seat |

### 6.1 The flow (any app)

```
App list ─► Is App X in the library?
              ├─ Yes ─► Paste token ─► Test ─► Savings ─► Live
              └─ No  ─► Paste docs ─► AI fills spec ─► Auto checks ─► Admin reviews
                        ─► Paste token ─► Templates write code ─► Test (auto-fix ≤3)
                        ─► Savings ─► Live ─► Submit to library ─► Platform review
```

1. **Start (F1).** In the app list, App X shows its spend, its renewal date and "No usage data". The admin clicks **Connect usage data**.
2. **Library check (F2).**
   - **If App X is in the library:** jump to step 7. The admin only pastes their own token.
   - **If not:** go to step 3.
3. **Paste docs (F3).** The admin pastes App X's API docs link, or uploads its OpenAPI file.
4. **AI fills the spec (F3, live progress).** It answers the five questions in §5.1 and attaches a docs quote to every answer.
5. **Automatic checks (no AI).**
   - Every quote really exists in the docs.
   - Only read calls.
   - Only App X's own host.
   - No secrets in URLs.
   - If a check fails, the field is dropped and the AI is asked once more.
6. **Admin review in plain words (F4).** For example: "Login: API token from an Admin, scopes X and Y. Users: yes. Usage: last login date." It comes with token setup steps. The buttons are **Looks right** and **This looks wrong**, which lets the admin add a hint.
7. **Paste the token (F5).** The token is stored encrypted and never shown to the AI. If the admin doesn't hold the token, they click **Ask the app owner**, which makes a one-time link the app owner can use to paste a scoped token.
8. **Code is generated.** Templates turn the spec into code. The same templates are used for every app.
9. **Test run in a locked sandbox (F5).** It reads all users and a sample of usage, read-only, and can only reach App X's own host.
   - **Wrong URL, field or paging:** the AI fixes the spec and retries, up to 3 times.
   - **Permission, scope or plan problem:** the admin gets a plain message, for example "This token needs the Admin role and scope X". There is no auto-fix.
   - **Users work but usage is blocked:** the admin can go live with users only, clearly labelled.
10. **Cross-check and savings preview (F6).** The users are compared with HRIS (who left), SSO (who is assigned) and the contract (seats bought). The screen shows: N users, X left the company, Y inactive, Z seats never assigned, and $ recoverable before the renewal. Every number shows its source.
11. **Go live.** The admin confirms, and the connector syncs daily.
12. **Library (F8).** Once the connector is live and healthy, the admin can **submit it to the library**. Customer-specific values are stripped, and a platform engineer reviews it before any other customer can see it.
13. **Ongoing (F7, F8).** If App X changes its API, the connector shows **Needs repair** and keeps the last good data, marked stale. The AI proposes a fix, an engineer reviews it, and it rolls out to a canary group first, then to everyone.

### 6.2 What the AI sees and never sees

- **Sees:** public docs; masked error samples (keys and types only, no values); the admin's hint **after scrubbing**. Scrubbing removes emails, names that match users, long numbers, URLs with query strings, and anything that matches a stored secret.
- **Never sees:** tokens, user data, real names, emails, counts, company names.

### 6.3 Evidence and doc conflicts

- **Evidence on every field.** Each spec field needs a docs quote (≤ 25 words) or an OpenAPI pointer, and code checks that it exists. The reason: research shows LLMs invent endpoint URLs up to 39% of the time when writing API code ([WAPIIBench](https://arxiv.org/abs/2509.20172)).
- **Source ranking when docs disagree:** the vendor's API reference, then the vendor's OpenAPI file, then the vendor's guides, then third-party pages.
- **Conflicts are shown, not hidden.** For example: "Rate limit: a third-party guide says 60/min; Calendly's rate-limit page says 500/min on paid plans and 50 on free. We used Calendly's page." This shows up as a chip in the evidence drawer (F4).

### 6.4 What the generated code looks like (illustrative excerpt)

An excerpt for Calendly. The real file is rendered by the prototype from the spec in `TRD.md` §4. Comments mark the six assignment items.

```python
# calendly_v1.py  (generated from spec "calendly" v1 by templates; do not edit)
import json, logging, random, time
from collections.abc import Iterator
import httpx, jmespath
from runtime.transport import AllowOnlyHost   # blocks every host except the spec's

log = logging.getLogger("connector.calendly")

class ConnectorError(Exception):
    def __init__(self, code: str, status: int | None = None) -> None:
        super().__init__(code)
        self.code, self.status = code, status

# 1. API client  +  2. Auth setup (bearer token; scopes users:read, organizations:read, scheduled_events:read)
class Client:
    def __init__(self, secrets: dict[str, str]) -> None:
        self.http = httpx.Client(
            base_url="https://api.calendly.com", timeout=30,
            transport=AllowOnlyHost("api.calendly.com"),
            headers={"Accept": "application/json",
                     "Authorization": f"Bearer {secrets['token']}"})

    def get(self, path: str, params: dict[str, str]) -> dict:
        for attempt in range(5):
            start = time.monotonic()
            r = self.http.get(path, params=params)
            # 6. Logging: method, path, status, timing. Never bodies, never tokens.
            log.info(json.dumps({"method": "GET", "path": path, "status": r.status_code,
                                 "ms": int((time.monotonic() - start) * 1000), "retry": attempt}))
            # 4. Error handling
            if r.status_code == 429:   # Calendly sends X-RateLimit-Reset, no Retry-After
                time.sleep(int(r.headers.get("X-RateLimit-Reset", 2 ** attempt)) + random.random())
                continue
            if r.status_code >= 500 and attempt < 3:
                time.sleep(2 ** attempt)
                continue
            if r.status_code == 401: raise ConnectorError("AUTH_REJECTED", 401)
            if r.status_code == 403: raise ConnectorError("PERMISSION_OR_SCOPE", 403)
            if r.status_code in (400, 404, 410): raise ConnectorError("WRONG_REQUEST", r.status_code)
            if r.status_code >= 500: raise ConnectorError("SERVER_ERROR", r.status_code)
            return r.json()
        raise ConnectorError("RATE_LIMITED_OUT")

    # 5. Pagination (cursor)
    def pages(self, path: str, params: dict[str, str]) -> Iterator[dict]:
        seen: set[str] = set()
        while True:
            body = self.get(path, params)
            yield from body["collection"]
            token = jmespath.search("pagination.next_page_token", body)
            if not token:
                return
            if token in seen:
                raise ConnectorError("PAGINATION_LOOP")
            seen.add(token)
            params = {**params, "page_token": token}

# 3. Users (usage: get_usage() counts meetings hosted per user, last 90 days up to now)
def get_users(c: Client) -> Iterator[dict]:
    org = c.get("/users/me", {})["resource"]["current_organization"]
    for m in c.pages("/organization_memberships", {"organization": org, "count": "100"}):
        email = m["user"].get("email")
        yield {"external_id": m["user"]["uri"], "email": email.lower() if email else None,
               "name": m["user"].get("name"), "role": m["role"],
               "is_admin": m["role"] in ("owner", "admin"), "status": "active"}
```

---

## 7. Screens (Deliverable 1: a clickable prototype instead of static Figma)

**Decision:** we answer "Can you generate the Figma?" with the **clickable prototype's screens**. The panel can click through the real flow, and screenshots of each screen go into the submission. Plain language throughout; technical detail sits behind a toggle. Colours, type, components and screen layouts are in `DESIGN.md`.

| Screen | What it shows | Key elements |
|---|---|---|
| **F1 App inventory** | The app list: app, owner, annual spend, seats, renewal date, usage status (Connected / No usage data / In library) | Badge "Renews in 58 days"; button **Connect usage data** |
| **F2 Library check** | **In library:** "App X is in the platform library · checked by the platform team · used by 5+ customers · healthy" → token form. **Not in library:** "Build it with AI from the app's API docs" | Library connect still runs this customer's own test |
| **F3 Paste docs + progress** | A docs URL field or an OpenAPI upload. Live progress: Reading docs → Drafting → Checking evidence → Checking rules | Plain error if the docs can't be read: "Upload the OpenAPI file" |
| **F4 What we found** | Plain summary cards: **Login** (type, role, exact scopes), **Users** (where they come from), **Usage** (tier badge, definition, "proxy" label), **Limits**, **Warnings**. An evidence drawer with quotes and conflict chips | Buttons: **Looks right** / **This looks wrong** (add a hint) |
| **F5 Connect + test** | Token instructions and a scope checklist. Trust note: "Encrypted. Read-only. Never shared with the AI." A link to **Ask the app owner**. Then a live test checklist (Login ✓ Users ✓ Usage ✓ Mapping ✓) and a **Generated code** tab with the six items highlighted | Plain errors with the fix, e.g. "This token needs the Owner or Admin role and the scheduled_events:read scope" |
| **F6 Savings preview** | 48 users · 6 left the company (HRIS) · 11 hosted no meetings in 90 days (proxy) · 60 seats bought, 12 never assigned · **$6,960 a year recoverable before the renewal on 26 Dec**. Every number shows its source | Confirm → Go live. A mismatch with SSO over 2% needs a note |
| **F7 Connector detail** | Status, last sync, runs, versions with diff, token owner + offboarding warning, **Download data card** (for security review), Generated code | "Needs repair" with the proposed fix |
| **F8 Platform internal** | Library review queue (approve/reject), fleet health (used by N, failure rate, canary status), Opportunity Map (sample data) | Approve to library / approve repair |

---

## 8. Safeguards (Deliverable 2)

**Short answer:** Yes, test first, then go live. But "sandbox" here means the platform's isolated runner. It reads the customer's **real** data with read-only calls, because most SaaS vendors don't offer a test account. If the app does have one, the admin can point the test at it first, for example by entering the test account's subdomain.

**Lifecycle (the statuses used everywhere in the UI and the code)**

| Status | What runs | Used in platform reports? | Moves forward when |
|---|---|---|---|
| Draft | Nothing; spec only | No | Spec passes evidence + rule checks |
| Testing | Sandbox run: all users, sampled usage | Preview only | Test passes + cross-check OK + admin confirms |
| Needs help | Stopped after 3 failed repairs | No | The admin's hint or platform support fixes it |
| Live | Daily sandboxed sync | Yes | — |
| Live (users only) | Daily sync; usage blocked by permission or plan | Users yes; usage marked unavailable | A token with the right role/scope |
| Needs repair | Stopped (API change); last good data kept, marked stale | Stale only | A new version is tested, reviewed and approved |
| Reconnect needed | Token rejected | Stale only | A new token |
| Paused | The admin paused it | Stale only | The admin resumes it |

**The four risks that matter, and how we handle them**

| Risk | Safeguards |
|---|---|
| **1. Wrong data leads to wrong seat cuts** (the biggest risk for the customer) | Usage always labelled with what it measures ("Meetings hosted", not "Active"); T2 usage marked as a proxy; automatic cross-check with HRIS, SSO and contract data; the connector's own account excluded from "inactive"; the admin confirms before going live; **no automatic seat removal** in v1. Counter-metric: the false-inactive rate (§11) |
| **2. The connector token is misused or leaked** (the biggest risk for the platform) | Integration tokens are a proven attack path: stolen Salesloft Drift OAuth tokens were used against 700+ organisations' Salesforce data in Aug 2025 ([SecureWorld](https://www.secureworld.io/industry-news/salesloft-drift-breach-salesforce-data)). Safeguards: see the six steps listed just below this table |
| **3. Silent breakage when an app changes** | Drift detection (401/403 changes, 404/410, missing fields, auth changes like Zendesk's token retirement); versioned specs that need approval; last good data kept and marked stale; kill switch per connector |
| **4. One bad shared connector hurts many customers** | An engineer reviews before anything enters the library; each customer's own test always runs; repairs roll out to a canary group first, with automatic rollback; customer-specific values stripped; "used by N" shown only when N ≥ 5 |

**How risk 2 (the token) is handled:**
1. Ask for **exact scopes**, and flag full-access or old unscoped tokens.
2. Record the **token owner**. Warn before that person is offboarded, using HRIS data, and recommend a service account.
3. Keep tokens in an **encrypted vault with a separate key per customer**. A token is used only inside a sandbox run, and never appears in logs or AI prompts.
4. **Read operations only**, and the network is locked to the app's own host.
5. **Publish static egress IPs**, so customers can restrict the token to the platform's IP addresses. Alert when call volume is far above normal.
6. **One-click revoke** and an audit log. Each connector token is listed as a non-human identity in the platform's identity views.

**Also covered:**
- **Prompt injection.** Docs are treated as untrusted input. The LLM only outputs a schema-bound spec, never holds a token, and the host rule blocks calls to anywhere else.
- **The docs fetcher can't be used to reach internal systems (SSRF).** It only fetches http(s) URLs. It blocks private, loopback, link-local and cloud-metadata addresses, checks again after every redirect, and runs in its own sandbox.
- **Minimal personal data.** Only the canonical user fields are stored. Raw API responses are never stored. User records are deleted 30 days after a connector is removed.
- **Scrubbed admin hints.** Hints are scrubbed before they reach the LLM (§6.2).
- **Rate limits.** Paging stays below the documented rate limits. When the docs don't state one, we pace at 60 requests per minute.
- **AI provider data use.** We use the Gemini API's **paid tier**: Google's pricing page says free-tier content is "used to improve our products" and paid-tier content is not ([Gemini pricing](https://ai.google.dev/gemini-api/docs/pricing)).
- **Vendor API terms** are checked before a connector is published to the library.

**Rule on "read only":** the check is on the *operation*, not just the HTTP method. v1 allows GET, and POST only to get a login token. Later, POST search endpoints and GraphQL *queries* are allowed only when the docs say they are read-only and a reviewer approves.

---

## 9. AI model (Deliverable 3)

**Answer:** Google Gemini, through the Gemini API (paid tier).

| Job | Model | Why |
|---|---|---|
| Draft the spec; repair tries 1–2 | `gemini-3.8-flash` (stable) | Fast and low-cost; JSON-Schema-constrained output |
| Repair try 3 (the last); very large or messy docs | `gemini-4-argon` (stable, Google's flagship reasoning model, 1,048,576-token context) | Strongest reasoning for the hardest step |

Both sit behind an `LLMClient` interface, so changing the model or the provider (for example Claude or OpenAI) is a config change.

**Why Gemini fits this job:**
1. **Long context.** A whole API reference fits in one request.
2. **Structured output.** It returns JSON constrained to a JSON Schema, which is exactly what a spec needs ([structured output](https://ai.google.dev/gemini-api/docs/structured-output)). It doesn't enforce some schema keywords (`minLength`, `maxLength`, `uniqueItems` and similar), so we validate the full schema in our own code anyway.
3. **Cost.** Below $1 per connector (table below).
4. **Data use.** On the paid tier, prompts are not used to improve Google's products. The model only ever sees public docs and masked samples. For production, the same models are available through Google Cloud Vertex AI on enterprise terms, subject to the company's approved-provider list (§14).

**Cost per new connector** (about 90k input + 10k output tokens; list prices on 29 Oct 2026 from [Gemini pricing](https://ai.google.dev/gemini-api/docs/pricing)):

| Model | $ per 1M input / output | ≈ $ per connector | Scheduled price change |
|---|---|---|---|
| `gemini-3.5-flash-lite` | $0.30 / $2.50 | $0.05 | — |
| `gemini-3.8-flash` | $0.75 / $3.75 | $0.11 | $1.50 / $7.50 from 1 Jan 2027 (≈ $0.21) |
| `gemini-4-argon` | $2.00 / $10.00 | $0.28 | $4.00 / $20.00 from 1 Dec 2026 (≈ $0.56) |

The model cost is tiny next to 30–60 minutes of engineer review. So **we choose on pass rate and repairs, not price.** Library reuse costs zero AI tokens.

**Chosen by measurement, not opinion.** The prototype runs a benchmark: 3 apps (Zendesk, Calendly, Notion) × 3 models (`gemini-3.5-flash-lite`, `gemini-3.8-flash`, `gemini-4-argon`) × 3 runs = **27 drafts**. Each draft is scored on:
- spec valid;
- evidence quotes verified;
- sandbox test passes;
- user count matches the app's admin screen;
- repairs needed;
- real $ and seconds.

The full eval (metrics, targets, method) is in `EVAL.md` §2. The headline slide is one line: "We use X: N/9 passed, R repairs, $Y per connector." The defaults above change if the benchmark says so.

**Before production:** a 30-app backtest (10 per tier) against the platform's native connectors, plus one non-Gemini model for comparison.

---

## 10. Business case

All numbers below are **assumptions to replace with the company's real data**. The logic matters more than the figures.

**For the platform.** This frees the integrations team to deepen the top connectors; the long tail becomes net-new coverage.

| | Hand-built connector | AI-built (library) |
|---|---|---|
| Build | 5–10 engineer-days (assumption) | ≈ $0.10–0.60 of model cost + 30–60 min engineer review |
| Upkeep per year | 2–4 engineer-days (assumption) | Review only when a repair is proposed |
| 200 new long-tail apps per year | 1,000–2,000 engineer-days | ≈ 100–200 engineer-hours of review |
| Cost to build the feature | — | ≈ 2 engineers + 1 PM for 1 quarter to reach beta (assumption) |

**For the customer (value unlocked, net of what SSO already shows)**
- The company says "customers typically save 10–30% on SaaS spend" (company website).
- **Illustration:**
  - A customer has **40 apps** with no connector-level usage. Assume **half** already have SSO login data, so about **20 apps are truly dark**.
  - Value: 20 × **$10k/yr** average spend × **10–30%** recoverable = **$20k–$60k/yr** newly visible.
  - On the 20 SSO-covered apps, the connector improves accuracy (real use instead of logins) but adds less new value.
- **Honest caveat:** Zylo reports that its direct integrations cover about 20% of apps but about 80% of spend ([Zylo](https://zylo.com/blog/does-zylo-work-with-your-tech-stack)). Each long-tail app is small, so the value comes from **breadth and renewal timing**, not from any single app.

**Strategic value:** coverage is a selling point in evaluations. "We cover the long tail with real usage, and every connector is checked" answers competitors who ship AI builders without the cross-check.

---

## 11. Success metrics

| Metric | Definition | Proposed target (beta) |
|---|---|---|
| **North star: spend coverage** | % of a customer's SaaS spend with seat-level usage data | Baseline measured at beta start; +15 points within 2 quarters |
| Builder success | % of new builds where the test passes and the admin confirms (T1/T2) | ≥ 70% |
| Time to first data | Median minutes from click to savings preview | Library connect ≤ 2 min; new build ≤ 10 min |
| Library reuse | Average customers per library connector | ≥ 5 after 2 quarters |
| Count accuracy | Confirmed connectors whose billable-user count is within 2% of the SSO-assigned count (or the app's admin screen) | ≥ 95% |
| **False-inactive rate (counter-metric)** | % of users flagged inactive that the admin marks "actually uses it", or that are restored within 30 days | ≤ 5% |
| Sync failure | % of live connectors failing a scheduled run in a week | ≤ 3% |
| Repair safety | % of fleet repairs rolled back after the canary | Tracked; ≤ 10% |
| Token hygiene | % of connectors using scoped tokens or service accounts | ≥ 80% |
| Renewals with usage data | % of renewals negotiated with seat-level usage | Up vs baseline |
| Savings found | $ of unused seats flagged on AI-built connectors | Tracked per customer |

**Before launch:** a backtest on apps the platform already supports, shown as a scoreboard (e.g. "user counts matched on 26/30 apps").

---

## 12. Pricing and rollout stance

- **Bundle it in the platform.** It protects the savings story that drives renewals. Cap new custom builds per plan; library connectors are unlimited. No contribution credits in v1: opt-in sharing is acknowledged but not paid for, to keep the legal side simple.
- **Internal first (decided).** The platform's integrations team uses the builder first, picking apps from the Opportunity Map. Then self-serve opens to design partners.

---

## 13. Roadmap (each phase starts when its gate is met)

| Phase | What | Gate to move on |
|---|---|---|
| 0 Prototype | Generic engine; Zendesk, Calendly, Notion + a surprise app; library with review; savings preview; 27-draft model benchmark | Counts match the admin screens on all 3 apps; security tests pass; benchmark done |
| 1 Internal build team | Builds long-tail connectors from the Opportunity Map; 30-app backtest; final model choice; data cards | Backtest score agreed with the company |
| 2 Customer beta | Self-serve for library + new builds (T1–T3); renewal trigger; fleet health; token governance | Beta targets in §11 met; customer security reviews signed off |
| 3 GA | Platform-registered OAuth apps (Slack etc.); POST-search and GraphQL reads with review; one-call-per-user usage; bulk OpenAPI import; connector data through the platform's MCP server | Read-only data trusted across customers |
| 4 Beyond read | Remove or downgrade seats with approvals; feature-level usage; apps with no API via browser automation | — |

---

## 14. Risks and open questions

| Risk | Mitigation |
|---|---|
| Wrong usage definition → wrong cuts | Labels, proxy flag, cross-check, false-inactive counter-metric, no automatic removal |
| Token breach through the platform | Exact scopes, per-customer keys, egress IPs, anomaly alerts, revoke, token owner tracking (§8) |
| A shared spec is wrong for some customers (plan differences) | The spec records plan and role needs; each customer's own test always runs; canary repairs; failures show in the fleet view |
| Legal/consent issues with sharing customer-built connectors | The library is built by the platform team from public docs; customer builds stay private; opt-in only, rebuilt from public docs |
| Bad or JavaScript-only docs | OpenAPI first; headless browser; file upload; the platform team as fallback |
| Vendors change auth (e.g. Zendesk retiring API tokens) | Auth changes count as drift; the spec is versioned; the admin is told in plain words |
| Competitors already have AI builders and catalogs | Win on usage depth, cross-check, renewals and token governance; move fast on Opportunity Map apps |

**Open questions for the company**
- [ ] Is opt-in sharing of customer-built connectors acceptable (terms of service, consent)?
- [ ] What is the platform's real canonical user/license schema (so `TRD.md` §5 matches it)?
- [ ] Is Gemini (Gemini API or Vertex AI) an approved LLM provider? Any data-residency rules?
- [ ] Who owns support for customer-built connectors?
- [ ] Can the company share user counts from its native Zendesk, Calendly and Notion connectors for the backtest?
- [ ] Do any vendors' API terms limit sharing connector specs?

**Validation still to do (before the panel):** 3–5 short conversations with IT, procurement and security buyers. Questions:
- "Would you paste an admin token into an AI-built connector? What would your security team need?"
- "How do you define 'inactive'?"

Their answers replace the assumptions above.

---

## 15. 5-minute demo script

**Setup.** Two demo tenants:
- **Acme** runs on **demo data**: recorded API responses for a fake 48-person company, clearly labelled on screen. This gives realistic savings numbers.
- **Globex** runs **live** on a real Calendly account, which proves the code works on the real API.

In these demo tenants Calendly has no connector yet. (The platform does have a native one; we use Calendly because it is the assignment's example, and the native connector is our answer key.)

| Time | Beat |
|---|---|
| 0:00–0:30 | **Acme inventory:** Calendly shows its spend, "Renews in 58 days" and "No usage data". Click **Connect usage data**. Not in the library, so **Build with AI** |
| 0:30–1:30 | Paste the Calendly docs link. The AI fills the spec live. **What we found:** T2, Owner/Admin + 3 scopes, usage = meetings hosted (90 days, proxy). Open the evidence drawer and show the rate-limit conflict chip |
| 1:30–2:15 | Paste the token. Open the **Generated code** tab and point to the six items. The test passes |
| 2:15–3:00 | **Savings preview:** 48 users · 6 left · 11 inactive · 12 seats never assigned · **$6,960/yr before 26 Dec**. Confirm → Live |
| 3:00–3:45 | Submit to library → switch to the **platform internal** view → approve → switch to **Globex** (live). Calendly shows "In library". Paste Globex's own token; its own test runs; live with real data |
| 3:45–4:30 | **Surprise app:** paste the docs of an app the builder has never seen → spec drafted → test |
| 4:30–5:00 | **Safety and model:** a blocked prompt-injection doc and a blocked DELETE call, then the benchmark table ("We use X: N/9 passed, $Y per connector") |

**Backup:** a 3-minute recorded video of the same run.

---

## Sources

Opened or checked on 29 Oct 2026. API paths should be re-checked against vendor docs at build time.

- **The platform:** its public website, blog, integration pages and press page (not linked, to keep this repo company-neutral)
- **Competitors and adjacent:**
  - [Torii Integration Builder](https://support.toriihq.com/hc/en-us/articles/48261770863771-Integration-Builder-Build-Your-Own-Integration)
  - Lumos: [integrations](https://www.lumos.com/integrations), [blog](https://www.lumos.com/blog/how-we-use-ai-to-build-integrations)
  - [Josys AI-Powered Integration Builder](https://www.josys.com/features/ai-powered-integration-builder)
  - [BetterCloud shared integrations](https://www.bettercloud.com/releasenote/09-25-19/)
  - Zluri: [SDK](https://developers.zluri.com/docs/custom-integrations), [AI integrations](https://help.zluri.com/docs/ai-powered-integrations), [Calendly data processing](https://help.zluri.com/docs/calendly-data-processing)
  - [1Password SaaS Manager: Calendly](https://support.1password.com/saas-manager-calendly/)
  - [ServiceNow SAM: Calendly](https://www.servicenow.com/docs/r/it-asset-management/saas-license-management/integrate-with-calendly.html)
  - [Zylo](https://zylo.com/blog/does-zylo-work-with-your-tech-stack)
  - [Airbyte AI Assist](https://docs.airbyte.com/platform/connector-development/connector-builder-ui/ai-assist)
  - Fivetran AI Connector Agent: [setup](https://fivetran.com/docs/connectors/ai-connector-agent/setup-guide), [blog](https://www.fivetran.com/blog/ai-can-build-your-data-connector-heres-what-it-cant-do)
  - [Nango](https://github.com/nangohq/nango)
- **Calendly:**
  - [Rate limits](https://developer.calendly.com/api-docs/overview/rate-limits)
  - [OpenAPI spec](https://calendly.stoplight.io/api/v1/projects/calendly/api-docs/nodes/reference%2Fcalendly-api%2Fopenapi.yaml)
  - [Scopes](https://developer.calendly.com/docs/authentication/scopes)
  - [Personal access tokens](https://developer.calendly.com/personal-access-tokens)
  - [MCP server](https://developer.calendly.com/calendly-mcp-server)
  - [API overview (activity log plan)](https://calendly.com/help/calendly-api-overview)
- **Zendesk:**
  - [Users API](https://developer.zendesk.com/api-reference/ticketing/users/users/)
  - [Pagination](https://developer.zendesk.com/api-reference/introduction/pagination/)
  - [Rate limits](https://developer.zendesk.com/api-reference/introduction/rate-limits/)
  - [API token removal](https://support.zendesk.com/hc/en-us/articles/10851263566234)
  - [OAuth migration](https://developer.zendesk.com/documentation/authentication/oauth-migration/)
- **Notion:**
  - [List users](https://developers.notion.com/reference/get-users)
  - [Capabilities](https://developers.notion.com/reference/capabilities)
  - [Versioning](https://developers.notion.com/reference/versioning)
  - [Request limits](https://developers.notion.com/reference/request-limits)
- **Zoom:**
  - [Users API](https://developers.zoom.us/docs/api/users/)
  - [Server-to-Server OAuth](https://developers.zoom.us/blog/why-use-server-to-server-oauth.md)
- **GitHub:** [Copilot activity data](https://docs.github.com/copilot/managing-copilot/managing-github-copilot-in-your-organization/reviewing-activity-related-to-github-copilot-in-your-organization/reviewing-user-activity-data-for-copilot-in-your-organization)
- **Atlassian:**
  - [JRACLOUD-97537](https://jira.atlassian.com/browse/JRACLOUD-97537)
  - [Last-active dates endpoint](https://developer.atlassian.com/cloud/admin/organization/user-last-active-dates)
- **Asana:** [Audit log events](https://developers.asana.com/docs/audit-log-events)
- **HubSpot:** [Account activity API](https://developers.hubspot.com/docs/api-reference/latest/account/audit-logs/guide)
- **Gemini:**
  - [Models](https://ai.google.dev/gemini-api/docs/models)
  - [Pricing](https://ai.google.dev/gemini-api/docs/pricing)
  - [API key](https://ai.google.dev/gemini-api/docs/api-key)
  - [Structured output](https://ai.google.dev/gemini-api/docs/structured-output)
  - [Gemini 4 Argon](https://ai.google.dev/gemini-api/docs/models/gemini-4-argon)
- **Research and incidents:**
  - [WAPIIBench: LLM API hallucinations](https://arxiv.org/abs/2509.20172)
  - [Salesloft Drift breach](https://www.secureworld.io/industry-news/salesloft-drift-breach-salesforce-data)
  - [Gainsight incident](https://www.techradar.com/pro/security/google-security-experts-say-gainsight-hacks-may-have-left-hundreds-of-companies-affected)
