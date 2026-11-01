// The DESIGN.md components (§6). Tokens only; no raw colours.
import { Fragment, useEffect, useRef, useState, type ReactNode } from "react";

export const cx = (...names: (string | false | null | undefined)[]) => names.filter(Boolean).join(" ");

// --- formatting (DESIGN.md §7) -------------------------------------------------------------

const MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];
export function fmtDate(iso: string | null | undefined, short = false): string {
  if (!iso) return "—";
  const d = new Date(iso.length === 10 ? `${iso}T00:00:00Z` : iso);
  const day = `${d.getUTCDate()} ${MONTHS[d.getUTCMonth()]}`;
  return short ? day : `${day} ${d.getUTCFullYear()}`;
}
export function fmtMoney(n: number | null | undefined, perYear = false): string {
  if (n === null || n === undefined) return "—";
  return `$${Math.round(n).toLocaleString("en-US")}${perYear ? " / yr" : ""}`;
}
export const dash = (v: unknown) => (v === null || v === undefined || v === "" ? "—" : String(v));
// The spec's paging types are code names; screens show these words.
const PAGING: Record<string, string> = {
  cursor: "Cursor (a token for the next page)",
  next_url: "Next-page link",
  offset_limit: "Offset and limit",
  page_number: "Page numbers",
  link_header: "Link header",
  none: "One page, no paging",
};
export const pagingLabel = (type: string) => PAGING[type] ?? type;

// --- brand ----------------------------------------------------------------------------------

// The logo (DESIGN.md §6): a purple mark with a white link, then "Integration" stacked over a spaced-out "BUILDER".
export function Logo({ onArt }: { onArt?: boolean }) {
  return (
    <span className="inline-flex items-center gap-2.5" aria-label="Integration builder">
      <span aria-hidden className="flex h-9 w-9 items-center justify-center rounded-md bg-primary shadow-control">
        <svg viewBox="0 0 24 24" className="h-5 w-5" fill="none" stroke="white" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
          <path d="M10 13a5 5 0 0 0 7.54.54l3-3a5 5 0 0 0-7.07-7.07l-1.72 1.71" />
          <path d="M14 11a5 5 0 0 0-7.54-.54l-3 3a5 5 0 0 0 7.07 7.07l1.71-1.71" />
        </svg>
      </span>
      <span aria-hidden className="flex flex-col leading-none">
        <span className="text-[17px] font-bold tracking-[-0.02em] text-navy">Integration</span>
        <span className={cx("mt-1 text-[10px] font-semibold tracking-[0.24em]", onArt ? "text-navy" : "text-primary")}>BUILDER</span>
      </span>
    </span>
  );
}

// --- icons: paths from the reference design system's 16px stroke set ---------------------------

const ICON_PATHS = {
  grid: "M2.5 2.5h4v4h-4ZM9.5 2.5h4v4h-4ZM2.5 9.5h4v4h-4ZM9.5 9.5h4v4h-4Z",
  search: "M7 2.5a4.5 4.5 0 1 0 0 9 4.5 4.5 0 0 0 0-9ZM10.3 10.3l3.2 3.2",
  plus: "M8 3v10M3 8h10",
  "plus-circle": "M8 1.8a6.2 6.2 0 1 0 0 12.4A6.2 6.2 0 0 0 8 1.8ZM8 5.5v5M5.5 8h5",
  "x-circle": "M8 1.8a6.2 6.2 0 1 0 0 12.4A6.2 6.2 0 0 0 8 1.8ZM6 6l4 4M10 6l-4 4",
  "chev-down": "M4 6l4 4 4-4",
  bulb: "M6 12.5h4M6.5 14.5h3M8 1.5a4.5 4.5 0 0 0-2.5 8.2V11h5V9.7A4.5 4.5 0 0 0 8 1.5Z",
  check: "M3 8.5 6.2 11.5 13 4.5",
  x: "M4 4l8 8M12 4l-8 8",
  alert: "M8 2 14.5 13.5h-13ZM8 6.5v3M8 11.5h.01",
  info: "M8 1.8a6.2 6.2 0 1 0 0 12.4A6.2 6.2 0 0 0 8 1.8ZM8 7.3v3.7M8 5.2h.01",
  "chev-left": "M10 4 6 8l4 4",
  "chev-right": "M6 4l4 4-4 4",
  calendar: "M2.5 3.5h11v10h-11ZM2.5 6.5h11M5.5 2v3M10.5 2v3",
  "check-circle": "M8 1.8a6.2 6.2 0 1 0 0 12.4A6.2 6.2 0 0 0 8 1.8ZM5.3 8.2l1.8 1.8 3.6-3.8",
  clock: "M8 1.8a6.2 6.2 0 1 0 0 12.4A6.2 6.2 0 0 0 8 1.8ZM8 4.5V8l2.5 1.5",
  external: "M9.5 2.5h4v4M13.5 2.5 7.5 8.5M11.5 9.5v4h-9v-9h4",
  lock: "M3.5 7.5h9v6.5h-9ZM5.5 7.5V5a2.5 2.5 0 0 1 5 0v2.5",
  doc: "M4 1.8h5.5l3 3v9.4H4ZM9.5 1.8v3h3",
  code: "M5.5 4.5 2 8l3.5 3.5M10.5 4.5 14 8l-3.5 3.5",
  "arrow-right": "M3 8h10M9.5 4.5 13 8l-3.5 3.5",
} as const;
export type IconName = keyof typeof ICON_PATHS;

export function Icon({ name, className = "h-4 w-4" }: { name: IconName; className?: string }) {
  return (
    <svg aria-hidden viewBox="0 0 16 16" className={cx("shrink-0", className)} fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
      <path d={ICON_PATHS[name]} />
    </svg>
  );
}

// --- buttons ----------------------------------------------------------------------------

type ButtonProps = {
  children: ReactNode;
  variant?: "primary" | "secondary" | "ghost" | "danger";
  small?: boolean;
  block?: boolean; // full width, 40px: the login card only (DESIGN.md §6)
  disabled?: boolean;
  busy?: boolean;
  onClick?: () => void;
  type?: "button" | "submit";
};
export function Button({ children, variant = "secondary", small, block, disabled, busy, onClick, type = "button" }: ButtonProps) {
  const styles = {
    primary: "border-primary bg-primary text-white shadow-primary enabled:hover:border-primary-hover enabled:hover:bg-primary-hover enabled:active:bg-primary-pressed disabled:border-primary-disabled disabled:bg-primary-disabled",
    secondary: "border-border-strong bg-surface text-text shadow-control enabled:hover:border-border-hover disabled:text-text-placeholder",
    ghost: "border-transparent bg-transparent text-text-subdued enabled:hover:bg-surface-subdued disabled:text-text-placeholder",
    danger: "border-danger bg-danger text-white shadow-primary enabled:hover:opacity-90 disabled:opacity-50",
  }[variant];
  return (
    <button
      type={type}
      onClick={onClick}
      disabled={disabled || busy}
      className={cx(
        "inline-flex items-center justify-center gap-1.5 whitespace-nowrap rounded-sm border font-semibold transition-colors focus-visible:shadow-focus focus-visible:outline-none disabled:cursor-not-allowed disabled:shadow-none",
        small ? "h-7 px-2 text-[13px]" : block ? "h-10 w-full px-4" : "h-8 px-3",
        styles,
      )}
    >
      {busy && <Spinner light={variant === "primary" || variant === "danger"} />}
      {children}
    </button>
  );
}

// Reference Spinner: a 16px (24px large) purple ring with a brand-coloured top, one turn every 2 s.
export function Spinner({ light, large }: { light?: boolean; large?: boolean }) {
  return (
    <span
      role="status"
      aria-label="Loading"
      className={cx(
        "inline-block shrink-0 animate-[spin_2s_linear_infinite] rounded-full border-2",
        large ? "h-6 w-6" : "h-4 w-4",
        light ? "border-white/40 border-t-white" : "border-primary-tint border-t-primary",
      )}
    />
  );
}

// --- status ------------------------------------------------------------------------------

export type Tone = "success" | "danger" | "warning" | "info" | "neutral";
const TONES: Record<Tone, string> = {
  success: "bg-success-bg text-success-fg",
  danger: "bg-danger-bg text-danger-fg",
  warning: "bg-warning-bg text-warning-fg",
  info: "bg-info-bg text-info-fg",
  neutral: "bg-neutral-bg text-neutral-fg",
};
const BADGE_BORDER: Record<Tone, string> = {
  success: "border-success-border",
  danger: "border-danger-border",
  warning: "border-warning-border",
  info: "border-info-border",
  neutral: "border-border-strong",
};
const BADGE_ICON: Record<Tone, IconName | null> = { success: "check", danger: "x", warning: "alert", info: "info", neutral: null };

export function Badge({ tone = "neutral", children, icon = true }: { tone?: Tone; children: ReactNode; icon?: boolean }) {
  return (
    <span className={cx("inline-flex items-center gap-1 whitespace-nowrap rounded-badge border px-1.5 py-0.5 text-xs font-medium leading-[14px]", TONES[tone], BADGE_BORDER[tone])}>
      {children}
      {icon && BADGE_ICON[tone] && <Icon name={BADGE_ICON[tone]!} className="h-3 w-3 [stroke-width:2]" />}
    </span>
  );
}

// Reference Tag: 16px, 11px semibold, grey.
export function Tag({ children }: { children: ReactNode }) {
  return <span className="inline-flex h-4 items-center whitespace-nowrap rounded-badge bg-neutral-bg px-[5px] text-[11px] font-semibold leading-4 text-text-subdued">{children}</span>;
}

// PRD §8 lifecycle → DESIGN.md §6.1 badge tones.
export const STATUS: Record<string, { label: string; tone: Tone }> = {
  draft: { label: "Draft", tone: "neutral" },
  testing: { label: "Testing", tone: "info" },
  needs_help: { label: "Needs help", tone: "warning" },
  live: { label: "Live", tone: "success" },
  live_users_only: { label: "Live (users only)", tone: "warning" },
  needs_repair: { label: "Needs repair", tone: "danger" },
  reconnect_needed: { label: "Reconnect needed", tone: "danger" },
  paused: { label: "Paused", tone: "neutral" },
};
export function StatusBadge({ status }: { status: string }) {
  const s = STATUS[status] ?? { label: status, tone: "neutral" as Tone };
  return <Badge tone={s.tone}>{s.label}</Badge>;
}

// --- layout -----------------------------------------------------------------------------

// Reference PageHeader: optional breadcrumb and eyebrow, 28px title with badge, subtitle, actions on the right.
export function PageHeader({ breadcrumb, eyebrow, title, badge, actions, children }: { breadcrumb?: ReactNode; eyebrow?: string; title: string; badge?: ReactNode; actions?: ReactNode; children?: ReactNode }) {
  return (
    <div className="mb-6 flex items-start justify-between gap-6">
      <div className="grid gap-1">
        {breadcrumb}
        {eyebrow && <div className="eyebrow">{eyebrow}</div>}
        <div className="flex items-center gap-3">
          <h1 className="title">{title}</h1>
          {badge}
        </div>
        {children && <div className="mt-1 text-text-subdued">{children}</div>}
      </div>
      {actions && <div className="flex shrink-0 items-center gap-2">{actions}</div>}
    </div>
  );
}

// Reference SectionTitle: 20px bold over a strong rule.
export function SectionTitle({ children, action }: { children: ReactNode; action?: ReactNode }) {
  return (
    <div className="mb-4 mt-8 flex items-center justify-between gap-3 border-b border-border-strong pb-3">
      <h2 className="text-xl font-bold text-text-heading">{children}</h2>
      {action}
    </div>
  );
}

export function Card({ title, children, aside, className }: { title?: ReactNode; children: ReactNode; aside?: ReactNode; className?: string }) {
  return (
    <section className={cx("rounded-md border border-border bg-surface p-4", className)}>
      {title && (
        <div className="mb-3 flex items-center justify-between gap-2">
          <h3 className="text-base font-bold text-text-heading">{title}</h3>
          {aside}
        </div>
      )}
      {children}
    </section>
  );
}

// Reference Metric: grey label, 20px semibold value, a muted 12px line under it (where the number comes from).
export function Metric({ label, value, compare }: { label: ReactNode; value: ReactNode; compare?: ReactNode }) {
  return (
    <div className="grid content-start gap-0.5">
      <span className="text-text-subdued">{label}</span>
      <span className="text-xl font-semibold leading-7 text-text">{value}</span>
      {compare && <span className="text-xs text-text-muted">{compare}</span>}
    </div>
  );
}

// Reference Banner: icon, bold title, text. Neutral is grey (our "info"), critical red with a border, warning yellow,
// success white with a border.
const BANNER: Record<Tone, { box: string; icon: IconName; iconColor: string; title?: string }> = {
  info: { box: "bg-surface-subdued", icon: "bulb", iconColor: "text-text-subdued" },
  neutral: { box: "bg-surface-subdued", icon: "bulb", iconColor: "text-text-subdued" },
  danger: { box: "border border-danger-border bg-danger-subtle", icon: "alert", iconColor: "text-danger-fg", title: "text-danger-fg" },
  warning: { box: "bg-warning-bg", icon: "clock", iconColor: "text-warning-fg" },
  success: { box: "border border-border-strong bg-surface", icon: "check-circle", iconColor: "text-success" },
};
export function Banner({ tone = "info", icon, title, children, action }: { tone?: Tone; icon?: IconName; title?: string; children?: ReactNode; action?: ReactNode }) {
  const t = BANNER[tone];
  return (
    <div className={cx("flex items-start gap-2 rounded-sm px-3 py-2 text-text", t.box)} role={tone === "danger" ? "alert" : "status"}>
      <Icon name={icon ?? t.icon} className={cx("mt-0.5 h-4 w-4", t.iconColor)} />
      <div className="min-w-0 flex-1">
        {title && <div className={cx("font-semibold", t.title)}>{title}</div>}
        {children && <div>{children}</div>}
      </div>
      {action && <div className="flex flex-none items-center gap-3">{action}</div>}
    </div>
  );
}

// Reference DetailsList: "stacked" (bold label over value) or "rows" (grey label left, value right); "—" when empty.
export function DetailsList({ items, layout = "stacked" }: { items: [string, ReactNode][]; layout?: "stacked" | "rows" }) {
  const rows = layout === "rows";
  return (
    <dl className={cx("grid", rows ? "gap-0" : "gap-4")}>
      {items.map(([label, value]) => (
        <div key={label} className={cx(rows && "grid grid-cols-[minmax(120px,200px)_1fr] gap-4 py-1.5")}>
          <dt className={rows ? "text-text-subdued" : "font-semibold text-text"}>{label}</dt>
          <dd className={cx("break-words text-neutral-fg", !rows && "mt-0.5")}>
            {value === null || value === undefined || value === "" ? <span className="text-text-placeholder">—</span> : value}
          </dd>
        </div>
      ))}
    </dl>
  );
}

// Reference Breadcrumb: purple links, each followed by a small chevron.
export function Breadcrumb({ items }: { items: { label: string; onClick: () => void }[] }) {
  return (
    <nav aria-label="Breadcrumb" className="flex items-center gap-1 text-[13px] leading-4">
      {items.map((it) => (
        <span key={it.label} className="flex items-center gap-1">
          <button type="button" onClick={it.onClick} className="font-semibold text-link hover:text-text">{it.label}</button>
          <Icon name="chev-right" className="h-3 w-3 text-text-muted" />
        </span>
      ))}
    </nav>
  );
}

// Reference EmptyState (boxed): optional icon tile, title, 13px description, action.
export function EmptyState({ title, icon, children, action }: { title?: string; icon?: IconName; children?: ReactNode; action?: ReactNode }) {
  return (
    <div className="grid justify-items-center gap-1 rounded-md border border-dashed border-border-strong p-6 text-center">
      {icon && (
        <span className="mb-2 grid h-8 w-8 place-items-center rounded-sm bg-surface-subdued text-text-muted">
          <Icon name={icon} />
        </span>
      )}
      {title && <span className="font-semibold text-text">{title}</span>}
      {children && <span className="max-w-[44ch] text-[13px] text-text-muted">{children}</span>}
      {action && <div className="mt-2">{action}</div>}
    </div>
  );
}

// --- tables, tabs ---------------------------------------------------------------------------

// Reference Table: bold 12px headers, 38px rows, "—" for empty cells, optional footer (Pagination).
export function Table<T>({ rows, columns, rowKey, onRow, footer }: {
  rows: T[];
  columns: { key: string; header: string; render: (row: T) => ReactNode; align?: "right" }[];
  rowKey: (row: T) => string | number;
  onRow?: (row: T) => void;
  footer?: ReactNode;
}) {
  return (
    <div>
      <div className="overflow-x-auto">
        <table className="w-full border-collapse">
          <thead>
            <tr>
              {columns.map((c) => (
                <th key={c.key} className={cx("whitespace-nowrap border-b border-border-strong py-2 pr-3 text-xs font-semibold text-text", c.align === "right" ? "text-right" : "text-left")}>
                  {c.header}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {rows.map((row) => (
              <tr key={rowKey(row)} onClick={onRow ? () => onRow(row) : undefined} className={cx("hover:bg-surface-subdued", onRow && "cursor-pointer")}>
                {columns.map((c) => {
                  const v = c.render(row);
                  return (
                    <td key={c.key} className={cx("h-[38px] border-b border-border py-1.5 pr-3 align-middle text-neutral-fg", c.align === "right" && "text-right")}>
                      {v === null || v === undefined || v === "" ? <span className="text-text-placeholder">—</span> : v}
                    </td>
                  );
                })}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      {footer && <div className="pt-3">{footer}</div>}
    </div>
  );
}

export function Pagination({ summary, hasPrevious, hasNext, onPrevious, onNext }: { summary: ReactNode; hasPrevious: boolean; hasNext: boolean; onPrevious: () => void; onNext: () => void }) {
  return (
    <div className="flex items-center justify-between gap-3 text-xs text-text-muted">
      <span>{summary}</span>
      <span className="flex gap-2">
        <Button small disabled={!hasPrevious} onClick={onPrevious}>Previous</Button>
        <Button small disabled={!hasNext} onClick={onNext}>Next</Button>
      </span>
    </div>
  );
}

// Reference CountTabs: bordered status tiles above a list that filter it and show counts.
export function CountTabs({ items, value, onChange }: { items: { value: string; label: string; count: number }[]; value: string; onChange: (v: string) => void }) {
  return (
    <div role="tablist" className="grid grid-cols-[repeat(auto-fit,minmax(120px,1fr))] gap-2">
      {items.map((t) => {
        const on = t.value === value;
        return (
          <button
            key={t.value}
            type="button"
            role="tab"
            aria-selected={on}
            onClick={() => onChange(t.value)}
            className={cx("grid gap-0.5 rounded-sm border bg-surface px-3 py-2 text-left", on ? "border-primary text-link shadow-focus" : "border-border-strong text-text-subdued")}
          >
            {t.label}
            <span className={cx("text-base font-semibold", on ? "text-link" : "text-text")}>{t.count}</span>
          </button>
        );
      })}
    </div>
  );
}

// Closes a popover on a click outside it or Escape.
function useDismiss<T extends HTMLElement>(open: boolean, close: () => void) {
  const ref = useRef<T>(null);
  useEffect(() => {
    if (!open) return;
    const onEvent = (e: MouseEvent | KeyboardEvent) => {
      if (e instanceof KeyboardEvent ? e.key === "Escape" : !ref.current?.contains(e.target as Node)) close();
    };
    document.addEventListener("mousedown", onEvent);
    document.addEventListener("keydown", onEvent);
    return () => {
      document.removeEventListener("mousedown", onEvent);
      document.removeEventListener("keydown", onEvent);
    };
  }, [open, close]);
  return ref;
}

// Reference FilterChip (dashed pill, solid with its value once applied); picking opens the reference Menu.
export function FilterChip({ label, value, options, onChange }: { label: string; value: string; options: string[]; onChange: (v: string) => void }) {
  const [open, setOpen] = useState(false);
  const ref = useDismiss<HTMLSpanElement>(open, () => setOpen(false));

  return (
    <span ref={ref} className="relative inline-flex">
      <span
        className={cx(
          "inline-flex h-6 items-center gap-1.5 whitespace-nowrap rounded-full border bg-surface pl-1.5 pr-2 text-xs font-semibold text-text-subdued hover:bg-surface-subdued has-[:focus-visible]:shadow-focus",
          value ? "border-solid border-border-strong" : "border-dashed border-border-hover",
        )}
      >
        {value ? (
          <button type="button" aria-label={`Clear the ${label.toLowerCase()} filter`} onClick={() => onChange("")} className="grid hover:text-text focus-visible:outline-none">
            <Icon name="x-circle" className="h-3.5 w-3.5" />
          </button>
        ) : (
          <Icon name="plus-circle" className="h-3.5 w-3.5" />
        )}
        <button type="button" aria-haspopup="menu" aria-expanded={open} onClick={() => setOpen(!open)} className="inline-flex items-center gap-1.5 focus-visible:outline-none">
          {label}
          {value && (
            <>
              <span className="h-3 w-px bg-border-strong" />
              <span className="text-link">{value}</span>
              <Icon name="chev-down" className="h-3 w-3" />
            </>
          )}
        </button>
      </span>
      {open && (
        <div role="menu" className="absolute left-0 top-full z-20 mt-1 grid min-w-[180px] rounded-md bg-surface py-1 shadow-popover">
          <div className="px-3 pb-1 pt-1.5 text-xs font-semibold text-text-muted">Filter by {label.toLowerCase()}</div>
          {options.map((o) => (
            <button
              key={o}
              type="button"
              role="menuitemradio"
              aria-checked={o === value}
              onClick={() => {
                onChange(o);
                setOpen(false);
              }}
              className="flex min-h-8 items-center gap-2 px-3 text-left text-text hover:bg-surface-subdued focus-visible:bg-surface-subdued focus-visible:outline-none"
            >
              <Icon name="check" className={cx("h-4 w-4 text-link", o !== value && "invisible")} />
              {o}
            </button>
          ))}
        </div>
      )}
    </span>
  );
}

// Reference ChoiceCard group: bordered options, exactly one picked (a radio group).
export function ChoiceCards<T extends string>({ label, value, onChange, options }: {
  label: string;
  value: T;
  onChange: (v: T) => void;
  options: { value: T; title: string; description?: string }[];
}) {
  return (
    <div role="radiogroup" aria-label={label} className="grid grid-cols-[repeat(auto-fit,minmax(140px,1fr))] gap-2">
      {options.map((o) => {
        const on = o.value === value;
        return (
          <button
            key={o.value}
            type="button"
            role="radio"
            aria-checked={on}
            onClick={() => onChange(o.value)}
            className={cx(
              "grid gap-0.5 rounded-sm border bg-surface px-3 py-2 text-left text-text focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-focus",
              on ? "border-primary shadow-[0_0_0_1px_var(--primary)]" : "border-border-strong shadow-control",
            )}
          >
            <span className={cx("font-semibold", on && "text-link")}>{o.title}</span>
            {o.description && <span className="text-xs text-text-muted">{o.description}</span>}
          </button>
        );
      })}
    </div>
  );
}

// Reference SearchInput: the borderless grey search field.
export function SearchInput({ value, onChange, placeholder = "Search" }: { value: string; onChange: (v: string) => void; placeholder?: string }) {
  return (
    <label className="flex h-9 items-center gap-2 rounded-sm bg-surface-subdued px-3 text-text-muted focus-within:shadow-focus">
      <Icon name="search" />
      <input
        type="search"
        aria-label={placeholder}
        placeholder={placeholder}
        value={value}
        onChange={(e) => onChange(e.target.value)}
        className="min-w-0 flex-1 appearance-none border-0 bg-transparent text-text placeholder:text-text-muted focus:outline-none [&::-webkit-search-cancel-button]:appearance-none"
      />
    </label>
  );
}

// Reference Card + Metric with the ChartCard footer (border-top, link left, note right).
export function MetricCard({ label, value, compare, link, note }: { label: string; value: ReactNode; compare?: ReactNode; link?: { label: string; onClick: () => void }; note?: ReactNode }) {
  return (
    <div className="grid content-between gap-3 rounded-md border border-border bg-surface p-4">
      <div className="grid gap-0.5">
        <span className="text-text-subdued">{label}</span>
        <span className="text-xl font-semibold text-text">{value}</span>
        {compare && <span className="text-xs text-text-muted">{compare}</span>}
      </div>
      {(link || note) && (
        <div className="flex justify-between gap-2 border-t border-border pt-2 text-xs text-text-muted">
          {link ? <button type="button" onClick={link.onClick} className="font-semibold text-link hover:text-text">{link.label}</button> : <span />}
          {note}
        </div>
      )}
    </div>
  );
}

// Reference Tabs: 20px apart over a strong rule; the current tab is purple with a 2px underline.
export function Tabs({ tabs, value, onChange }: { tabs: { id: string; label: string; count?: number }[]; value: string; onChange: (id: string) => void }) {
  return (
    <div className="mb-4 flex gap-5 overflow-x-auto border-b border-border-strong" role="tablist">
      {tabs.map((t) => (
        <button
          key={t.id}
          type="button"
          role="tab"
          aria-selected={value === t.id}
          onClick={() => onChange(t.id)}
          className={cx(
            "relative whitespace-nowrap py-2 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-focus",
            value === t.id ? "font-semibold text-link after:absolute after:inset-x-0 after:-bottom-px after:h-0.5 after:bg-primary" : "font-medium text-text-subdued hover:text-text",
          )}
        >
          {t.label}
          {t.count !== undefined && <span className="ml-1.5 font-normal text-text-muted">{t.count}</span>}
        </button>
      ))}
    </div>
  );
}

// --- progress ---------------------------------------------------------------------------------

// Reference Stepper: the vertical step list of setup flows. 16px nodes: green when done, purple when current;
// the current step can list its substeps.
export type Step = { label: string; status: "done" | "active" | "pending"; substeps?: { label: string; current?: boolean }[] };
export function Stepper({ steps }: { steps: Step[] }) {
  return (
    <ol className="grid gap-2">
      {steps.map((s, i) => (
        <Fragment key={s.label}>
          <li aria-current={s.status === "active" ? "step" : undefined} className={cx("flex items-center gap-2 text-[13px] font-semibold", s.status === "pending" ? "text-text-subdued" : "text-text")}>
            <span className={cx("grid h-4 w-4 flex-none place-items-center rounded-full text-[10px] leading-none", s.status === "done" ? "bg-success text-white" : s.status === "active" ? "bg-primary text-white" : "bg-border-strong text-text-subdued")}>
              {s.status === "done" ? <Icon name="check" className="h-3 w-3 [stroke-width:2]" /> : i + 1}
            </span>
            {s.label}
          </li>
          {s.substeps?.map((ss) => (
            <li
              key={ss.label}
              aria-current={ss.current ? "step" : undefined}
              className={cx("relative pl-6 text-[13px] font-medium before:absolute before:left-1.5 before:top-2 before:h-1 before:w-1 before:rounded-full", ss.current ? "text-link before:bg-primary" : "text-text-subdued before:bg-text-placeholder")}
            >
              {ss.label}
            </li>
          ))}
        </Fragment>
      ))}
    </ol>
  );
}

// Reference Timeline: status nodes on a hairline spine, each with a title, a muted time and optional detail.
export type TimelineItem = { title: ReactNode; time?: ReactNode; tone?: "neutral" | "success" | "danger" | "warning"; icon?: IconName; busy?: boolean; children?: ReactNode };
export function Timeline({ items }: { items: TimelineItem[] }) {
  return (
    <ol className="relative grid gap-4 before:absolute before:bottom-2.5 before:left-[7.5px] before:top-2.5 before:w-px before:bg-border-strong" aria-live="polite">
      {items.map((it, i) => {
        const tone = it.tone ?? "neutral";
        const icon: IconName = tone === "success" ? "check-circle" : tone === "danger" ? "x-circle" : tone === "warning" ? "alert" : it.icon ?? "clock";
        return (
          <li key={i} className="relative grid grid-cols-[16px_1fr] gap-3">
            <span className={cx("mt-0.5 grid h-4 w-4 place-items-center rounded-full bg-surface", { success: "text-success", danger: "text-danger", warning: "text-warning-fg", neutral: "text-text-muted" }[tone])}>
              {it.busy ? <Spinner /> : <Icon name={icon} />}
            </span>
            <div className="min-w-0">
              <div className="text-text">{it.title}</div>
              {it.time && <div className="text-xs text-text-muted">{it.time}</div>}
              {it.children}
            </div>
          </li>
        );
      })}
    </ol>
  );
}

// Reference RequestLog: one mono row per API call: status badge, method and path, and its time.
export function RequestLog({ entries }: { entries: { status: number | null; method: string; path: string; time: ReactNode }[] }) {
  return (
    <div className="grid">
      {entries.map((e, i) => (
        <div key={i} className="grid grid-cols-[auto_1fr_auto] items-center gap-3 border-b border-border py-1.5 font-mono text-[13px] leading-5">
          <Badge tone={!e.status ? "danger" : e.status < 300 ? "success" : e.status < 500 ? "warning" : "danger"}>{e.status ? `${e.status} ${e.status < 300 ? "OK" : "ERR"}` : "Blocked"}</Badge>
          <span className="min-w-0 truncate">{e.method} {e.path}</span>
          <time className="font-sans text-xs text-text-muted">{e.time}</time>
        </div>
      ))}
    </div>
  );
}

// Reference FocusHeader: the 52px bar of full-screen task pages: close, title, status and the actions.
export function FocusHeader({ title, status, actions, onClose }: { title: ReactNode; status?: ReactNode; actions?: ReactNode; onClose: () => void }) {
  return (
    <header className="sticky top-0 z-20 flex h-[52px] items-center gap-3 border-b border-border bg-surface px-4">
      <CloseButton onClick={onClose} />
      <span className="h-5 w-px bg-border-strong" />
      <span className="truncate font-semibold text-text">{title}</span>
      <div className="ml-auto flex shrink-0 items-center gap-3">
        {status && <span className="text-xs text-text-muted">{status}</span>}
        {actions}
      </div>
    </header>
  );
}

// --- code ----------------------------------------------------------------------------------

const ITEM = /^\s*# (\d)\. /;
const ITEM_NAMES: Record<string, string> = { "1": "API client", "2": "Auth setup", "3": "Users and usage", "4": "Error handling", "5": "Pagination", "6": "Logging" };
export function CodeBlock({ code, highlightItems }: { code: string; highlightItems?: boolean }) {
  const [copied, setCopied] = useState(false);
  const lines = code.split("\n");
  return (
    <div className="relative max-w-full rounded-md border border-border bg-surface-subdued">
      <div className="absolute right-2 top-2">
        <Button small onClick={() => navigator.clipboard?.writeText(code).then(() => setCopied(true))}>
          {copied ? "Copied" : "Copy"}
        </Button>
      </div>
      <pre className="code max-h-[560px] overflow-auto py-3">
        {lines.map((line, i) => {
          const m = highlightItems ? ITEM.exec(line) : null;
          const items = m ? line.match(/# (\d)\./g)?.map((x) => x[2]) ?? [] : [];
          return (
            <div key={i} className={cx("flex", m && "bg-primary-subtle")}>
              <span className="w-12 shrink-0 select-none pr-3 text-right text-text-placeholder">{i + 1}</span>
              <span className={cx("whitespace-pre pr-4", m && "border-l-2 border-primary pl-2 font-medium text-link")}>{line || " "}</span>
              {m && <span className="ml-auto mr-3 shrink-0 self-center">{items.map((n) => <Tag key={n}>{ITEM_NAMES[n]}</Tag>)}</span>}
            </div>
          );
        })}
      </pre>
    </div>
  );
}

// --- overlays -------------------------------------------------------------------------------

// Reference Drawer: a right-side sheet for creating one object without leaving the list, with a sticky footer.
export function Drawer({ open, title, eyebrow, onClose, footerStart, footer, width = 440, children }: {
  open: boolean;
  title: string;
  eyebrow?: string;
  onClose: () => void;
  footerStart?: ReactNode;
  footer?: ReactNode;
  width?: number;
  children: ReactNode;
}) {
  useEffect(() => {
    if (!open) return;
    const key = (e: KeyboardEvent) => e.key === "Escape" && onClose();
    window.addEventListener("keydown", key);
    return () => window.removeEventListener("keydown", key);
  }, [open, onClose]);
  if (!open) return null;
  return (
    <div className="fixed inset-0 z-50 flex justify-end bg-overlay" onClick={(e) => e.target === e.currentTarget && onClose()}>
      <aside role="dialog" aria-modal="true" aria-label={title} className="flex h-full max-w-full flex-col bg-surface shadow-modal" style={{ width }}>
        <div className="flex items-center justify-between gap-4 border-b border-border px-5 py-4">
          <div>
            {eyebrow && <div className="text-xs font-semibold text-link">{eyebrow}</div>}
            <h2 className="text-base font-bold text-text-heading">{title}</h2>
          </div>
          <CloseButton onClick={onClose} />
        </div>
        <div className="grid flex-1 content-start gap-5 overflow-y-auto p-5">{children}</div>
        {(footer || footerStart) && (
          <div className="flex items-center justify-between gap-3 border-t border-border px-5 py-3">
            <span>{footerStart}</span>
            <span className="flex flex-none gap-2">{footer}</span>
          </div>
        )}
      </aside>
    </div>
  );
}

// Reference Modal: a centred dialog over the grey-blue scrim; title, close x, body, right-aligned footer.
export function Modal({ open, title, onClose, children, footer, width = 480 }: { open: boolean; title: string; onClose: () => void; children: ReactNode; footer: ReactNode; width?: number }) {
  useEffect(() => {
    if (!open) return;
    const key = (e: KeyboardEvent) => e.key === "Escape" && onClose();
    window.addEventListener("keydown", key);
    return () => window.removeEventListener("keydown", key);
  }, [open, onClose]);
  if (!open) return null;
  return (
    <div className="fixed inset-0 z-[60] grid place-items-center bg-overlay px-4 py-8" onClick={(e) => e.target === e.currentTarget && onClose()}>
      <div role="dialog" aria-modal="true" aria-label={title} className="grid overflow-hidden rounded-md bg-surface shadow-modal" style={{ width: `min(100%, ${width}px)` }}>
        <div className="flex items-center justify-between gap-4 px-5 pt-4">
          <h2 className="text-base font-bold text-text-heading">{title}</h2>
          <CloseButton onClick={onClose} />
        </div>
        <div className="grid gap-4 px-5 pb-5 pt-3">{children}</div>
        <div className="flex items-center justify-end gap-2 border-t border-border px-5 py-3">{footer}</div>
      </div>
    </div>
  );
}

// Reference sd-close.
function CloseButton({ onClick }: { onClick: () => void }) {
  return (
    <button type="button" aria-label="Close" onClick={onClick} className="-m-1 grid rounded-badge p-1 text-text-subdued hover:bg-surface-subdued focus-visible:shadow-focus focus-visible:outline-none">
      <Icon name="x" />
    </button>
  );
}

let toastSetter: ((m: string | null) => void) | null = null;
export function toast(message: string) {
  toastSetter?.(message);
}
export function ToastHost() {
  const [message, setMessage] = useState<string | null>(null);
  useEffect(() => {
    toastSetter = setMessage;
    return () => {
      toastSetter = null;
    };
  }, []);
  useEffect(() => {
    if (!message) return;
    const t = setTimeout(() => setMessage(null), 3500);
    return () => clearTimeout(t);
  }, [message]);
  if (!message) return null;
  return (
    <div className="fixed bottom-6 left-1/2 z-50 inline-flex -translate-x-1/2 items-center gap-2 rounded-md bg-text px-3 py-2 font-medium text-white shadow-modal" role="status">
      <Icon name="check-circle" className="h-4 w-4 text-success-bg" />
      {message}
    </div>
  );
}

// --- forms ----------------------------------------------------------------------------------

// Reference Field: semibold label (with an Optional tag), the control, then the error or the help.
export function Field({ label, optional, help, error, children }: { label: string; optional?: boolean; help?: ReactNode; error?: string | null; children: ReactNode }) {
  return (
    <label className="grid gap-1.5">
      <span className="flex items-center gap-1.5 font-semibold text-text">
        {label}
        {optional && <Tag>Optional</Tag>}
      </span>
      {children}
      {error ? (
        <span role="alert" className="flex items-start gap-1 text-xs text-danger-fg">
          <Icon name="alert" className="h-3.5 w-3.5 text-danger" />
          {error}
        </span>
      ) : (
        help && <span className="text-xs text-text-muted">{help}</span>
      )}
    </label>
  );
}

// Reference sd-input. `large` is the 40px login field; `affix` is the reference input group ("$" before the value).
const INPUT = "border border-border-strong bg-surface text-text shadow-control transition-shadow placeholder:text-text-placeholder hover:border-border-hover focus:border-primary focus:shadow-focus focus:outline-none disabled:bg-surface-subdued disabled:text-text-muted disabled:shadow-none";

export function TextInput({ large, affix, className, ...props }: React.InputHTMLAttributes<HTMLInputElement> & { large?: boolean; affix?: string }) {
  if (affix)
    return (
      <div
        className={cx(
          "flex items-center overflow-hidden rounded-sm border border-border-strong bg-surface shadow-control hover:border-border-hover focus-within:border-primary focus-within:shadow-focus",
          large ? "h-10" : "h-8",
        )}
      >
        <span className="shrink-0 pl-2 text-text-subdued">{affix}</span>
        <input {...props} className={cx("h-full w-full min-w-0 border-0 bg-transparent px-2 text-text placeholder:text-text-placeholder focus:outline-none", className)} />
      </div>
    );
  return <input {...props} className={cx(large ? "h-10" : "h-8", "w-full rounded-sm px-2", INPUT, className)} />;
}

export function Textarea(props: React.TextareaHTMLAttributes<HTMLTextAreaElement>) {
  return <textarea {...props} className={cx("w-full rounded-sm px-2 py-1.5", INPUT)} />;
}

const MONTH_NAMES = ["January", "February", "March", "April", "May", "June", "July", "August", "September", "October", "November", "December"];
const pad2 = (n: number) => String(n).padStart(2, "0");

// The reference DatePicker (Monday-first calendar, popover) opened from an sd-input-style field.
// Days before `min` (an ISO date) show like the other months' days and can't be picked.
export function DateField({ value, onChange, placeholder = "Pick a date", min }: { value: string; onChange: (iso: string) => void; placeholder?: string; min?: string }) {
  const [open, setOpen] = useState(false);
  const now = new Date();
  const [month, setMonth] = useState(value ? value.slice(0, 7) : `${now.getFullYear()}-${pad2(now.getMonth() + 1)}`);
  const ref = useDismiss<HTMLDivElement>(open, () => setOpen(false));
  const [y, m] = month.split("-").map(Number);
  const lead = (new Date(y, m - 1, 1).getDay() + 6) % 7;
  const days = new Date(y, m, 0).getDate();
  const prevDays = new Date(y, m - 1, 0).getDate();
  const trail = (7 - ((lead + days) % 7)) % 7;
  const shift = (k: number) => {
    const d = new Date(y, m - 1 + k, 1);
    setMonth(`${d.getFullYear()}-${pad2(d.getMonth() + 1)}`);
  };
  const off = (n: number, key: string) => (
    <span key={key} className="h-7 leading-7 text-text-placeholder">
      {n}
    </span>
  );
  return (
    <div ref={ref} className="relative">
      <button type="button" aria-haspopup="dialog" aria-expanded={open} onClick={() => setOpen(!open)} className={cx("flex h-8 w-full items-center justify-between rounded-sm px-2 text-left", INPUT)}>
        <span className={value ? "text-text" : "text-text-placeholder"}>{value ? fmtDate(value) : placeholder}</span>
        <Icon name="calendar" className="h-4 w-4 text-text-subdued" />
      </button>
      {open && (
        <div role="dialog" aria-label="Choose a date" className="absolute left-0 top-full z-20 mt-1 grid gap-2 rounded-md bg-surface p-3 shadow-popover">
          <div className="flex items-center justify-between font-semibold text-text">
            <button type="button" aria-label="Previous month" onClick={() => shift(-1)} className="grid p-0.5 text-text-subdued">
              <Icon name="chev-left" />
            </button>
            {MONTH_NAMES[m - 1]} {y}
            <button type="button" aria-label="Next month" onClick={() => shift(1)} className="grid p-0.5 text-text-subdued">
              <Icon name="chev-right" />
            </button>
          </div>
          <div role="grid" className="grid grid-cols-[repeat(7,28px)] gap-0.5 text-center text-xs">
            {["Mo", "Tu", "We", "Th", "Fr", "Sa", "Su"].map((d) => (
              <span key={d} className="h-5 leading-5 text-text-muted">
                {d}
              </span>
            ))}
            {Array.from({ length: lead }, (_, i) => off(prevDays - lead + i + 1, `p${i}`))}
            {Array.from({ length: days }, (_, i) => {
              const iso = `${month}-${pad2(i + 1)}`;
              if (min && iso < min) return off(i + 1, iso);
              return (
                <button
                  key={iso}
                  type="button"
                  onClick={() => {
                    onChange(iso);
                    setOpen(false);
                  }}
                  className={cx("h-7 rounded-badge leading-7", iso === value ? "bg-primary font-semibold text-white" : "text-text hover:bg-surface-subdued")}
                >
                  {i + 1}
                </button>
              );
            })}
            {Array.from({ length: trail }, (_, i) => off(i + 1, `n${i}`))}
          </div>
        </div>
      )}
    </div>
  );
}

// --- savings chart (DESIGN.md §2.5) --------------------------------------------------------------

// Reference BreakdownBar: an 8px bar of segments 2px apart, then a legend of rows (swatch and label, value right).
export function BreakdownBar({ segments }: { segments: { label: string; value: number; display?: ReactNode; color: string }[] }) {
  const total = segments.reduce((sum, s) => sum + s.value, 0) || 1;
  return (
    <div className="grid gap-3">
      <div className="flex h-2 gap-0.5 overflow-hidden rounded-[2px]" role="img" aria-label={segments.map((s) => `${s.label}: ${s.value}`).join(", ")}>
        {segments.filter((s) => s.value > 0).map((s) => (
          <span key={s.label} className={cx("block h-full", s.color)} style={{ width: `${(100 * s.value) / total}%` }} />
        ))}
      </div>
      <div className="grid">
        {segments.map((s) => (
          <div key={s.label} className="flex h-[26px] items-center justify-between gap-2 text-[13px]">
            <span className="inline-flex items-center gap-2 text-neutral-fg">
              <span className={cx("h-2.5 w-2.5 rounded-[2px]", s.color)} />
              {s.label}
            </span>
            <span>{s.display ?? s.value}</span>
          </div>
        ))}
      </div>
    </div>
  );
}
