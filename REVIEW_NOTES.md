# Review notes: AI-Generated Integration Builder

29 Oct 2026. Two independent reviewers checked PRD v1 against the assignment:

1. **Coverage reviewer:** does the PRD cover every line of the assignment, and can an AI coder build from it?
2. **CPO reviewer:** reads it as the company's Chief Product Officer. What is generic, what stands out, what is missing?

`PRD.md` (v2) fixes everything marked **Fixed** below. Items marked **Open** need Sujeet or the company.

---

## 1. The most important correction

**v1 said no SaaS-management tool uses AI to build connectors. That was wrong.**
- Torii's Integration Builder has **"Build with AI"**. It takes a docs link, pasted docs or hints. In about 1–5 minutes it drafts auth, the users endpoint with paging, field mappings (incl. last visit time), and status and license rules. A test call refines the draft.
- Source: [Torii help article](https://support.toriihq.com/hc/en-us/articles/48261770863771-Integration-Builder-Build-Your-Own-Integration). Checked directly.

**What this means:** "AI builds a connector from docs" is table stakes, not a moat. v2 makes the edge come from what the company has and a per-customer builder doesn't:

1. **Shared library:** build once, every customer connects with their own token.
2. **Automatic cross-check** with HRIS, SSO and contract seat counts.
3. **Starts from inventory and renewals**, not a separate integrations page.
4. **Fleet self-healing:** one repair fixes the connector for every customer.
5. **Roles/admin flags** for access reviews (security buyer).

---

## 2. Coverage reviewer: findings and status

| # | Finding | Status in v2 |
|---|---|---|
| 1 | Figma not delivered, only described | **Partly fixed.** §7 now has 7 named frames with content. **Open:** the frames still need to be drawn (Claude Code can build them as clickable HTML screens; then recreate or import into Figma) |
| 2 | Prototype not delivered, only planned | **Open.** Build it with Claude Code using Appendix A |
| 3 | Answers buried in a 760-line doc | **Fixed.** §0 is a one-page answer to all 3 deliverables |
| 4 | Model choice weak; "drafted with Claude" aside undercut it | **Fixed.** §9: 3 reasons, ~100k tokens per connector, benchmark plan vs one OpenAI and one Google model. Aside removed |
| 5 | Calendly (the assignment's own example) under-specified | **Fixed.** Full Calendly spec in A4, checked against Calendly's OpenAPI and rate-limit page |
| 6 | Test cap (5 pages) broke the count check | **Fixed.** Test mode reads all users (warn at 50 pages); only usage is sampled and labelled "sample" |
| 7 | AI coder missing contracts | **Fixed.** Placeholder syntax, field_map rules, runner stdin/stdout/exit codes, JSON Patch repair format, env vars, SSE events, accounts needed |
| 8 | No license / seat field | **Fixed.** Added `license_type`, `is_billable`, `is_admin`, `usage_is_proxy` |
| 9 | Too much marked MUST | **Fixed.** A1 has a tight MUST list; OAuth refresh, email alerts and roles moved to LATER |
| 10 | No targets, no ROI | **Fixed.** §10 business case (assumptions labelled), §11 proposed targets + north star |
| — | Calendly rate limit wrong | **Fixed.** 500/user/min paid, 50 free; uses `X-RateLimit-*` headers (no `Retry-After` documented) |
| — | Calendly 403 was on the wrong call | **Fixed.** The 403 comes from `/scheduled_events?organization=` (Owner/Admin needed), not from the members list |
| — | Slack listed as both T2 and T4 | **Fixed.** Slack is T4 (needs a platform-registered OAuth app) |
| — | Atlassian used as a live T1 example | **Fixed.** Now past tense, used as the drift example |
| — | Sandbox via proxy can be bypassed | **Fixed.** Docker with internal network + egress proxy; subprocess fallback labelled "demo isolation only" |
| — | Timeouts contradicted (120 s vs 30 min) | **Fixed.** Test 120 s, full sync 30 min |
| — | "Sandbox" wording hid that test runs read real data | **Fixed.** §8 says plainly: read-only calls against real data |
| — | "Edit and retry" undefined | **Fixed.** Replaced by "Add a hint" (plain text to the AI); no code editing in UI |
| — | Diagrams "broken" | Not a real issue: they show in the online doc, they just don't export to markdown. v2 uses tables instead |

---

## 3. CPO reviewer: findings and status

| Finding | Status |
|---|---|
| Most of v1 is what every AI-assisted submission will have (generic flow, safeguards list, wizard screens, boilerplate runtime rules) | **Fixed.** Part 1 now leads with the factory/library stance, cross-check, competitive table, ROI. Build detail moved to Appendix A |
| Strong parts worth keeping: usage tiers, trap table, "AI decides, templates write", evidence quotes, AI never sees tokens, backtest on existing connectors, internal-first rollout | **Kept** and moved higher |
| Reframe the premise: the risk is wrong data → wrong seat cuts, not code breaking prod | **Fixed.** Top of §0 and §8 |
| "GET-only" is naive (GraphQL, POST search) | **Fixed.** Rule is now "read operations only", checked per operation; v1 GET only, POST search/GraphQL reads later with review |
| Missing demo moment | **Fixed.** §15: savings reveal + second tenant connects from library in 30 s |
| Missing pricing / rollout stance | **Fixed.** §12 |
| Cut length for the panel | **Partly.** Part 1 is now ~6 pages; Appendix A stays because the AI coder needs it. **Open:** for the panel, share §0–§15 only (or export Part 1 as PDF) |

---

## 4. Open items (need Sujeet or the company)

- [ ] **Figma (Deliverable 1):** draw F1–F7. Fastest path: ask Claude Code to build the screens as part of the prototype frontend, take screenshots, then recreate in Figma (or use a Figma plugin that imports HTML).
- [ ] **Prototype (Deliverable 3):** build with Claude Code from Appendix A. Record a 3–5 minute demo video as backup.
- [ ] **Accounts:** Anthropic API key; Calendly (ideally a Teams org with 2+ users; free works for basics); Zendesk trial; Notion workspace + internal integration.
- [ ] **Backtest scoreboard:** run the builder on ~10 apps with known answers. Report honestly, e.g. "8/10".
- [ ] **Your call:** whether to add one line saying you used AI tools for research and drafting. Many panels respect this when the judgment is clearly yours.
- [ ] **Assumptions to replace if the company shares data:** engineer-days per connector, long-tail app count, average spend per app.
- [ ] Ask the company the open questions in PRD §14 (sharing specs across customers, approved LLM providers, support ownership).
