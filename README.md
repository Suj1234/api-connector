# AI-Generated Integration Builder

A generic builder that turns any SaaS app's public API docs into a tested, read-only connector for users and usage data. AI fills a structured connector spec, with a docs quote as proof for every answer. Fixed templates write the code. A sandbox tests it, and a cross-check with HR, SSO and contract data shows the savings before anything goes live.

**Live prototype:** https://integration-builder-five.vercel.app (login by invite). It runs on a sample company with fake people; add an app, such as Calendly, from its API docs and follow it through to its users.

## Read in this order

| # | File | What it answers |
|---|---|---|
| 1 | [`PRD.md`](PRD.md) | **What and why.** The problem, the customer, the approach, what's built today, safeguards, the AI model choice, metrics and the roadmap. Start with §0, the one-page answer to the assignment. |
| 2 | [`TRD.md`](TRD.md) | **How it is built.** Architecture, stack and deployment, the connector spec format, the engine, the AI pipeline, API, tables and savings math. |
| 3 | [`DESIGN.md`](DESIGN.md) | **How it looks.** Colours, type, components, writing rules and the screen layouts. |
| 4 | [`EVAL.md`](EVAL.md) | **How we know it works.** The test approach, the AI model benchmark, acceptance scenarios and results. |
| 5 | [`prototype/`](prototype/README.md) | **The code.** How to run it, test it and deploy it. |

## The idea in one line

**AI decides, templates write.** The AI only fills a small, checkable spec; it never writes code that runs. Every connector makes read calls only, to the app's own host only, and is tested before going live.
