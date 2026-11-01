// F6 Check the savings, then Go live: the users cross-checked with HR, SSO and contract data. Every number says
// where it comes from. Going live is confirmed in a dialog and lands on the app's page.
import { useEffect, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { api, type ConnectorDetail, type Savings } from "../api";
import { Banner, BreakdownBar, Button, Card, Field, Metric, Modal, Table, Tabs, Tag, Textarea, fmtDate, fmtMoney, toast } from "../components/ui";
import { FlowPage } from "./Flow";

const BUCKET_LABEL: Record<string, string> = {
  left: "Left the company",
  inactive: "Inactive",
  active: "Active",
  not_in_hr: "Not in HR data",
  excluded: "Connector's own account",
  usage_unknown: "Usage unknown",
};

export default function SavingsPreview() {
  const { id } = useParams();
  const navigate = useNavigate();
  const [c, setC] = useState<ConnectorDetail | null>(null);
  const [s, setS] = useState<Savings | null>(null);
  const [tab, setTab] = useState("left");
  const [confirmOpen, setConfirmOpen] = useState(false);
  const [note, setNote] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    api.get<ConnectorDetail>(`/api/connectors/${id}`).then(setC);
    api.get<Savings>(`/api/connectors/${id}/savings`).then(setS).catch((e: Error) => setError(e.message));
  }, [id]);

  if (!c || !s) {
    return (
      <FlowPage app={c?.app ?? null} step="savings" title="Check the savings">
        {error && <Banner tone="danger" title="We couldn't work out the savings">{error}</Banner>}
      </FlowPage>
    );
  }
  const usersOnly = c.last_run?.status === "partial";
  const live = c.status.startsWith("live");

  const goLive = async () => {
    setBusy(true);
    setError(null);
    try {
      await api.post(`/api/connectors/${id}/confirm`, { accept: true, users_only: usersOnly, note: note || null });
      toast(`${c.app} is live`);
      navigate(`/apps/${encodeURIComponent(c.app)}`);
    } catch (e) {
      setError((e as Error).message);
      setBusy(false);
    }
  };

  const usageSource = s.usage_source === "sso_fallback" ? "From SSO, not from the app" : s.usage_label;
  const buckets = ["left", "inactive", "not_in_hr", "excluded", "active", "usage_unknown"].filter((b) => s.buckets[b as keyof Savings["buckets"]] > 0);
  const shown = buckets.includes(tab) ? tab : buckets[0];

  return (
    <FlowPage
      app={c.app}
      step={live ? "live" : "savings"}
      status={live ? "Live" : `Tested · version ${c.version ?? 1}`}
      actions={!live && <Button variant="primary" onClick={() => setConfirmOpen(true)}>{usersOnly ? "Go live with users only" : "Go live"}</Button>}
      title="Check the savings"
      intro={
        <span className="inline-flex flex-wrap items-center gap-2">
          Who uses {c.app}, cross-checked with your HR, SSO and contract files. Nobody's seat is removed automatically.
          {s.run_mode === "replay" && <Tag>Sample data</Tag>}
        </span>
      }
    >
      {s.missing.length > 0 && <Banner tone="info" title={`Upload ${s.missing.join(", ")} data to see the full picture`}>Without HR data we can't tell who left the company.</Banner>}
      {s.needs_note && (
        <Banner tone="warning" title={`The user count differs from SSO by ${s.mismatch_pct}%`}>
          {s.billable_users} billable users in {c.app}, {s.sso_assigned} assigned in SSO. Going live needs a short note explaining the gap.
        </Banner>
      )}
      {s.token_owner_warning && <Banner tone="warning" title="Token owner leaving">{s.token_owner_warning}</Banner>}

      <Card>
        <div className="grid grid-cols-2 gap-6 lg:grid-cols-5">
          <Metric label="Users" value={s.users} compare={`From ${c.app}'s API`} />
          <Metric label="Left the company" value={s.buckets.left} compare="From HR data" />
          <Metric label="Inactive" value={s.buckets.inactive} compare={usageSource} />
          <Metric label="Seats nobody holds" value={s.never_assigned ?? "—"} compare={`${s.seats ?? "—"} seats bought · from ${s.contract_source}`} />
          <Metric
            label="Recoverable before renewal"
            value={fmtMoney(s.recoverable_annual, true)}
            compare={s.renewal_date ? `Renews ${fmtDate(s.renewal_date)} · in ${s.days_to_renewal} days` : "No renewal date"}
          />
        </div>
      </Card>

      <Card title="Where every user lands">
        <BreakdownBar
          segments={[
            { label: "Left the company", value: s.buckets.left, color: "bg-chart-left" },
            { label: "Inactive", value: s.buckets.inactive, color: "bg-chart-inactive" },
            { label: "Seats nobody holds", value: s.never_assigned ?? 0, color: "bg-chart-never" },
            { label: "Not in HR data", value: s.buckets.not_in_hr, color: "bg-chart-nothr" },
            { label: "Active", value: s.buckets.active, color: "bg-chart-active" },
            { label: "Connector's own account", value: s.buckets.excluded, color: "bg-chart-excluded" },
          ]}
        />
        <p className="mt-3 text-text-muted">
          {s.recoverable_seats ?? "—"} recoverable seats × {fmtMoney(s.price_per_seat)} a seat ({fmtMoney(s.seats && s.price_per_seat ? s.seats * s.price_per_seat : null, true)} ÷ {s.seats ?? "—"} seats).
          Only people who left, inactive people and seats nobody holds count; people not in HR data never do.
          {s.usage_label.includes("proxy") && " Usage is a proxy: people who only attend meetings can show 0."}
        </p>
      </Card>

      {buckets.length > 0 && (
        <div>
          <Tabs value={shown} onChange={setTab} tabs={buckets.map((b) => ({ id: b, label: BUCKET_LABEL[b], count: s.buckets[b as keyof Savings["buckets"]] }))} />
          <Table
            rows={s.people.filter((p) => p.bucket === shown)}
            rowKey={(p) => `${p.email}-${p.name}`}
            columns={[
              ...(s.people.some((p) => p.name) ? [{ key: "name", header: "Name", render: (p: Savings["people"][number]) => p.name && <span className="font-semibold text-text">{p.name}</span> }] : []),
              { key: "email", header: "Email", render: (p) => p.email },
              { key: "usage", header: "Usage", align: "right" as const, render: (p) => p.usage_metric_value },
              { key: "last", header: "Last active", render: (p) => (p.last_active_at ? fmtDate(p.last_active_at) : null) },
              { key: "why", header: "Why", render: (p) => <span className="text-text-subdued">{p.reason}</span> },
            ]}
          />
        </div>
      )}

      <Modal
        open={confirmOpen}
        title={usersOnly ? "Go live with users only?" : `Go live with ${c.app}?`}
        onClose={() => setConfirmOpen(false)}
        footer={
          <>
            <Button onClick={() => setConfirmOpen(false)}>Cancel</Button>
            <Button variant="primary" busy={busy} disabled={s.needs_note && !note.trim()} onClick={goLive}>{usersOnly ? "Go live with users only" : "Go live"}</Button>
          </>
        }
      >
        <div className="grid gap-4">
          <p className="text-text-subdued">
            The connector syncs {c.app}'s users every day, and its users and usage show on {c.app}'s page. Nobody's seat is removed automatically; you decide what to cut.
          </p>
          {s.needs_note && (
            <Field label="Why the counts differ" help="Needed because the count differs from SSO by more than 2%.">
              <Textarea rows={3} value={note} onChange={(e) => setNote(e.target.value)} />
            </Field>
          )}
          {error && <Banner tone="danger">{error}</Banner>}
        </div>
      </Modal>
    </FlowPage>
  );
}
