// The app page: one app from the inventory, with the users and usage its generated connector retrieved.
// Built from the reference parts: Breadcrumb, PageHeader, Card + Metric, Tabs, SearchInput, FilterChip,
// Table + Pagination, DetailsList, EmptyState.
import { useEffect, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { api, type AppUser, type AppUsers, type ConnectorDetail, type InventoryRow, type Savings } from "../api";
import {
  Badge, Breadcrumb, Button, Card, DetailsList, EmptyState, FilterChip, MetricCard, PageHeader, Pagination, SearchInput, StatusBadge, Table, Tabs, Tag,
  fmtDate, fmtMoney, type Tone,
} from "../components/ui";

const PAGE_SIZE = 25;
const STATUS: Record<AppUser["status"], { label: string; tone: Tone }> = {
  active: { label: "Active", tone: "success" },
  suspended: { label: "Suspended", tone: "warning" },
  deactivated: { label: "Deactivated", tone: "neutral" },
  invited: { label: "Invited", tone: "info" },
  unknown: { label: "Unknown", tone: "neutral" },
};
const usageTone = (s: string): Tone => (s.startsWith("Connected") ? "success" : s === "Users only" ? "warning" : "neutral");

export default function AppPage() {
  const { app = "" } = useParams();
  const navigate = useNavigate();
  const [row, setRow] = useState<InventoryRow | null | undefined>(undefined);
  const [connector, setConnector] = useState<ConnectorDetail | null>(null);
  const [data, setData] = useState<AppUsers | null>(null);
  const [sv, setSv] = useState<Savings | null>(null); // the cards use the savings step's own numbers
  const [tab, setTab] = useState("users");
  const [q, setQ] = useState("");
  const [status, setStatus] = useState("");
  const [page, setPage] = useState(0);

  useEffect(() => {
    api.get<InventoryRow[]>("/api/inventory").then((rows) => {
      const found = rows.find((r) => r.app === app) ?? null;
      setRow(found);
      if (found?.connector) {
        api.get<ConnectorDetail>(`/api/connectors/${found.connector.id}`).then(setConnector);
        api.get<AppUsers>(`/api/connectors/${found.connector.id}/users`).then(setData).catch(() => setData(null));
        api.get<Savings>(`/api/connectors/${found.connector.id}/savings`).then(setSv).catch(() => setSv(null));
      }
    });
  }, [app]);

  const back = [{ label: "App inventory", onClick: () => navigate("/") }];
  if (row === undefined) return null;
  if (row === null)
    return (
      <>
        <PageHeader breadcrumb={<Breadcrumb items={back} />} title={app} />
        <EmptyState icon="search" title="Not in your inventory" action={<Button onClick={() => navigate("/")}>Back to App inventory</Button>}>
          There's no app called {app} in your inventory.
        </EmptyState>
      </>
    );

  const users = data?.users ?? [];
  const has = users.length > 0;
  const live = !!connector?.status.startsWith("live");
  const setup = () => navigate(row.connector ? `/connectors/${row.connector.id}` : `/connect/${encodeURIComponent(app)}`);
  const setupLabel = row.connector ? "Continue setup" : "Connect usage data";

  const hasActivity = users.some((u) => u.last_active_at);
  const savings = has ? sv : null; // the same buckets and seats as the savings step, so the two never disagree
  const named = users.some((u) => u.name);
  // A usage column only when the API gives a number (Zendesk and Slack give a sign-in date: Last active shows it).
  const usageLabel = users.find((u) => u.usage_metric_value !== null && u.usage_metric_label)?.usage_metric_label ?? null;
  // Who holds a seat: the same rule as the savings preview (deactivated people and free guests don't).
  const holders = users.filter((u) => u.is_billable ?? ["unknown", "active", "invited"].includes(u.status)).length;

  const ql = q.trim().toLowerCase();
  const shown = users.filter((u) => (!status || STATUS[u.status].label === status) && (!ql || `${u.name ?? ""} ${u.email ?? ""}`.toLowerCase().includes(ql)));
  const last = Math.max(0, Math.ceil(shown.length / PAGE_SIZE) - 1);
  const p = Math.min(page, last);

  const notYet = (
    <EmptyState
      icon="search"
      title="No usage data yet"
      action={<Button variant="primary" onClick={setup}>{setupLabel}</Button>}
    >
      {connector?.status === "needs_help"
        ? `${app}'s connector stopped during setup${connector.error ? `: ${connector.error.message}` : "."} Continue setup to fix it.`
        : row.connector
          ? `${app}'s connector hasn't finished its test yet. Finish setup and its users show here.`
          : `Connect usage data and the generated connector pulls ${app}'s users and their usage here.`}
    </EmptyState>
  );

  return (
    <>
      <PageHeader
        breadcrumb={<Breadcrumb items={back} />}
        title={app}
        badge={
          <span className="flex items-center gap-2">
            {connector ? <StatusBadge status={connector.status} /> : <Badge tone={usageTone(row.usage_status)}>{row.usage_status}</Badge>}
            {data?.sample && <Tag>Sample data</Tag>}
          </span>
        }
        actions={!live && <Button variant="primary" onClick={setup}>{setupLabel}</Button>}
      >
        {[row.owner, row.renewal_date && `Renews ${fmtDate(row.renewal_date)}`].filter(Boolean).join(" · ")}
      </PageHeader>

      <div className="grid grid-cols-1 gap-6">
        <div className="grid grid-cols-2 gap-4 lg:grid-cols-4">
          <MetricCard label="Users" value={has ? users.length : "—"} compare={has ? (data?.sample ? "Sample data: fake people" : `From ${app}'s API`) : "Not connected yet"} />
          <MetricCard label="Inactive" value={savings ? savings.buckets.inactive : "—"} compare={savings ? savings.usage_label : "Not connected yet"} />
          <MetricCard
            label="Left the company"
            value={savings && !savings.missing.includes("HRIS") ? savings.buckets.left : "—"}
            compare={!savings ? "Not connected yet" : savings.missing.includes("HRIS") ? "No HR file yet" : "From HR data"}
          />
          <MetricCard
            label="Seats paid for"
            value={row.seats ?? "—"}
            compare={
              has && row.seats !== null
                ? `${savings?.never_assigned ?? Math.max(0, row.seats - holders)} seats nobody holds`
                : row.annual_cost !== null
                  ? fmtMoney(row.annual_cost, true)
                  : undefined
            }
          />
        </div>

        <div>
          <Tabs
            value={tab}
            onChange={setTab}
            tabs={[
              { id: "users", label: "Users", count: has ? users.length : undefined },
              { id: "connector", label: "Connector" },
              { id: "contract", label: "Contract" },
            ]}
          />

          {tab === "users" &&
            (has ? (
              <div className="grid grid-cols-1 gap-4">
                <div className="flex flex-wrap items-center gap-3">
                  <div className="w-full max-w-[320px]">
                    <SearchInput
                      value={q}
                      placeholder="Search by name or email"
                      onChange={(v) => {
                        setQ(v);
                        setPage(0);
                      }}
                    />
                  </div>
                  <FilterChip
                    label="Status"
                    value={status}
                    options={[...new Set(users.map((u) => STATUS[u.status].label))]}
                    onChange={(v) => {
                      setStatus(v);
                      setPage(0);
                    }}
                  />
                </div>
                {shown.length ? (
                  <Table
                    rows={shown.slice(p * PAGE_SIZE, (p + 1) * PAGE_SIZE)}
                    rowKey={(u) => u.external_id}
                    footer={
                      <Pagination
                        summary={shown.length <= PAGE_SIZE ? `${shown.length} users` : `Viewing ${p * PAGE_SIZE + 1}–${Math.min(shown.length, (p + 1) * PAGE_SIZE)} of ${shown.length} users`}
                        hasPrevious={p > 0}
                        hasNext={p < last}
                        onPrevious={() => setPage(p - 1)}
                        onNext={() => setPage(p + 1)}
                      />
                    }
                    columns={[
                      // Some APIs return no names (Calendly's sample data has none): then the email leads.
                      ...(named
                        ? [
                            { key: "name", header: "Name", render: (u: AppUser) => u.name && <span className="font-semibold text-text">{u.name}</span> },
                            { key: "email", header: "Email", render: (u: AppUser) => u.email },
                          ]
                        : [{ key: "email", header: "Email", render: (u: AppUser) => u.email && <span className="font-semibold text-text">{u.email}</span> }]),
                      ...(users.some((u) => u.role) ? [{ key: "role", header: "Role", render: (u: AppUser) => u.role }] : []),
                      { key: "status", header: "Status", render: (u) => <Badge tone={STATUS[u.status].tone}>{STATUS[u.status].label}</Badge> },
                      ...(hasActivity ? [{ key: "last", header: "Last active", render: (u: AppUser) => (u.last_active_at ? fmtDate(u.last_active_at) : null) }] : []),
                      ...(usageLabel
                        ? [{ key: "usage", header: usageLabel[0].toUpperCase() + usageLabel.slice(1), align: "right" as const, render: (u: AppUser) => (u.usage_available ? u.usage_metric_value : null) }]
                        : []),
                    ]}
                  />
                ) : (
                  <EmptyState icon="search" title="No users match" action={<Button onClick={() => { setQ(""); setStatus(""); }}>Clear filters</Button>}>
                    Try another name, or clear the status filter.
                  </EmptyState>
                )}
              </div>
            ) : (
              notYet
            ))}

          {tab === "connector" &&
            (connector ? (
              <Card title="Connector" aside={<Button small onClick={() => navigate(`/connectors/${connector.id}`)}>Open connector</Button>}>
                <DetailsList
                  layout="rows"
                  items={[
                    ["Status", <StatusBadge key="s" status={connector.status} />],
                    ["Data", connector.run_mode === "replay" ? "Sample data (recorded API answers, fake people)" : `${app}'s live API`],
                    ["Built from", connector.ai_source === "Gemini" ? "AI draft from the API docs (Gemini)" : connector.ai_source],
                    ["Last test", connector.last_run?.finished_at ? `${fmtDate(connector.last_run.finished_at)} · ${connector.last_run.exit_code === 0 ? "passed" : "failed"}` : null],
                    ["Users retrieved", connector.last_run?.summary?.users ?? null],
                    ["Usage tier", connector.tier],
                    ["API docs", connector.docs_url],
                    ["Version", connector.version !== null ? `v${connector.version}` : null],
                  ]}
                />
              </Card>
            ) : (
              notYet
            ))}

          {tab === "contract" && (
            <Card title="Contract">
              <DetailsList
                layout="rows"
                items={[
                  ["Owner", row.owner],
                  ["Annual spend", row.annual_cost !== null ? fmtMoney(row.annual_cost) : null],
                  ["Seats paid for", row.seats],
                  ["Price per seat", row.annual_cost !== null && row.seats ? `${fmtMoney(row.annual_cost / row.seats)} a year` : null],
                  ["Renewal date", row.renewal_date ? `${fmtDate(row.renewal_date)}${row.days_to_renewal !== null && row.days_to_renewal >= 0 ? ` · in ${row.days_to_renewal} days` : ""}` : null],
                ]}
              />
            </Card>
          )}
        </div>
      </div>
    </>
  );
}
