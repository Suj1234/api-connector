# AI-Generated Integration Builder — DESIGN

**For:** Senior PM take-home assignment
**Author:** Sujeet Kumar
**Date:** 31 Oct 2026
**Status:** v2. The design system for the prototype's screens (`PRD.md` §7). The frontend uses these tokens and nothing else.

---

## 1. Principles

The people using this screen are IT admins, procurement and security reviewers. They are deciding whether to trust a connector with an admin token and whether to cut seats. The design has to feel **calm, exact and trustworthy**, like an admin console, not like a marketing page.

**Built from the reference.** Every screen is made from the dashboard design reference's own parts: its app shell, sidebar, top bar, page header, cards, metrics, count tiles, filter pills, tables, pagination, tabs, drawer, modal, fields and date picker. Each component in §6 copies the reference part of the same name (sizes, colours, states). Only four things are our own: the logo, the Log out link, the page footer and the font.

1. **Dense and white.** Lots of information, little decoration. White surfaces, cool greys, thin borders.
2. **Colour has a job.** Blurple means "you can act on this". Tinted badges mean "this is the state of something". Nothing else gets colour.
3. **Every number shows its source.** "48 users · from Calendly API". "6 left the company · from HRIS". Usage always says what it measures ("Meetings hosted, 90 days · proxy").
4. **Plain words first, detail on demand.** Summary cards up front; users, evidence, logs and code behind a tab, a drawer or a toggle.
5. **Nothing decorative.** No gradients, no glows, no glass, no illustrations, no emoji, no sparkle icons for "AI". The AI is shown by what it found and the quotes that prove it, not by effects. One exception: the login page's gradient band and its slow drift (§8), the only brand moment in the product.

---

## 2. Colour

### 2.1 Core palette

| Token | Hex | Use |
|---|---|---|
| `--primary` | `#635BFF` | Blurple. Primary button, selected tab underline, selected count tile and choice card, focused input border |
| `--primary-hover` | `#5851EA` | Primary button hover |
| `--primary-pressed` | `#533AFD` | Primary button pressed |
| `--primary-subtle` | `#F5F4FF` | Selected row background; the evidence answer you opened |
| `--primary-tint` | `#E3E1FF` | The spinner's ring; the current step's segment in the build progress bar |
| `--primary-disabled` | `#B3ADFF` | Disabled primary button fill |
| `--focus-ring` | `#635BFF` | 2px focus outline, or the `--shadow-focus` ring on controls |
| `--link` | `#533AFD` | Text links, the current nav item, breadcrumbs, card footer links, and any blurple text on `--primary-subtle` (`#635BFF` on it is below 4.5:1) |
| `--navy` | `#0A2540` | Dark brand colour: the logo name. Never a button. |
| `--overlay` | `rgba(183, 192, 205, 0.6)` | The grey-blue scrim behind drawers and modals |

The palette follows the dashboard design reference: white surfaces, cool greys and one blurple for anything actionable.

### 2.2 Neutrals

| Token | Hex | Use |
|---|---|---|
| `--surface` | `#FFFFFF` | Page, cards, tables, modals, drawers |
| `--surface-subdued` | `#F6F8FA` | Search fields, row hover, the empty-state icon tile, code background, the login footer strip |
| `--border` | `#EBEEF1` | Dividers, card outlines, table rows |
| `--border-strong` | `#D5DBE1` | Input, button, count-tile and choice-card borders; the rule under section titles, tabs and table headers |
| `--border-hover` | `#C0C8D2` | A control's border on hover; the dashed border of an empty filter pill |
| `--text-heading` | `#21252C` | Page titles, section headings |
| `--text` | `#353A44` | Body text, field labels, table headers |
| `--text-subdued` | `#545969` | Card labels, nav icons, unselected tabs, descriptions |
| `--text-muted` | `#687385` | Timestamps, help text, sources ("from HRIS"), result counts |
| `--text-placeholder` | `#A3ACBA` | Placeholders, the em dash for empty values, disabled button text |

### 2.3 Status colours (always as a tinted badge with a word)

| Tone | Background | Border | Text / icon | Used for |
|---|---|---|---|---|
| Success | `#D1FAB3` | `#A8E28E` | `#217005` | Live, Connected, test passed, an active user |
| Danger | `#FFE8EE` | `#FFC4D3` | `#B3093C` | Needs repair, Reconnect needed, blocked call, left the company |
| Warning | `#FEF8CA` | `#F5DE7A` | `#8A4B00` | Needs help, Live (users only), "Renews in 58 days", a suspended user |
| Info | `#CFF4FC` | `#A4E3F5` | `#0055BC` | Testing, In library, conflict chip, an invited user |
| Neutral | `#EBEEF1` | `#D5DBE1` | `#414552` | Draft, Paused, No usage data, tier badges (T1, T2, T3), a deactivated user |

A badge is the word first, then a 12px icon (✓ success, ✕ danger, ⚠ warning, ⓘ info, none for neutral). Destructive buttons (Discard, Delete connector, Revoke token) use `--danger: #DF1B41` as the fill.

Two solid status colours from the reference: `--success: #2A9B0E` (a done step's node, a passed timeline item, the success banner's icon) and `--danger-subtle: #FDF4F5` (the critical banner's background).

### 2.4 Sample data

Replay mode must never be mistaken for real data (`TRD.md` §1), but it should not shout either. A neutral `Tag` reading "Sample data" sits beside the app name in the inventory (F1) and on the app page (F9), and beside the numbers it affects: the Users card ("Sample data: fake people"), the test, the savings preview and the connector detail. It is not in the sidebar or the top bar. No extra colour.

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

**Font:** IBM Plex Sans for everything, IBM Plex Mono for code, IDs, paths and JSON. Both from Google Fonts. Fallback: the system UI font. Numbers use tabular figures so columns line up. (The reference uses Ubuntu Sans; we keep IBM Plex.)

**Base size:** body text is 14px on the browser's default 16px root. The root must stay at 16px: Tailwind sizes are in rem, so a 14px root made every size 12.5% too small (12px text came out at 10.5px, 32px buttons at 28px).

| Style | Size / line height | Weight | Use |
|---|---|---|---|
| Page title | 28 / 36 | 700 | "App inventory", "Calendly" |
| Section title | 20 / 28 | 700 | Section headings over a strong rule |
| Card title | 16 / 24 | 700 | Card, drawer and modal titles |
| Metric value | 20 / 28, tabular | 600 | The number in a metric card |
| Big metric | 28 / 36, tabular | 600 | Big numbers in the savings preview |
| Body | 14 / 20 | 400 | Almost everything |
| Label | 14 / 20 | 600 | Field labels, nav items, app names in tables, links, buttons |
| Table header | 12 / 16 | 600 | Column headers |
| Caption | 12 / 16 | 400 | Help text, compare lines, timestamps, sources, result counts |
| Overline | 11 / 16, uppercase, 0.06em tracking | 600 | Small eyebrows above a title |
| Code | 13 / 20 | 400 | Generated code, run log, evidence pointers |

---

## 4. Spacing, size and shape

- **4px grid.** `--space-1` 4, `--space-2` 8, `--space-3` 12, `--space-4` 16, `--space-5` 20, `--space-6` 24, `--space-8` 32, `--space-12` 48.
- **Radius:** `--radius-sm` 6px for inputs, buttons, count tiles and choice cards; `--radius-md` 8px for cards, drawers, modals and popovers. Badges and tags are 4px. Filter pills are fully rounded.
- **Shadows:**
  - `--shadow-control` (light) on secondary buttons, inputs, choice cards and the logo mark;
  - `--shadow-primary` (a little stronger) on primary and danger buttons;
  - `--shadow-focus` (a blurple ring) on a focused control and the selected count tile;
  - `--shadow-popover` on menus and the date picker;
  - `--shadow-modal` on drawers, modals and the login card.
  Cards use a border, not a shadow.
- **Sizes:** controls 32px tall; small buttons 28px; login inputs and its button 40px; search field 36px; filter pills 24px; table rows 38px; top bar 60px.

---

## 5. Layout

The reference's app shell: sidebar, top bar, page.

| Part | Size |
|---|---|
| Sidebar | 244px, white, right border, 16px / 12px padding. The `Logo` on top; nav items 30px high with a 16px icon (the current one blurple text, no fill); "AI model" with the model's name pinned at the bottom |
| Top bar | 60px, white: the search field (max 560px, "Search apps or owners", filters App inventory) on the left, **Log out** on the right |
| Page | 24px gutters, full width; 24px between blocks |
| Footer | "© 2026 Integration builder", 12px, muted |
| Drawer | 480px, from the right, over the page and a grey-blue scrim; sticky footer with the buttons |
| Forms | Inside a drawer: fields 20px apart; short fields in two columns |
| Task page | The build flow (F3–F6) is one full-screen task, the reference pattern for setup flows: no sidebar; the 52px `FocusHeader` (✕ back to the app page, "Connect Calendly", a muted status, the step's buttons); a 200px `Stepper` rail on the left (Read the docs → Review what we found → Connect and test → Check the savings → Go live); the step's content on the right, 28px title and intro, cards 24px apart, max 1200px wide |

**Sidebar items:** App inventory. The Library and the platform review queue are built but hidden for now (`PRD.md` §15).

**One company on screen.** The tenant switcher is gone; the prototype shows one customer (Acme). Its sample data is labelled where the numbers are (§2.4).

---

## 6. Components

The prototype builds only what the screens need. Unless the row says otherwise, each one copies the reference part of the same name.

| Component | What it is | Where it appears |
|---|---|---|
| `AppShell` | Sidebar + top bar + page + footer | Every signed-in screen |
| `PageHeader` | Optional breadcrumb and overline, 28px title with badges, a subtitle line, actions on the right (primary first) | Every screen |
| `Breadcrumb` | Blurple 13px links, each followed by a 12px chevron | App page ("App inventory ›") |
| `Button` | `primary` (blurple), `secondary` (white, border), `ghost` (grey text), `danger`. 32px, semibold, with a shadow; `small` is 28px; `block` is full width and 40px (login only). Hover: primary darkens, secondary's border darkens. Disabled: primary `--primary-disabled`, others grey text, no shadow. Focus: `--shadow-focus` | Everywhere; **one primary per view**, right-most |
| `Icon` | The reference's 16px line set (1.5px stroke) | Nav, buttons, badges, fields |
| `Badge` | Tinted status with a 1px border; the word, then a 12px icon | Usage status, connector status, user status, "Renews in 58 days" |
| `Tag` | 16px high, 11px semibold, grey | "Sample data", "Optional" |
| `Card` | Bordered white block, 16px padding, 16px bold title, optional control on the right | App page tabs, F3–F7 |
| `MetricCard` | A `Card` holding a metric: grey label, 20px value, 12px compare line; optional footer (border on top) with a link on the left and a note on the right | App inventory, app page |
| `Metric` | Grey label, 20px semibold value, a 12px muted line saying where the number comes from | F5 results, F6 savings |
| `CountTabs` | Bordered tiles with a label and a count that filter the list below; the selected one is blurple with a focus ring | App inventory (All / No usage data / Connected / Renewing in 90 days) |
| `FilterChip` | A 24px pill: dashed with ⊕ when empty, solid with "Label │ value ⌄" and a ⊗ that clears it when applied. Picking opens a `Menu` | Owner (App inventory), Status (app page) |
| `Menu` | Popover list: 180px min, 8px radius, `--shadow-popover`, a 12px grey label, 32px items, ✓ on the chosen one | Under a filter pill |
| `SearchInput` | 36px borderless grey field with a search icon; one focus ring, no browser outline | Top bar, app page Users tab |
| `Table` | 12px bold headers over a strong rule, 38px rows, hover tint, "—" for empty cells, no outer border; optional footer | App inventory, app page users, F7, F8 |
| `Pagination` | Result count on the left; small **Previous** / **Next** on the right; no page numbers | Under every list |
| `Tabs` | Text tabs 20px apart over a strong rule; the selected one blurple and semibold with a 2px underline; optional count | App page (Users / Connector / Contract), F5 (Test / Generated code / Run log), F6 buckets, F7 |
| `DetailsList` | Label / value pairs: `stacked` (bold label over value) or `rows` (grey label left, value right); "—" when empty | App page tabs, F4, F7 |
| `Field` | Semibold label (with an `Optional` tag when it is), the control, then the error (red, with ⚠) or the help text (12px, muted) | All forms |
| `TextInput`, `Textarea` | 32px inputs with a border, a light shadow, a darker border on hover and a blurple ring on focus. `large` is 40px (login). `affix` puts a fixed "$" in front | All forms |
| `DateField` | An input-style field showing the date and a calendar icon; opens the reference `DatePicker` (Monday-first month grid, arrows, the chosen day in blurple) | Renewal date |
| `ChoiceCards` | Bordered options in a row, exactly one picked; the picked one has a blurple border and title | "API documentation: Docs link / OpenAPI file" |
| `Drawer` | A right-side sheet for creating one object without leaving the list: title and ✕, scrolling body, sticky footer with the buttons on the right. Closes on ✕, Escape or a click on the scrim | Add an app and Connect usage data (F2), evidence (F4) |
| `Modal` | A centred dialog over the scrim: 16px bold title and ✕, body, right-aligned footer. Closes on ✕, Escape or a click on the scrim | "Leave without saving?", confirm go-live, "This looks wrong" hint |
| `EmptyState` | A dashed box: a grey icon tile, a bold title, a 13px muted line, one action | "No usage data yet", "No apps match these filters" |
| `Banner` | A 16px icon, a bold title and text, an optional action. Neutral (our "info"): grey with a bulb; critical: red with a red border and ⚠; warning: yellow with a clock; success: white with a border and a green ✓ | Warnings, errors, partial results, token owner leaving, "Written by our templates, not by the AI" |
| `FocusHeader` | The 52px bar of a full-screen task: ✕, a divider, the title, then a muted status and the buttons on the right | Top of F3–F6 |
| `Stepper` | The vertical step list of setup flows: 13px semibold labels, 16px nodes (grey number; blurple when current; green ✓ when done); the current step lists its substeps with a 4px dot | The F3–F6 rail; F3 lists its four build stages under "Read the docs" |
| `Timeline` | Status nodes on a hairline spine, newest first: a title, a muted time and optional detail; green ✓, red ✕, yellow ⚠ or a spinner while running | F3 activity, F5 test (Login / Users / Usage / Mapping), F5 "Fixed automatically" |
| `CodeBlock` | Mono, line numbers, copy button; the six assignment items highlighted with a side marker and label | F5 / F7 Generated code tab |
| `RequestLog` | One mono row per API call: a status badge ("200 OK"), method and path, and the step and time on the right; never bodies or tokens | F5 Run log tab |
| `EvidenceDrawer` | A 520px `Drawer`: how the check works, then each answer in plain words ("Users endpoint"), its value, the docs quote, the page link and a **Proved** / **Not proved** badge with the reason. The **Proved** badge beside an answer on F4 opens it on that answer, highlighted | F4 |
| `ConflictChip` | Info chip: "2 sources disagree" → opens both values and the chosen source | F4 evidence drawer |
| `BreakdownBar` | An 8px bar of segments 2px apart, then a legend of 26px rows (10px swatch and label, value on the right) | F6 "Where every user lands" |
| `Logo` (ours) | A 36px blurple rounded square (`--radius-md`, `--shadow-control`) with a white link symbol, then a stacked name: "Integration" (17px, bold, navy, letter spacing -0.02em) over "BUILDER" (10px, semibold, blurple, letter spacing 0.24em). On the login gradient "BUILDER" is navy, so it stays readable | Login header, sidebar top |
| `Toast` | Short past-tense confirmation: dark grey (`--text`), white text, a green ✓ | "Miro is in your inventory", "Calendly is live", "Test passed" |
| `Spinner` | A 16px ring (24px large) in `--primary-tint` with a blurple top, one turn every 2 s | Buttons while saving, the running build step, running timeline items |

### 6.1 Status → badge

The connector statuses come from `PRD.md` §8. Every screen uses the same mapping.

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
| In library (hidden for now) | Info |

Usage status in the inventory: **Connected** (success), **Users only** (warning), **No usage data** (neutral). On the app page the header shows the connector's own status once there is a connector.

A user's account status on the app page: **Active** (success), **Suspended** (warning), **Invited** (info), **Deactivated** and **Unknown** (neutral).

### 6.2 Icons

The reference's line set (1.5px stroke, 16px; 12px inside badges). Used: grid (App inventory), search, plus, plus-circle and x-circle (filter pills), x (close), check, check-circle, alert, info, clock, chevrons, calendar, bulb (AI model, neutral banners), lock (the token note), code ("Written by our templates"), external (evidence links). Only for actions and status. No "magic" or sparkle icons.

---

## 7. Writing rules

- **Sentence case** for titles, buttons, tabs and column headers ("Connect usage data", "Generated code"). Uppercase only in overlines.
- **Buttons start with a verb and name the thing:** "Add an app", "Save app", "Build with AI", "Connect usage data", "Run test", "Continue setup". The confirm button repeats what will happen ("Go live with users only").
- **Talk to the admin as "you"**: "Your token is encrypted and never shared with the AI."
- **Errors say what to fix**, using the plain messages in `TRD.md` §7: "This token needs the Owner or Admin role and the scheduled_events:read scope", "Enter a full link, like https://developer.example.com/api", "Calendly is already in your inventory. Use Connect usage data on its row."
- **Confirmations are past tense and specific**: "Calendly is live", "Miro is in your inventory".
- **Unsaved work is never lost silently.** Closing a form with input asks "Leave without saving?", with **Discard** and **Save app** (or **Keep editing**).
- **Either/or is said out loud**: "Give one of the two."
- **Every number has a source**: "from Calendly API", "from HRIS", "from SSO", "from contract", "Sample data: fake people".
- **Usage says what it measures**, never just "active": "Meetings hosted (90 days) · proxy", "Last login · from SSO, not from the app".
- **Money:** "$6,960 / yr". **Dates:** "26 Dec 2026"; in tables "26 Dec". **Relative time:** "Renews in 58 days".
- **Empty values** are an em dash (—), never blank or "N/A".
- No emoji. No exclamation marks.

---

## 8. Screen patterns

| Screen | Pattern |
|---|---|
| **Login** | Based on the reference's sign-in layout. White page; a gradient band (yellow → red → purple → cyan, `--gradient-*`) across the top 62%, skewed −12°, its colours drifting slowly (15 s, off when the user prefers reduced motion). `Logo` top left; "© 2026 Integration builder" caption bottom left. A 480px white card with `--shadow-modal`, centred both ways, fading up 8px on load: "Log in to your account" (24px, medium), **Email** (format-checked; "Enter a valid email, like name@company.com" after the field is left) and **Password** (with a show/hide eye), 40px inputs with a blurple focus ring, and a `block` primary **Log in** that stays disabled until both are valid ("Logging in…" while it works). A `--surface-subdued` footer strip: "Access is by invite. Please reach out to Sujeet Kumar for your email and password." No other sign-in options. |
| **F1 App inventory** | `PageHeader` ("App inventory", **+ Add an app**) → four `MetricCard`s with footers: Annual spend, With usage data, Without usage data, Next renewal (each footer link filters the list) → `CountTabs` → Owner `FilterChip` → `Table` (app, owner, annual spend, seats, renewal with a "Renews in N days" badge within 90 days, usage status badge, **Connect usage data** link) → `Pagination` (10 per page). The top bar search filters it too. Clicking a row opens the app page (F9); the link opens the F2 drawer. "No apps match these filters" `EmptyState` with **Clear filters** |
| **F2 Add an app / Connect usage data** | A 480px `Drawer` over the inventory. **Add an app:** App name; Owner and Renewal date (`DateField`); Annual spend ("$" affix) and Seats; then "API documentation" `ChoiceCards` (**Docs link** or **OpenAPI file**, "Give one of the two") and only the chosen field. Footer: **Cancel**, **Save app** (adds it to the inventory without building), **Build with AI** (primary). Buttons stay off until the fields are valid. **Connect usage data** (a listed app): the same drawer with only the documentation part. Closing with input opens the "Leave without saving?" `Modal`; a reload or closed tab gets the browser's warning. In the library (hidden for now): info `Banner` + **Connect with your token** |
| **F3 Read the docs** (task page) | "Building the Calendly connector", "This usually takes 1 to 2 minutes…" → a `Card` for the current step: large `Spinner`, "Step 2 of 4: Drafting the connector", the time so far, one plain sentence on what is happening, and a 4-segment progress bar → "What each step does" `Card` (all four steps explained) → "Activity" `Card` with a `Timeline` (each step's result and how long it took). The rail lists the four build stages as substeps. Done: a success `Banner` ("Done in 1 min 32 s") and it opens F4; failed: a critical `Banner` with **Add a hint**, **Try again** (same docs) and a "Use another docs link" link |
| **F4 Review what we found** (task page) | Header buttons **This looks wrong** / **Looks right** (primary) → intro with "16 of 16 answers are proved" and **See all the evidence** → full-width `Card`s with `rows` `DetailsList`s: Login (sign-in method, role, scopes, setup), Users (endpoint, paging, fields read), Usage (what it measures, where it comes from, endpoint, window, SSO fallback), Limits (rate limit, plan note, API address); a **Proved** badge beside each answer opens the `EvidenceDrawer` on it → warnings `Banner` → "Written by our templates, not by the AI" `Banner`. **This looks wrong** opens a `Modal`: what a hint does, the hint `Textarea`, and four examples of hints that help |
| **F5 Connect and test** (task page) | `Tabs`: **Test** / **Generated code** / **Run log**. Test: "Connect" `Card` (sample data: no token needed; live: setup steps, exact scopes, the fields, the token owner's email; a lock line "Encrypted, read-only, never shared with the AI" and **Run test**) → "Test in the sandbox" `Card` with a `Timeline` (live events while it runs; then Login, Users, Usage, Mapping) → "Results" `Card` of four `Metric`s → "What the generated code covers": the assignment's six items, each with a **Done** badge → "Fixed automatically" `Timeline` when repairs ran. When passed, the header shows **Continue** |
| **F6 Check the savings** (task page) | Header **Go live** (or **Go live with users only**) → `Banner`s (missing files, SSO mismatch, token owner leaving) → a `Card` of five `Metric`s (users, left, inactive, seats nobody holds, recoverable before renewal) → "Where every user lands" `Card` with the `BreakdownBar` and how the money is worked out → bucket `Tabs` over a people `Table`. **Go live** opens a confirm `Modal` (a note is required when the count differs from SSO by more than 2%) and lands on the app page (F9) with a toast |
| **F7 Connector detail** | `Breadcrumb` "App inventory › Calendly" → `PageHeader` ("Calendly connector", status badge, "Sample data" tag, **Download data card**, **Continue setup** until live) → `Banner`s → `Tabs` (Overview / Generated code / Versions). Overview: "Last test run" and "What it reads" `Card`s with `rows` lists, and a "Details" `Card` on the right with a `stacked` list. Submit to library is hidden for now |
| **F8 Platform internal** | Hidden for now. `Tabs`: Review queue / Fleet health / Opportunity map; each a `Table` with **Approve** / **Reject** |
| **F9 App page** | `Breadcrumb` "App inventory ›" → `PageHeader` (app name, status badge, "Sample data" tag, "Owner · Renews 26 Dec 2026", **Connect usage data** or **Continue setup** until live) → four `MetricCard`s: Users, Active accounts, No activity in 30 days, Seats paid for ("12 seats nobody holds") → `Tabs`. **Users:** `SearchInput` + Status `FilterChip` + `Table` of every user the connector retrieved (name or email, role, status badge, last active, the app's usage metric with its label; empty columns are hidden) + `Pagination` (25 per page). **Connector:** `Card` with a `rows` `DetailsList` (status, data source, last test, users retrieved, usage tier, docs, version) and **Open connector**. **Contract:** `Card` with owner, annual spend, seats, price per seat, renewal date. Before a connector has data: "No usage data yet" `EmptyState` with the next action, and "—" in the cards instead of made-up numbers |

---

## 9. Accessibility

- Text contrast meets WCAG AA (4.5:1). Every text and badge pair in §2 passes (lowest: `--text-muted` on `--surface-subdued`, 4.5:1). The one exception is `--text-placeholder` (2.3:1), used only for placeholders, the em dash and disabled text, never for real content.
- Status is never colour alone: always a word, and an icon where space allows.
- Every interactive element works with the keyboard and shows focus: a 2px `--focus-ring` outline, or the `--shadow-focus` ring on buttons, inputs, pills and tiles.
- Drawers, modals and menus close on Escape; Escape on the "Leave without saving?" question goes back to editing.
- Tabs, count tiles, choice cards and menus use the tab, radio and menu roles.
- Live progress (F3, F5) is announced to screen readers with `aria-live="polite"`.
- Light theme only in the prototype.

---

## 10. Tokens (for the frontend)

The frontend (React + Tailwind, `TRD.md` §2) loads these CSS variables from `src/index.css` and maps Tailwind's theme to them. No raw hex values in components.

```css
:root {
  /* primary */
  --primary: #635BFF;
  --primary-hover: #5851EA;
  --primary-pressed: #533AFD;
  --primary-subtle: #F5F4FF;
  --primary-tint: #E3E1FF;
  --primary-disabled: #B3ADFF;
  --focus-ring: #635BFF;
  --link: #533AFD;
  --navy: #0A2540;
  --overlay: rgba(183, 192, 205, 0.6);

  /* neutrals */
  --surface: #FFFFFF;
  --surface-subdued: #F6F8FA;
  --border: #EBEEF1;
  --border-strong: #D5DBE1;
  --border-hover: #C0C8D2;
  --text-heading: #21252C;
  --text: #353A44;
  --text-subdued: #545969;
  --text-muted: #687385;
  --text-placeholder: #A3ACBA;

  /* status: background / foreground / border */
  --success: #2A9B0E;     --success-bg: #D1FAB3;  --success-fg: #217005;  --success-border: #A8E28E;
  --danger-subtle: #FDF4F5;
  --danger-bg: #FFE8EE;   --danger-fg: #B3093C;   --danger: #DF1B41;  --danger-border: #FFC4D3;
  --warning-bg: #FEF8CA;  --warning-fg: #8A4B00;  --warning-border: #F5DE7A;
  --info-bg: #CFF4FC;     --info-fg: #0055BC;     --info-border: #A4E3F5;
  --neutral-bg: #EBEEF1;  --neutral-fg: #414552;

  /* savings chart (§2.5) */
  --chart-left: #DF1B41; --chart-inactive: #EE6902; --chart-never: #87909F; --chart-not-in-hr: #0055BC;
  --chart-active: #2A9B0E; --chart-excluded: #D5DBE1;

  /* type */
  --font-sans: "IBM Plex Sans", system-ui, sans-serif;
  --font-mono: "IBM Plex Mono", ui-monospace, Menlo, monospace;

  /* spacing (Tailwind's scale on a 16px root) */
  --space-1: 4px; --space-2: 8px; --space-3: 12px; --space-4: 16px; --space-5: 20px;
  --space-6: 24px; --space-8: 32px; --space-12: 48px;

  /* shape */
  --radius-sm: 6px; --radius-md: 8px;
  --shadow-float: 0 4px 16px rgba(10, 37, 64, 0.12);
  --shadow-modal: 0 0 0 1px rgba(64, 68, 82, 0.08), 0 5px 15px rgba(0, 0, 0, 0.12), 0 15px 35px rgba(48, 49, 61, 0.08);
  --shadow-focus: 0 0 0 1px #635BFF, 0 0 0 4px rgba(99, 91, 255, 0.28);
  --shadow-control: 0 1px 1px rgba(0, 0, 0, 0.08), 0 2px 5px rgba(60, 66, 87, 0.08);
  --shadow-primary: 0 1px 1px rgba(0, 0, 0, 0.12), 0 2px 5px rgba(60, 66, 87, 0.12);
  --shadow-popover: 0 0 0 1px rgba(64, 68, 82, 0.08), 0 3px 6px rgba(0, 0, 0, 0.12), 0 7px 14px rgba(60, 66, 87, 0.08);

  /* login band only */
  --gradient-yellow: #FFCB57; --gradient-red: #FF333D; --gradient-purple: #A960EE; --gradient-cyan: #90E0FF;
}
```
