# AI-Generated Integration Builder

A generic builder that turns any SaaS app's public API docs into a tested, read-only connector for users and usage data. AI fills a structured connector spec, with a docs quote as proof for every field. Fixed templates write the code. A locked sandbox tests it, and a cross-check with HR, SSO and contract data shows the savings before anything goes live.

## Read in this order

| # | File | What it answers |
|---|---|---|
| 1 | [`PRD.md`](PRD.md) | **What and why.** The problem, the customer, the approach, safeguards, the AI model choice, metrics and the 5-minute demo. Start with §0, the one-page answer to the assignment. |
| 2 | [`TRD.md`](TRD.md) | **How it is built.** Connector spec format, engine, sandbox, AI pipeline, API, tables and savings math. |
| 3 | [`DESIGN.md`](DESIGN.md) | **How it looks.** Colours, type, components, writing rules and layouts for screens F1–F8. |
| 4 | [`EVAL.md`](EVAL.md) | **How we know it works.** The AI quality benchmark, acceptance scenarios, security tests and test plan. |
| 5 | [`prototype/`](prototype/README.md) | **The working prototype.** Run steps, the demo click-path and the tests. |

## The idea in one line

**AI decides, templates write.** The AI only fills a small, checkable spec; it never writes code that runs. Every connector makes read calls only, to the app's own host only, and is tested on the customer's own data before going live.
