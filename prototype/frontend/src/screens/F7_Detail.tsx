// F7 Connector detail: status, runs, versions, token owner, data card, generated code, library.
import { useEffect, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { api, type ConnectorDetail } from "../api";
import { Badge, Banner, Button, Card, CodeBlock, DetailsList, PageHeader, SectionTitle, StatusBadge, Table, Tabs, Tag, fmtDate, toast } from "../components/ui";

export default function Detail() {
  const { id } = useParams();
  const navigate = useNavigate();
  const [c, setC] = useState<ConnectorDetail | null>(null);
  const [tab, setTab] = useState("overview");
  const [code, setCode] = useState("");
  const [busy, setBusy] = useState(false);

  const load = () => api.get<ConnectorDetail>(`/api/connectors/${id}`).then(setC);
  useEffect(() => {
    load();
    api.get<string>(`/api/connectors/${id}/code`).then(setCode).catch(() => setCode(""));
  }, [id]); // eslint-disable-line react-hooks/exhaustive-deps

  if (!c || !c.summary) return null;

  const submit = async () => {
    setBusy(true);
    try {
      await api.post(`/api/connectors/${id}/submit-to-library`);
      toast("Submitted to the platform library for review");
      await load();
    } finally {
      setBusy(false);
    }
  };

  const downloadCard = async () => {
    const text = await api.get<string>(`/api/connectors/${id}/data-card`);
    const url = URL.createObjectURL(new Blob([text], { type: "text/markdown" }));
    const a = Object.assign(document.createElement("a"), { href: url, download: `${c.app.toLowerCase()}-data-card.md` });
    a.click();
    URL.revokeObjectURL(url);
  };

  const run = c.last_run;
  const live = c.status.startsWith("live");

  return (
    <>
      <PageHeader
        eyebrow="Connector"
        title={c.app}
        badge={<StatusBadge status={c.status} />}
        actions={
          <>
            <Button onClick={downloadCard}>Download data card</Button>
            {live && !c.from_library && !c.library && <Button variant="primary" busy={busy} onClick={submit}>Submit to library</Button>}
            {!live && <Button variant="primary" onClick={() => navigate(`/connectors/${id}/connect`)}>Continue setup</Button>}
          </>
        }
      >
        {c.summary.usage.label ?? "Users only"} · {c.summary.usage.tier}
        {c.run_mode === "replay" && <span className="ml-2"><Tag>Sample data</Tag></span>}
      </PageHeader>

      {c.library && <Banner tone={c.library.status === "approved" ? "success" : "info"} title={c.library.status === "approved" ? "In the platform library" : "Waiting for review by the platform team"}>Customer-specific values were removed. Other customers only see it after a platform engineer approves it, and their own test always runs first.</Banner>}
      {c.status === "live_users_only" && <Banner tone="warning" title="Live with users only">Usage is blocked by the token's role, scope or plan. A token with the right access turns it on.</Banner>}
      {c.token_owner_warning && <Banner tone="warning" title="Token owner leaving">{c.token_owner_warning}</Banner>}
      {c.confirm_note && <Banner tone="neutral" title="Note at go-live">{c.confirm_note}</Banner>}

      <Tabs value={tab} onChange={setTab} tabs={[{ id: "overview", label: "Overview" }, { id: "code", label: "Generated code" }, { id: "versions", label: "Versions", count: c.versions.length }]} />

      {tab === "overview" && (
        <div className="grid grid-cols-1 gap-6 lg:grid-cols-[1fr_280px]">
          <div>
            <Card title="Last test run" aside={run && <Badge tone={run.exit_code === 0 ? (run.status === "partial" ? "warning" : "success") : "danger"}>{run.exit_code === 0 ? (run.status === "partial" ? "Users only" : "Passed") : "Failed"}</Badge>}>
              {run ? (
                <DetailsList
                  items={[
                    ["Finished", fmtDate(run.finished_at)],
                    ["Users", run.summary?.users ?? "—"],
                    ["Sandbox", run.sandbox === "docker" ? "Docker (no network except the app's host)" : "Subprocess · demo isolation only"],
                    ["Mode", run.run_mode === "replay" ? "Sample data" : "Live"],
                    ...(run.message ? ([["Problem", run.message]] as [string, string][]) : []),
                  ]}
                />
              ) : (
                <span className="text-text-muted">No run yet</span>
              )}
            </Card>
            <SectionTitle>What it reads</SectionTitle>
            <DetailsList
              items={[
                ["Host", <code className="code" key="h">{c.summary.host}</code>],
                ["Users", <code className="code" key="u">GET {c.summary.users.path}</code>],
                ["Usage", c.summary.usage.path ? <code className="code" key="g">GET {c.summary.usage.path}</code> : c.summary.usage.fallback ? "SSO last login (fallback)" : "On the user record"],
                ["Rate limit", `${c.summary.limits.requests_per_minute} per minute`],
              ]}
            />
          </div>
          <aside className="rounded-md border border-border p-4">
            <div className="heading-sm mb-3">Details</div>
            <DetailsList
              items={[
                ["Status", <StatusBadge key="s" status={c.status} />],
                ["Version", c.version ?? "—"],
                ["Login", ({ bearer_token: "API token", basic: "Username and token", api_key_header: "API key header", oauth_client_credentials: "OAuth client credentials" } as Record<string, string>)[c.summary.login.type] ?? c.summary.login.type],
                ["Scopes", c.summary.login.scopes.join(", ") || "—"],
                ["Role", c.summary.login.role_required ?? "—"],
                ["Token owner", c.token_owner_email ?? "Not recorded"],
                ["Evidence", c.evidence_pct === null || c.evidence_pct === undefined ? "Hand-written or library" : `${c.evidence_pct}% proved by the docs`],
                ["Source", c.from_library ? "Platform library" : c.ai_source ?? "Built with AI"],
              ]}
            />
          </aside>
        </div>
      )}
      {tab === "code" && <div className="min-w-0"><CodeBlock code={code} highlightItems /></div>}
      {tab === "versions" && (
        <Table
          rows={c.versions}
          rowKey={(v) => v.version}
          columns={[
            { key: "v", header: "Version", render: (v) => `v${v.version}` },
            { key: "by", header: "Made by", render: (v) => ({ ai: "AI draft", repair: "Automatic repair", library: "Platform library" } as Record<string, string>)[v.created_by] ?? v.created_by },
            { key: "at", header: "Created", render: (v) => fmtDate(v.created_at) },
          ]}
        />
      )}
    </>
  );
}
