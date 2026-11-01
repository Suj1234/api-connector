# Model benchmark results

27 drafts. Test runs use replay recordings (EVAL §2.2). Cost from benchmark/prices.json.

| Model | Schema valid | Evidence verified | Test pass | User count match | Usage match | Avg repairs | Avg $ | Avg s |
|---|---|---|---|---|---|---|---|---|
| `gemini-3.5-flash-lite` | 8/9 | 72% | 2/9 | 2/9 | 3/9 | 2.0 | 0.117 | 42 |
| `gemini-3.8-flash` | 9/9 | 100% | 7/9 | 4/9 | 3/9 | 0.7 | 0.133 | 46 |
| `gemini-4-argon` | 9/9 | 100% | 9/9 | 9/9 | 3/9 | 0.0 | 0.232 | 50 |

**We use `gemini-4-argon`: 9/9 passed, 0.0 repairs on average, $0.23 per connector.**

Failures:
- calendly / gemini-3.5-flash-lite / run 2: RULES_REJECTED
- zendesk / gemini-3.5-flash-lite / run 1: WRONG_REQUEST
- zendesk / gemini-3.5-flash-lite / run 2: WRONG_REQUEST
- zendesk / gemini-3.5-flash-lite / run 3: WRONG_REQUEST
- zendesk / gemini-3.8-flash / run 1: WRONG_REQUEST
- zendesk / gemini-3.8-flash / run 2: WRONG_REQUEST
- notion / gemini-3.5-flash-lite / run 1: WRONG_REQUEST
- notion / gemini-3.5-flash-lite / run 2: WRONG_REQUEST
- notion / gemini-3.5-flash-lite / run 3: WRONG_REQUEST
