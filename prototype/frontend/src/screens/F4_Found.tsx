// F4 What we found: plain summary cards, the evidence drawer and conflict chips.
import { useEffect, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { api, type ConnectorDetail } from "../api";
import { Badge, Banner, Button, Card, Drawer, Field, Modal, PageHeader, StatusBadge, Tag, Textarea, cx } from "../components/ui";

const AUTH_LABEL: Record<string, string> = {
  bearer_token: "API token (bearer)",
  basic: "Username and password / token",
  api_key_header: "API key in a header",
  oauth_client_credentials: "OAuth client credentials",
};
const TIER: Record<string, string> = {
  T1: "T1 · last activity on each user",
  T2: "T2 · counted from activity records",
  T3: "T3 · no usage in the API",
};

export default function Found() {
  const { id } = useParams();
  const navigate = useNavigate();
  const [c, setC] = useState<ConnectorDetail | null>(null);
  const [drawer, setDrawer] = useState(false);
  const [hintOpen, setHintOpen] = useState(false);
  const [hint, setHint] = useState("");
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    api.get<ConnectorDetail>(`/api/connectors/${id}`).then(setC);
  }, [id]);

  if (!c) return null;
  if (!c.summary) {
    return (
      <>
        <PageHeader eyebrow="Connector" title={c.app} badge={<StatusBadge status={c.status} />} />
        {c.error && <Banner tone="danger" title="We couldn't build this connector">{c.error.message}</Banner>}
        <Button onClick={() => navigate(`/connect/${encodeURIComponent(c.app)}`)}>Try again</Button>
      </>
    );
  }
  const s = c.summary;
  const proved = c.evidence.filter((e) => e.verified).length;
  const unproved = c.warnings.filter((w) => w.startsWith("Not proved"));
  const warnings = c.warnings.filter((w) => !w.startsWith("Not proved"));

  const sendHint = async () => {
    setBusy(true);
    await api.post(`/api/connectors/${id}/hint`, { text: hint });
    navigate(`/connectors/${id}/build`);
  };

  return (
    <>
      <PageHeader
        eyebrow="What we found"
        title={c.app}
        badge={<StatusBadge status={c.status} />}
        actions={
          <>
            <Button onClick={() => setHintOpen(true)}>This looks wrong</Button>
            <Button variant="primary" onClick={() => navigate(`/connectors/${id}/connect`)}>Looks right</Button>
          </>
        }
      >
        Read from {s.host}. Nothing has run yet.
      </PageHeader>

      {c.ai_source && c.ai_source !== "Gemini" && <Banner tone="warning" title={c.ai_source}>This draft didn't come from a live AI call in this session.</Banner>}
      {unproved.length > 0 && (
        <Banner tone="warning" title="Some answers aren't proved by the docs yet">
          Check them in the evidence before trusting them. The test run will still catch anything wrong.
        </Banner>
      )}

      <div className="grid grid-cols-1 gap-4 md:grid-cols-2 lg:grid-cols-3">
        <Card title="Login" aside={<Tag>{AUTH_LABEL[s.login.type] ?? s.login.type}</Tag>}>
          <Line label="Role needed">{s.login.role_required ?? "—"}</Line>
          <Line label="Exact scopes">
            {s.login.scopes.length ? <div className="flex flex-wrap gap-1">{s.login.scopes.map((x) => <Tag key={x}>{x}</Tag>)}</div> : "None listed"}
          </Line>
        </Card>
        <Card title="Users">
          <Line label="Where they come from"><code className="code">GET {s.users.path}</code></Line>
          <Line label="Paging">{s.users.pagination}</Line>
          <Line label="Fields">{s.users.fields.join(", ")}</Line>
        </Card>
        <Card title="Usage" aside={<Badge tone={s.usage.tier === "T3" ? "warning" : "info"} icon={false}>{s.usage.tier}</Badge>}>
          <Line label="What it measures">
            {s.usage.label ?? "Nothing in the API"}
            {s.usage.proxy && <span className="ml-2"><Tag>proxy</Tag></span>}
          </Line>
          <Line label="How">{TIER[s.usage.tier]}{s.usage.window_days ? `, last ${s.usage.window_days} days` : ""}</Line>
          {s.usage.fallback === "sso_last_login" && <Line label="Fallback">Last login from SSO, labelled "from SSO, not from the app"</Line>}
        </Card>
        <Card title="Limits">
          <Line label="Rate limit">{s.limits.requests_per_minute} requests per minute</Line>
          {s.limits.plan_note && <Line label="Plan note">{s.limits.plan_note}</Line>}
          {c.conflicts.map((cf) => (
            <button key={cf.field} onClick={() => setDrawer(true)} className="mt-2">
              <Badge tone="info">{cf.values.length} sources disagree</Badge>
            </button>
          ))}
        </Card>
        <Card title="Warnings" className="md:col-span-2">
          {warnings.length ? (
            <ul className="list-disc space-y-1 pl-5">{warnings.map((w) => <li key={w}>{w}</li>)}</ul>
          ) : (
            <span className="text-text-muted">None</span>
          )}
        </Card>
      </div>

      <div className="mt-6 flex items-center gap-3">
        <Button onClick={() => setDrawer(true)}>View evidence</Button>
        <span className="text-text-muted">
          {proved} of {c.evidence.length} fields proved by a quote from the docs
        </span>
      </div>

      <Drawer open={drawer} title="Evidence" onClose={() => setDrawer(false)}>
        {c.conflicts.map((cf) => (
          <div key={cf.field} className="mb-4 rounded-md bg-info-bg p-3 text-info-fg">
            <div className="font-semibold">Sources disagree on {cf.field}</div>
            <ul className="mt-1 space-y-0.5">
              {cf.values.map((v) => (
                <li key={v.source}>
                  {String(v.value)} · <a href={v.source} target="_blank" rel="noreferrer" className="underline">{new URL(v.source).hostname}</a>
                </li>
              ))}
            </ul>
            <div className="mt-1">We used {String(cf.chosen)}. {cf.reason}</div>
          </div>
        ))}
        <ul className="space-y-4">
          {c.evidence.map((e) => (
            <li key={e.field} className="border-b border-border pb-4 last:border-0">
              <div className="flex items-center justify-between gap-2">
                <code className="code text-text-subdued">{e.field}</code>
                {e.verified ? <Badge tone="success">Verified</Badge> : <Badge tone="warning">Not proved</Badge>}
              </div>
              <div className="code mt-1 break-all text-text-heading">{typeof e.value === "string" ? e.value : JSON.stringify(e.value)}</div>
              {e.quote && <blockquote className="mt-2 border-l-2 border-border-strong pl-3 italic text-text-subdued">"{e.quote}"</blockquote>}
              {e.openapi_pointer && <div className="caption mt-1">OpenAPI: {e.openapi_pointer}</div>}
              {e.url && <a className="caption mt-1 block text-link underline" href={e.url} target="_blank" rel="noreferrer">{e.url}</a>}
              {!e.verified && e.problem && <div className={cx("caption mt-1", "text-warning-fg")}>{e.problem}</div>}
            </li>
          ))}
        </ul>
      </Drawer>

      <Modal
        open={hintOpen}
        title="What looks wrong?"
        onClose={() => setHintOpen(false)}
        footer={
          <>
            <Button onClick={() => setHintOpen(false)}>Cancel</Button>
            <Button variant="primary" busy={busy} disabled={!hint.trim()} onClick={sendHint}>Re-draft with this hint</Button>
          </>
        }
      >
        <Field label="Your hint" help="Emails, links with parameters, long numbers, names and tokens are removed before the AI sees it. 500 characters max.">
          <Textarea rows={4} maxLength={500} value={hint} onChange={(e) => setHint(e.target.value)} placeholder="For example: the users list is under /members, and it needs the admin role." />
        </Field>
      </Modal>
    </>
  );
}

function Line({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div className="mb-2 last:mb-0">
      <div className="caption">{label}</div>
      <div className="mt-0.5">{children}</div>
    </div>
  );
}
