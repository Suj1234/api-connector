// The DESIGN.md components (§6). Tokens only; no raw colours.
import { useEffect, useState, type ReactNode } from "react";

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

// --- buttons ----------------------------------------------------------------------------

type ButtonProps = {
  children: ReactNode;
  variant?: "primary" | "secondary" | "ghost" | "danger";
  small?: boolean;
  disabled?: boolean;
  busy?: boolean;
  onClick?: () => void;
  type?: "button" | "submit";
};
export function Button({ children, variant = "secondary", small, disabled, busy, onClick, type = "button" }: ButtonProps) {
  const styles = {
    primary: "bg-primary text-white hover:bg-primary-hover active:bg-primary-pressed border border-primary",
    secondary: "bg-surface text-text-heading border border-border-strong hover:bg-surface-subdued",
    ghost: "bg-transparent text-link hover:bg-surface-subdued border border-transparent",
    danger: "bg-danger text-white border border-danger hover:opacity-90",
  }[variant];
  return (
    <button
      type={type}
      onClick={onClick}
      disabled={disabled || busy}
      className={cx(
        "inline-flex items-center gap-2 rounded-sm font-medium whitespace-nowrap transition-colors disabled:opacity-50 disabled:cursor-not-allowed",
        small ? "h-7 px-2.5 text-xs" : "h-8 px-3",
        styles,
      )}
    >
      {busy && <Spinner light={variant === "primary" || variant === "danger"} />}
      {children}
    </button>
  );
}

export function Spinner({ light }: { light?: boolean }) {
  return (
    <span
      aria-hidden
      className={cx("inline-block h-3.5 w-3.5 animate-spin rounded-full border-2 border-t-transparent", light ? "border-white" : "border-primary")}
      style={{ borderTopColor: "transparent" }}
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
const ICONS: Record<Tone, string> = { success: "✓", danger: "✕", warning: "!", info: "i", neutral: "" };

export function Badge({ tone = "neutral", children, icon = true }: { tone?: Tone; children: ReactNode; icon?: boolean }) {
  return (
    <span className={cx("inline-flex items-center gap-1 rounded-badge px-1.5 py-0.5 text-xs font-medium", TONES[tone])}>
      {icon && ICONS[tone] && <span aria-hidden className="text-[10px] font-semibold">{ICONS[tone]}</span>}
      {children}
    </span>
  );
}

export function Tag({ children }: { children: ReactNode }) {
  return <span className="inline-flex rounded-badge bg-neutral-bg px-1.5 py-0.5 text-xs text-neutral-fg">{children}</span>;
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

export function PageHeader({ overline, title, badge, actions, children }: { overline?: string; title: string; badge?: ReactNode; actions?: ReactNode; children?: ReactNode }) {
  return (
    <div className="mb-6 flex items-start justify-between gap-6">
      <div>
        {overline && <div className="overline mb-1">{overline}</div>}
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

export function SectionTitle({ children, action }: { children: ReactNode; action?: ReactNode }) {
  return (
    <div className="mb-3 mt-8 flex items-end justify-between border-b border-border-strong pb-2">
      <h2 className="heading">{children}</h2>
      {action}
    </div>
  );
}

export function Card({ title, children, aside, className }: { title?: ReactNode; children: ReactNode; aside?: ReactNode; className?: string }) {
  return (
    <section className={cx("rounded-md border border-border bg-surface p-4", className)}>
      {title && (
        <div className="mb-3 flex items-center justify-between gap-2">
          <h3 className="heading-sm">{title}</h3>
          {aside}
        </div>
      )}
      {children}
    </section>
  );
}

export function Metric({ label, value, source, tone }: { label: string; value: ReactNode; source?: string; tone?: "danger" | "warning" }) {
  return (
    <div className="rounded-md border border-border bg-surface p-4">
      <div className="text-text-subdued">{label}</div>
      <div className={cx("metric mt-1", tone === "danger" && "text-danger-fg", tone === "warning" && "text-warning-fg")}>{value}</div>
      {source && <div className="caption mt-1">{source}</div>}
    </div>
  );
}

export function Banner({ tone = "info", title, children, action }: { tone?: Tone; title?: string; children?: ReactNode; action?: ReactNode }) {
  return (
    <div className={cx("mb-4 flex items-start justify-between gap-4 rounded-md px-4 py-3", TONES[tone])} role={tone === "danger" ? "alert" : "status"}>
      <div>
        {title && <div className="font-semibold">{title}</div>}
        {children && <div className={cx(title && "mt-0.5")}>{children}</div>}
      </div>
      {action}
    </div>
  );
}

export function DetailsList({ items }: { items: [string, ReactNode][] }) {
  return (
    <dl className="space-y-3">
      {items.map(([label, value]) => (
        <div key={label}>
          <dt className="caption">{label}</dt>
          <dd className="mt-0.5 break-words">{value ?? "—"}</dd>
        </div>
      ))}
    </dl>
  );
}

export function EmptyState({ children, action }: { children: ReactNode; action?: ReactNode }) {
  return (
    <div className="rounded-md border border-dashed border-border-strong bg-surface-subdued px-6 py-10 text-center">
      <div className="text-text-subdued">{children}</div>
      {action && <div className="mt-4">{action}</div>}
    </div>
  );
}

// --- tables, tabs ---------------------------------------------------------------------------

export function Table<T>({ rows, columns, rowKey, onRow }: {
  rows: T[];
  columns: { key: string; header: string; render: (row: T) => ReactNode; align?: "right" }[];
  rowKey: (row: T) => string | number;
  onRow?: (row: T) => void;
}) {
  return (
    <div className="overflow-x-auto rounded-md border border-border">
      <table className="w-full border-collapse">
        <thead className="bg-surface-subdued">
          <tr>
            {columns.map((c) => (
              <th key={c.key} className={cx("border-b border-border px-3 py-2 text-xs font-medium text-text-subdued", c.align === "right" ? "text-right" : "text-left")}>
                {c.header}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map((row) => (
            <tr key={rowKey(row)} onClick={onRow ? () => onRow(row) : undefined} className={cx("border-b border-border last:border-0", onRow && "cursor-pointer hover:bg-surface-subdued")}>
              {columns.map((c) => (
                <td key={c.key} className={cx("px-3 py-2.5 align-middle", c.align === "right" && "text-right")}>
                  {c.render(row)}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

export function Tabs({ tabs, value, onChange }: { tabs: { id: string; label: string; count?: number }[]; value: string; onChange: (id: string) => void }) {
  return (
    <div className="mb-4 flex gap-6 border-b border-border" role="tablist">
      {tabs.map((t) => (
        <button
          key={t.id}
          role="tab"
          aria-selected={value === t.id}
          onClick={() => onChange(t.id)}
          className={cx("-mb-px border-b-2 pb-2 font-medium", value === t.id ? "border-primary text-text-heading" : "border-transparent text-text-subdued hover:text-text")}
        >
          {t.label}
          {t.count !== undefined && <span className="ml-1.5 text-text-muted">{t.count}</span>}
        </button>
      ))}
    </div>
  );
}

// --- progress ---------------------------------------------------------------------------------

export type StepState = "waiting" | "running" | "done" | "failed" | "warn";
export function Stepper({ steps }: { steps: { label: string; state: StepState; detail?: string }[] }) {
  return (
    <ol className="space-y-0" aria-live="polite">
      {steps.map((s, i) => (
        <li key={s.label} className="flex gap-3">
          <div className="flex flex-col items-center">
            <span
              className={cx(
                "flex h-6 w-6 items-center justify-center rounded-full border text-xs font-semibold",
                s.state === "done" && "border-primary bg-primary text-white",
                s.state === "running" && "border-primary bg-primary-subtle text-primary",
                s.state === "failed" && "border-danger bg-danger-bg text-danger-fg",
                s.state === "warn" && "border-warning-fg bg-warning-bg text-warning-fg",
                s.state === "waiting" && "border-border-strong bg-surface text-text-muted",
              )}
            >
              {s.state === "done" ? "✓" : s.state === "failed" ? "✕" : s.state === "warn" ? "!" : s.state === "running" ? <Spinner /> : i + 1}
            </span>
            {i < steps.length - 1 && <span className="my-1 w-px flex-1 bg-border-strong" style={{ minHeight: 16 }} />}
          </div>
          <div className="pb-4">
            <div className={cx("font-medium", s.state === "waiting" ? "text-text-muted" : "text-text-heading")}>{s.label}</div>
            {s.detail && <div className="caption mt-0.5">{s.detail}</div>}
          </div>
        </li>
      ))}
    </ol>
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
              <span className={cx("whitespace-pre pr-4", m && "border-l-2 border-primary pl-2 font-medium text-primary")}>{line || " "}</span>
              {m && <span className="ml-auto mr-3 shrink-0 self-center">{items.map((n) => <Tag key={n}>{ITEM_NAMES[n]}</Tag>)}</span>}
            </div>
          );
        })}
      </pre>
    </div>
  );
}

// --- overlays -------------------------------------------------------------------------------

export function Drawer({ open, title, onClose, children }: { open: boolean; title: string; onClose: () => void; children: ReactNode }) {
  useEffect(() => {
    const key = (e: KeyboardEvent) => e.key === "Escape" && onClose();
    window.addEventListener("keydown", key);
    return () => window.removeEventListener("keydown", key);
  }, [onClose]);
  if (!open) return null;
  return (
    <div className="fixed inset-0 z-40 flex justify-end" role="dialog" aria-modal aria-label={title}>
      <div className="absolute inset-0 bg-primary opacity-20" onClick={onClose} />
      <aside className="relative flex h-full w-[560px] max-w-full flex-col bg-surface shadow-float">
        <div className="flex items-center justify-between border-b border-border px-6 py-4">
          <h2 className="heading-sm">{title}</h2>
          <Button variant="ghost" small onClick={onClose}>Close</Button>
        </div>
        <div className="flex-1 overflow-y-auto px-6 py-4">{children}</div>
      </aside>
    </div>
  );
}

export function Modal({ open, title, onClose, children, footer }: { open: boolean; title: string; onClose: () => void; children: ReactNode; footer: ReactNode }) {
  if (!open) return null;
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center" role="dialog" aria-modal aria-label={title}>
      <div className="absolute inset-0 bg-primary opacity-20" onClick={onClose} />
      <div className="relative w-[480px] max-w-[92vw] rounded-md bg-surface shadow-float">
        <div className="border-b border-border px-6 py-4"><h2 className="heading-sm">{title}</h2></div>
        <div className="px-6 py-4">{children}</div>
        <div className="flex justify-end gap-2 border-t border-border px-6 py-3">{footer}</div>
      </div>
    </div>
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
    <div className="fixed bottom-6 left-1/2 z-50 -translate-x-1/2 rounded-md bg-primary px-4 py-2.5 text-white shadow-float" role="status">
      {message}
    </div>
  );
}

// --- forms ----------------------------------------------------------------------------------

export function Field({ label, help, error, children }: { label: string; help?: ReactNode; error?: string | null; children: ReactNode }) {
  return (
    <label className="block">
      <span className="mb-1 block font-medium text-text-subdued">{label}</span>
      {children}
      {help && !error && <span className="caption mt-1 block">{help}</span>}
      {error && <span className="mt-1 block text-xs text-danger-fg">{error}</span>}
    </label>
  );
}

export function TextInput(props: React.InputHTMLAttributes<HTMLInputElement>) {
  return (
    <input
      {...props}
      className={cx(
        "h-8 w-full rounded-sm border border-border-strong bg-surface px-2.5 text-text placeholder:text-text-placeholder focus:border-primary focus:outline-none",
        props.className,
      )}
    />
  );
}

export function Textarea(props: React.TextareaHTMLAttributes<HTMLTextAreaElement>) {
  return (
    <textarea
      {...props}
      className="w-full rounded-sm border border-border-strong bg-surface px-2.5 py-2 text-text placeholder:text-text-placeholder focus:border-primary focus:outline-none"
    />
  );
}

// --- savings chart (DESIGN.md §2.5) --------------------------------------------------------------

export function BreakdownBar({ segments }: { segments: { label: string; value: number; color: string }[] }) {
  const total = segments.reduce((sum, s) => sum + s.value, 0) || 1;
  return (
    <div>
      <div className="flex h-3 w-full overflow-hidden rounded-full bg-surface-subdued" role="img" aria-label={segments.map((s) => `${s.label}: ${s.value}`).join(", ")}>
        {segments.filter((s) => s.value > 0).map((s) => (
          <div key={s.label} className={s.color} style={{ width: `${(100 * s.value) / total}%` }} />
        ))}
      </div>
      <ul className="mt-3 flex flex-wrap gap-x-6 gap-y-2">
        {segments.map((s) => (
          <li key={s.label} className="flex items-center gap-2">
            <span className={cx("h-2.5 w-2.5 rounded-full", s.color)} />
            <span className="text-text-subdued">{s.label}</span>
            <span className="font-semibold text-text-heading">{s.value}</span>
          </li>
        ))}
      </ul>
    </div>
  );
}
