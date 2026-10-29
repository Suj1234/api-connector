// F6 Savings preview: the cross-check with HR, SSO and contract data. Every number shows its source.
import { useEffect, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { api, type ConnectorDetail, type Savings } from "../api";
import { Banner, BreakdownBar, Button, Field, Metric, Modal, PageHeader, Table, Tabs, Tag, Textarea, fmtDate, fmtMoney, toast } from "../components/ui";

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

  if (!c || !s) return error ? <Banner tone="danger">{error}</Banner> : null;
  const usersOnly = c.last_run?.status === "partial";
  const live = c.status.startsWith("live");

  const goLive = async () => {
    setBusy(true);
    setError(null);
    try {
      await api.post(`/api/connectors/${id}/confirm`, { accept: true, users_only: usersOnly, note: note || null });
      toast(`${c.app} is live`);
      navigate(`/connectors/${id}/detail`);
    } catch (e) {
      setError((e as Error).message);
      setBusy(false);
    }
  };

  const appSource = `from ${c.app} API`;
  const usageSource = s.usage_source === "sso_fallback" ? "from SSO, not from the app" : `${s.usage_label}`;

  return (
    <>
      <PageHeader
        overline="Savings preview"
        title={c.app}
        actions={!live && <Button variant="primary" onClick={() => setConfirmOpen(true)}>{usersOnly ? "Go live with users only" : "Go live"}</Button>}
      >
        Usage: {s.usage_label}
        {s.run_mode === "replay" && <Tag>Sample data</Tag>}
      </PageHeader>

      {s.missing.length > 0 && <Banner tone="info" title={`Upload ${s.missing.join(", ")} data to see the full picture`}>Without HR data we can't tell who left the company.</Banner>}
      {s.needs_note && (
        <Banner tone="warning" title={`The user count differs from SSO by ${s.mismatch_pct}%`}>
          {s.billable_users} billable users in {c.app}, {s.sso_assigned} assigned in SSO. Going live needs a short note explaining the gap.
        </Banner>
      )}
      {s.token_owner_warning && <Banner tone="warning" title="Token owner leaving">{s.token_owner_warning}</Banner>}

      <div className="grid grid-cols-2 gap-4 lg:grid-cols-5">
        <Metric label="Users" value={s.users} source={appSource} />
        <Metric label="Left the company" value={s.buckets.left} source="from HRIS" tone={s.buckets.left ? "danger" : undefined} />
        <Metric label="Inactive" value={s.buckets.inactive} source={usageSource} tone={s.buckets.inactive ? "warning" : undefined} />
        <Metric label="Seats never assigned" value={s.never_assigned ?? "—"} source={`${s.seats ?? "—"} seats bought · from ${s.contract_source}`} />
        <Metric label="Recoverable before renewal" value={fmtMoney(s.recoverable_annual, true)} source={s.renewal_date ? `Renews ${fmtDate(s.renewal_date)} · in ${s.days_to_renewal} days` : "No renewal date"} />
      </div>

      <div className="mt-6 rounded-md border border-border p-4">
        <div className="heading-sm mb-3">Where every user lands</div>
        <BreakdownBar
          segments={[
            { label: "Left the company", value: s.buckets.left, color: "bg-chart-left" },
            { label: "Inactive", value: s.buckets.inactive, color: "bg-chart-inactive" },
            { label: "Never assigned (seats)", value: s.never_assigned ?? 0, color: "bg-chart-never" },
            { label: "Not in HR data", value: s.buckets.not_in_hr, color: "bg-chart-nothr" },
            { label: "Active", value: s.buckets.active, color: "bg-chart-active" },
            { label: "Connector's own account", value: s.buckets.excluded, color: "bg-chart-excluded" },
          ]}
        />
        <p className="caption mt-3">
          {s.recoverable_seats ?? "—"} recoverable seats × {fmtMoney(s.price_per_seat)} per seat ({fmtMoney(s.seats && s.price_per_seat ? s.seats * s.price_per_seat : null, true)} ÷ {s.seats ?? "—"} seats). Only people who left, inactive users and seats nobody holds count; people not in HR data never do.
          {s.usage_label.includes("proxy") && " Usage is a proxy: people who only attend meetings can show 0."}
        </p>
      </div>

      <div className="mt-6">
        <Tabs
          value={tab}
          onChange={setTab}
          tabs={["left", "inactive", "not_in_hr", "excluded", "active"].map((b) => ({ id: b, label: BUCKET_LABEL[b], count: s.buckets[b as keyof Savings["buckets"]] }))}
        />
        <Table
          rows={s.people.filter((p) => p.bucket === tab)}
          rowKey={(p) => `${p.email}-${p.name}`}
          columns={[
            { key: "name", header: "Name", render: (p) => p.name ?? "—" },
            { key: "email", header: "Email", render: (p) => p.email ?? "—" },
            { key: "usage", header: "Usage", align: "right", render: (p) => (p.usage_metric_value ?? "—") },
            { key: "last", header: "Last active", render: (p) => fmtDate(p.last_active_at) },
            { key: "why", header: "Why", render: (p) => <span className="text-text-subdued">{p.reason}</span> },
          ]}
        />
      </div>

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
        <p className="text-text-subdued">The connector will sync daily. Nobody's seat is removed automatically; you decide what to cut.</p>
        {s.needs_note && (
          <div className="mt-4">
            <Field label="Why the counts differ" help="Required: the count differs from SSO by more than 2%.">
              <Textarea rows={3} value={note} onChange={(e) => setNote(e.target.value)} />
            </Field>
          </div>
        )}
        {error && <div className="mt-3 text-xs text-danger-fg">{error}</div>}
      </Modal>
    </>
  );
}
