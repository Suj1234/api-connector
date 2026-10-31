# AI-Generated Integration Builder — DESIGN

**For:** Senior PM take-home assignment
**Author:** Sujeet Kumar
**Date:** 29 Oct 2026
**Status:** v1. The design system for the prototype's screens (F1–F8, `PRD.md` §7). The frontend uses these tokens and nothing else.

---

## 1. Principles

The people using this screen are IT admins, procurement and security reviewers. They are deciding whether to trust a connector with an admin token and whether to cut seats. The design has to feel **calm, exact and trustworthy**, like an admin console, not like a marketing page.

1. **Dense and white.** Lots of information, little decoration. White surfaces, cool greys, thin borders.
2. **Colour has a job.** Navy means "you can act on this". Tinted badges mean "this is the state of something". Nothing else gets colour.
3. **Every number shows its source.** "48 users · from Calendly API". "6 left the company · from HRIS". Usage always says what it measures ("Meetings hosted, 90 days · proxy").
4. **Plain words first, detail on demand.** Summary cards up front; evidence, logs and code behind a drawer, a tab or a toggle.
5. **Nothing decorative.** No gradients, no glows, no glass, no illustrations, no emoji, no sparkle icons for "AI". The AI is shown by what it found and the quotes that prove it, not by effects.

---

## 2. Colour

### 2.1 Core palette

| Token | Hex | Use |
|---|---|---|
| `--primary` | `#0A2540` | Primary button, checked controls, active step, selected tab underline, active nav item |
| `--primary-hover` | `#1B3A5C` | Primary button hover |
| `--primary-pressed` | `#061A2E` | Primary button pressed |
| `--primary-subtle` | `#E9EEF4` | Selected row, active nav background, selected choice card |
| `--focus-ring` | `#7A9CC6` | 2px focus outline on every interactive element |
| `--link` | `#0055BC` | Text links, "View evidence", "Open docs" |

### 2.2 Neutrals

| Token | Hex | Use |
|---|---|---|
| `--surface` | `#FFFFFF` | Page, cards, tables, modals, drawers |
| `--surface-subdued` | `#F6F8FA` | Side panels, table header, search field, code background |
| `--border` | `#EBEEF1` | Dividers, card outlines, table rows |
| `--border-strong` | `#C0C8D2` | Input borders, the rule under section titles |
| `--text-heading` | `#21252C` | Page titles, section headings |
| `--text` | `#353A44` | Body text |
| `--text-subdued` | `#545969` | Field labels, table headers |
| `--text-muted` | `#687385` | Timestamps, help text, sources ("from HRIS") |
| `--text-placeholder` | `#A3ACBA` | Placeholders, the em dash for empty values |

### 2.3 Status colours (always as a tinted badge with a word)

| Tone | Background | Text / icon | Used for |
|---|---|---|---|
| Success | `#D1FAB3` | `#217005` | Live, test passed, evidence verified |
| Danger | `#FFE8EE` | `#B3093C` | Needs repair, Reconnect needed, blocked call, left the company |
| Warning | `#FEF8CA` | `#8A4B00` | Needs help, Live (users only), count mismatch, token owner leaving |
| Info | `#CFF4FC` | `#0055BC` | Testing, In library, conflict chip |
| Neutral | `#EBEEF1` | `#414552` | Draft, Paused, tier badges (T1, T2, T3), "proxy" tag |

Destructive buttons (Delete connector, Revoke token) use `--danger: #DF1B41` as the fill.

### 2.4 Sample data

Replay mode must never be mistaken for real data (`TRD.md` §1), but it should not shout either. A neutral `Tag` reading "Sample data" sits beside the tenant switcher on every screen of a replay-mode tenant, and beside the numbers it affects (savings, connector detail). No extra colour.

### 2.5 Charts (savings preview, F6)

| Bucket (`TRD.md` §11) | Colour |
|---|---|
| Left the company | `#DF1B41` |
| Inactive | `#EE6902` |
| Never assigned | `#87909F` |
| Not in HR data | `#0055BC` |
| Active | `#2A9B0E` |
| Excluded (connector's own account) | `#D5DBE1` |

Each bar segment has a text label and a count beside it; colour is never the only signal.

---

## 3. Type

**Font:** IBM Plex Sans for everything, IBM Plex Mono for code, IDs, paths and JSON. Both from Google Fonts. Fallback: the system UI font. Numbers use tabular figures so columns line up.

| Style | Size / line height | Weight | Use |
|---|---|---|---|
| `title` | 28 / 36 | 600 | Page title ("Calendly", "App inventory") |
| `heading` | 20 / 28 | 600 | Section heading inside a page |
| `heading-sm` | 16 / 24 | 600 | Card titles, modal and drawer titles |
| `body` | 14 / 20 | 400 | Almost everything |
| `body-strong` | 14 / 20 | 500 | Labels, nav items, table cell emphasis |
| `caption` | 12 / 16 | 400 | Help text, timestamps, sources |
| `overline` | 11 / 16, uppercase, 0.06em tracking | 600 | Small eyebrows above a title ("CONNECTOR") |
| `metric` | 28 / 36, tabular | 600 | Big numbers in the savings preview |
| `code` | 13 / 20 | 400 | Generated code, run log, evidence pointers |

---

## 4. Spacing, size and shape

- **4px grid.** `--space-1` 4, `--space-2` 8, `--space-3` 12, `--space-4` 16, `--space-6` 24, `--space-8` 32, `--space-12` 48.
- **Radius:** `--radius-sm` 6px for inputs and buttons, `--radius-md` 8px for cards, drawers and modals. Badges are 4px. Nothing is fully rounded except avatars.
- **Shadow:** only on things that float (menus, modals, drawers, toasts): `0 4px 16px rgba(10, 37, 64, 0.12)`. Cards use a border, not a shadow.
- **Controls:** 32px tall (buttons, inputs, selects); 28px for small buttons in tables.

---

## 5. Layout

| Part | Size |
|---|---|
| Sidebar | 240px, white, right border |
| Top bar | 56px: tenant switcher on the left, search in the middle, help on the right |
| Page gutters | 24px |
| Content max width | 1200px |
| Forms | One column, 480px max, fields 16px apart |
| Detail pages | Content on the left, a 280px "Details" rail on the right |

**Sidebar items:** App inventory, Library, Connectors, Savings. In the `internal` tenant: Review queue, Fleet health, Opportunity map.

**Tenant switcher:** always visible, top left. Shows the tenant name, with a "Sample data" tag beside it in replay mode.

---

## 6. Components

The prototype builds only what the screens need.

| Component | What it is | Where it appears |
|---|---|---|
| `AppShell` | Sidebar + top bar + page area | Every screen |
| `PageHeader` | Overline, title, status badge, actions on the right | Every screen |
| `Button` | `primary` (navy), `secondary` (white, border), `ghost`, `danger` | Everywhere; **one primary per view**, right-most |
| `Badge` | Tinted status with a word, optional icon | Connector status, tiers, test results |
| `Tag` | Small neutral label | "proxy", "sample", "from SSO" |
| `Card` | Bordered white block with a title | F4 summary cards, F6 metrics |
| `Metric` | Label, big number, source line | F6 savings preview |
| `Table` | Sortable columns, row hover, em dash for empty cells | F1 inventory, F2 library, F8 review queue |
| `Tabs` | Text tabs, navy underline on the selected one; optional count | F5 (Test / Generated code), F7 |
| `Stepper` | Vertical steps with live status: waiting, running, done, failed | F3 progress (Reading docs → Drafting → Checking evidence → Checking rules) |
| `Checklist` | Test results: Login ✓ Users ✓ Usage ✓ Mapping ✓, each with a plain message | F5 test run |
| `CodeBlock` | Mono, line numbers, copy button; the six assignment items highlighted with a side marker and label | F5 / F7 Generated code tab |
| `RunLog` | Request rows: method, path, status badge, ms, retry; never bodies or tokens | F5 / F7 run details |
| `EvidenceDrawer` | Right-side drawer: each field, its value, the docs quote, the link, and a "verified" badge | F4 |
| `ConflictChip` | Info chip: "2 sources disagree" → opens both values and the chosen source | F4 evidence drawer |
| `Banner` | Full-width message with tone and an action | Warnings, partial results, token owner leaving |
| `BreakdownBar` | One stacked bar with labelled segments and counts | F6 seat buckets |
| `DetailsList` | Label / value pairs in the right rail | F7 connector detail |
| `Field` | Label + input + help text + error text | All forms |
| `TextInput`, `Select`, `FileUpload`, `Textarea` | Standard inputs; secret inputs are masked and write-only | F3 docs URL / OpenAPI upload, F5 token, hints |
| `Modal` | 1–3 fields or a confirmation | "This looks wrong" hint, confirm go-live |
| `Drawer` | One object in detail | Evidence, run log |
| `Toast` | Short past-tense confirmation | "Connector is live", "Submitted for review" |
| `EmptyState` | One line of what's missing + one action | "No connectors yet", "Upload HR/SSO data to see who left" |
| `Tooltip` | Short definition on hover or focus | Tier meanings, "proxy", sources |
| `Spinner` | Small inline loader | Buttons while saving |

### 6.1 Connector status → badge

The statuses come from `PRD.md` §8. Every screen uses the same mapping.

| Status | Tone |
|---|---|
| Draft | Neutral |
| Testing | Info |
| Needs help | Warning |
| Live | Success |
| Live (users only) | Warning |
| Needs repair | Danger |
| Reconnect needed | Danger |
| Paused | Neutral |
| In library (F1/F2) | Info |
| No usage data (F1) | Neutral |

### 6.2 Icons

One line-icon set (1.5px stroke, 16px and 20px). Only for actions and status: check, x, alert, info, lock, external link, copy, code, doc, clock, refresh, upload, search, settings, chevrons. No "magic" or sparkle icons.

---

## 7. Writing rules

- **Sentence case** for titles, buttons, tabs and column headers ("Connect usage data", "Generated code"). Uppercase only in overlines.
- **Buttons start with a verb and name the thing:** "Connect usage data", "Paste token", "Run test", "Submit to library", "Approve to library". The confirm button repeats what will happen ("Go live with users only").
- **Talk to the admin as "you"**: "Your token is encrypted and never shared with the AI."
- **Errors say what to fix**, using the plain messages in `TRD.md` §7: "This token needs the Owner or Admin role and the scheduled_events:read scope."
- **Confirmations are past tense and specific**: "Calendly is live", "Submitted to the platform library for review".
- **Every number has a source**: "from Calendly API", "from HRIS", "from SSO", "from contract".
- **Usage says what it measures**, never just "active": "Meetings hosted (90 days) · proxy", "Last login · from SSO, not from the app".
- **Money:** "$6,960 / yr". **Dates:** "26 Dec 2026"; in tables "26 Dec". **Relative time:** "Renews in 58 days".
- **Empty values** are an em dash (—), never blank or "N/A".
- No emoji. No exclamation marks.

---

## 8. Screen patterns

| Screen | Pattern |
|---|---|
| **F1 App inventory** | `PageHeader` → `Table` (app, owner, annual spend, seats, renewal, usage status badge) → row action **Connect usage data** |
| **F2 Library check** | In library: info `Banner` + token form. Not in library: `EmptyState`-style card with **Build it with AI** |
| **F3 Paste docs** | One-column form (docs URL or OpenAPI upload) → `Stepper` with live progress |
| **F4 What we found** | Summary `Card`s in a grid (Login, Users, Usage, Limits, Warnings) → `EvidenceDrawer` → **Looks right** (primary) / **This looks wrong** (secondary) |
| **F5 Connect + test** | Token `Field` with scope checklist and trust note → `Checklist` → `Tabs`: Test results / Generated code / Run log |
| **F6 Savings preview** | Row of `Metric` cards → `BreakdownBar` → sources list → **Go live** |
| **F7 Connector detail** | Two columns: runs, versions and code on the left; `DetailsList` rail on the right (status, last sync, token owner, scopes, data card download) |
| **F8 Platform internal** | `Tabs`: Review queue / Fleet health / Opportunity map; each a `Table` with **Approve** / **Reject** |

---

## 9. Accessibility

- Text contrast meets WCAG AA (4.5:1). Every text and badge pair in §2 passes (lowest: `--text-muted` on `--surface-subdued`, 4.5:1). The one exception is `--text-placeholder` (2.3:1), used only for input placeholders and the em dash, never for real content.
- Status is never colour alone: always a word, and an icon where space allows.
- Every interactive element has a visible 2px `--focus-ring` outline and works with the keyboard.
- Live progress (F3, F5) is announced to screen readers with `aria-live="polite"`.
- Light theme only in the prototype.

---

## 10. Tokens (for the frontend)

The frontend (React + Tailwind, `TRD.md` §2) loads these CSS variables and maps Tailwind's theme to them. No raw hex values in components.

```css
:root {
  /* primary */
  --primary: #0A2540;
  --primary-hover: #1B3A5C;
  --primary-pressed: #061A2E;
  --primary-subtle: #E9EEF4;
  --focus-ring: #7A9CC6;
  --link: #0055BC;

  /* neutrals */
  --surface: #FFFFFF;
  --surface-subdued: #F6F8FA;
  --border: #EBEEF1;
  --border-strong: #C0C8D2;
  --text-heading: #21252C;
  --text: #353A44;
  --text-subdued: #545969;
  --text-muted: #687385;
  --text-placeholder: #A3ACBA;

  /* status: background / foreground */
  --success-bg: #D1FAB3;  --success-fg: #217005;
  --danger-bg: #FFE8EE;   --danger-fg: #B3093C;   --danger: #DF1B41;
  --warning-bg: #FEF8CA;  --warning-fg: #8A4B00;
  --info-bg: #CFF4FC;     --info-fg: #0055BC;
  --neutral-bg: #EBEEF1;  --neutral-fg: #414552;

  /* demo data */

  /* type */
  --font-sans: "IBM Plex Sans", system-ui, sans-serif;
  --font-mono: "IBM Plex Mono", ui-monospace, Menlo, monospace;

  /* spacing */
  --space-1: 4px; --space-2: 8px; --space-3: 12px; --space-4: 16px;
  --space-6: 24px; --space-8: 32px; --space-12: 48px;

  /* shape */
  --radius-sm: 6px; --radius-md: 8px;
  --shadow-float: 0 4px 16px rgba(10, 37, 64, 0.12);
}
```
