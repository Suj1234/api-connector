// F7 Connector detail: status, last test run, what it reads, versions, the generated code and its data card.
// Built from the reference parts: Breadcrumb, PageHeader, Banner, Tabs, Card + DetailsList, Table, CodeBlock.
// Submit to library is built but hidden for now (PRD §15).
import { useEffect, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { api, type ConnectorDetail } from "../api";
import { Badge, Banner, Breadcrumb, Button, Card, CodeBlock, DetailsList, PageHeader, StatusBadge, Table, Tabs, Tag, fmtDate, pagingLabel } from "../components/ui";

const LOGIN: Record<string, string> = { bearer_token: "API token", basic: "Username and token", api_key_header: "API key in a header", oauth_client_credentials: "OAuth client credentials" };
const MADE_BY: Record<string, string> = { ai: "AI draft", repair: "Automatic repair", library: "Platform library", hand_written: "Hand-written spec" };

export default function Detail() {
  const { id } = useParams();
  const navigate = useNavigate();
  const [c, setC] = useState<ConnectorDetail | null>(null);
  const [tab, setTab] = useState("overview");
  const [code, setCode] = useState("");

  useEffect(() => {
    api.get<ConnectorDetail>(`/api/connectors/${id}`).then(setC);
    api.get<string>(`/api/connectors/${id}/code`).then(setCode).catch(() => setCode(""));
  }, [id]);

  if (!c || !c.summary) return null;

  const downloadCard = async () => {
    const text = await api.get<string>(`/api/connectors/${id}/data-card`);
    const url = URL.createObjectURL(new Blob([text], { type: "text/markdown" }));
    const a = Object.assign(document.createElement("a"), { href: url, download: `${c.app.toLowerCase()}-data-card.md` });
    a.click();
    URL.revokeObjectURL(url);
  };

  const run = c.last_run;
  const live = c.status.startsWith("live");
  const crumbs = [
    { label: "App inventory", onClick: () => navigate("/") },
    { label: c.app, onClick: () => navigate(`/apps/${encodeURIComponent(c.app)}`) },
  ];

  return (
    <>
      <PageHeader
        breadcrumb={<Breadcrumb items={crumbs} />}
        title={`${c.app} connector`}
        badge={
          <span className="flex items-center gap-2">
            <StatusBadge status={c.status} />
            {c.run_mode === "replay" && <Tag>Sample data</Tag>}
          </span>
        }
        actions={
          <>
            <Button onClick={downloadCard}>Download data card</Button>
            {!live && <Button variant="primary" onClick={() => navigate(`/connectors/${id}`)}>Continue setup</Button>}
          </>
        }
      >
        {c.summary.usage.label ?? "Users only"} · usage tier {c.summary.usage.tier}
      </PageHeader>

      {(c.status === "live_users_only" || c.token_owner_warning || c.confirm_note) && (
        <div className="mb-6 grid gap-3">
          {c.status === "live_users_only" && <Banner tone="warning" title="Live with users only">Usage is blocked by the token's role, scope or plan, or the app's API has none. A token with the right access turns it on.</Banner>}
          {c.token_owner_warning && <Banner tone="warning" title="Token owner leaving">{c.token_owner_warning}</Banner>}
          {c.confirm_note && <Banner tone="info" title="Note at go-live">{c.confirm_note}</Banner>}
        </div>
      )}

      <Tabs
        value={tab}
        onChange={setTab}
        tabs={[
          { id: "overview", label: "Overview" },
          { id: "code", label: "Generated code" },
          { id: "versions", label: "Versions", count: c.versions.length },
        ]}
      />

      {tab === "overview" && (
        <div className="grid grid-cols-1 gap-4 lg:grid-cols-[minmax(0,1fr)_320px]">
          <div className="grid content-start gap-4">
            <Card
              title="Last test run"
              aside={run && <Badge tone={run.exit_code === 0 ? (run.status === "partial" ? "warning" : "success") : "danger"}>{run.exit_code === 0 ? (run.status === "partial" ? "Users only" : "Passed") : "Failed"}</Badge>}
            >
              {run ? (
                <DetailsList
                  layout="rows"
                  items={[
                    ["Finished", fmtDate(run.finished_at)],
                    ["Users", run.summary?.users ?? null],
                    ["Data", run.run_mode === "replay" ? "Sample data (recorded answers, fake people)" : `${c.app}'s live API`],
                    ["Sandbox", run.sandbox === "docker" ? "Docker: no network except the app's host" : "Demo isolation (subprocess)"],
                    ["Problem", run.message],
                  ]}
                />
              ) : (
                <span className="text-text-muted">No run yet</span>
              )}
            </Card>
            <Card title="What it reads">
              <DetailsList
                layout="rows"
                items={[
                  ["Host", <code className="code" key="h">{c.summary.host}</code>],
                  ["Users", <code className="code" key="u">GET {c.summary.users.path}</code>],
                  ["Usage", c.summary.usage.path ? <code className="code" key="g">GET {c.summary.usage.path}</code> : c.summary.usage.fallback ? "SSO last login (fallback)" : "On the user record"],
                  ["Paging", pagingLabel(c.summary.users.pagination)],
                  ["Rate limit", `${c.summary.limits.requests_per_minute} requests per minute`],
                ]}
              />
            </Card>
          </div>
          <Card title="Details">
            <DetailsList
              items={[
                ["Version", c.version !== null ? `v${c.version}` : null],
                ["Login", LOGIN[c.summary.login.type] ?? c.summary.login.type],
                ["Role", c.summary.login.role_required],
                ["Scopes", c.summary.login.scopes.length ? <span className="flex flex-wrap gap-1" key="s">{c.summary.login.scopes.map((x) => <Tag key={x}>{x}</Tag>)}</span> : null],
                ["Token owner", c.token_owner_email],
                ["Evidence", c.evidence_pct === null || c.evidence_pct === undefined ? "None needed: not drafted by the AI" : `${c.evidence_pct}% proved by the docs`],
                ["Built from", c.from_library ? "Platform library" : c.ai_source === "Gemini" ? "AI draft from the API docs (Gemini)" : c.ai_source],
              ]}
            />
          </Card>
        </div>
      )}
      {tab === "code" && (code ? <CodeBlock code={code} highlightItems /> : <span className="text-text-muted">No code yet</span>)}
      {tab === "versions" && (
        <Table
          rows={c.versions}
          rowKey={(v) => v.version}
          columns={[
            { key: "v", header: "Version", render: (v) => <span className="font-semibold text-text">v{v.version}</span> },
            { key: "by", header: "Made by", render: (v) => MADE_BY[v.created_by] ?? v.created_by },
            { key: "at", header: "Created", render: (v) => fmtDate(v.created_at) },
          ]}
        />
      )}
    </>
  );
}
