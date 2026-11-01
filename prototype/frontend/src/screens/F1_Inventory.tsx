// F1 App inventory: where the money decision starts.
// The reference list page: PageHeader, metric cards, CountTabs, FilterChip, Table + Pagination.
import { useEffect, useState } from "react";
import { useLocation, useNavigate, useSearchParams } from "react-router-dom";
import { api, type InventoryRow } from "../api";
import {
  Badge, Banner, Button, CountTabs, EmptyState, FilterChip, Icon, MetricCard, PageHeader, Pagination, Table, Tag, fmtDate, fmtMoney, type Tone,
} from "../components/ui";
import ConnectDrawer from "./F2_Library";

const PAGE_SIZE = 10;
const connected = (r: InventoryRow) => r.usage_status.startsWith("Connected");
const renewing = (r: InventoryRow) => r.days_to_renewal !== null && r.days_to_renewal >= 0 && r.days_to_renewal <= 90;
const VIEWS = [
  { value: "all", label: "All", test: () => true },
  { value: "none", label: "No usage data", test: (r: InventoryRow) => !connected(r) },
  { value: "connected", label: "Connected", test: connected },
  { value: "renewing", label: "Renewing in 90 days", test: renewing },
];
const spend = (list: InventoryRow[]) => list.reduce((sum, r) => sum + (r.annual_cost ?? 0), 0);
const share = (part: number, whole: number) => (whole ? `${Math.round((part / whole) * 100)}% of spend` : undefined);
const usageTone = (r: InventoryRow): Tone => (connected(r) ? "success" : r.usage_status === "Users only" ? "warning" : "neutral");
// A connector that isn't live yet: its build stopped, or setup isn't finished.
const unfinished = (r: InventoryRow): { label: string; tone: Tone } | null =>
  !r.connector || r.connector.status.startsWith("live") || r.connector.status === "paused"
    ? null
    : r.connector.status === "needs_help"
      ? { label: "Needs help", tone: "warning" }
      : { label: "Setup not finished", tone: "info" };

export default function Inventory() {
  const [rows, setRows] = useState<InventoryRow[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [view, setView] = useState("all");
  const [owner, setOwner] = useState("");
  const [page, setPage] = useState(0);
  const [params] = useSearchParams();
  const navigate = useNavigate();
  const { pathname } = useLocation();
  const q = (params.get("q") ?? "").trim().toLowerCase();

  const load = () => api.get<InventoryRow[]>("/api/inventory").then(setRows).catch((e: Error) => setError(e.message));
  useEffect(() => {
    load();
  }, []);
  // /connect and /connect/:app open the Add an app / Connect usage data drawer over this page.
  const drawer = pathname.startsWith("/connect") && (
    <ConnectDrawer
      onClose={() => navigate("/")}
      onSaved={() => {
        load();
        navigate("/");
      }}
    />
  );

  const header = (
    <PageHeader
      title="App inventory"
      actions={
        <Button variant="primary" onClick={() => navigate("/connect")}>
          <Icon name="plus" />
          Add an app
        </Button>
      }
    >
      Every app you pay for, and whether we can see who really uses it.
    </PageHeader>
  );
  if (!rows) return <>{header}{error && <Banner tone="danger" title="Couldn't load the inventory">{error}</Banner>}{drawer}</>;

  const pick = (v: string) => {
    setView(v);
    setPage(0);
  };
  const test = VIEWS.find((v) => v.value === view)!.test;
  const shown = rows.filter(
    (r) => test(r) && (!owner || r.owner === owner) && (!q || r.app.toLowerCase().includes(q) || (r.owner ?? "").toLowerCase().includes(q)),
  );
  const last = Math.max(0, Math.ceil(shown.length / PAGE_SIZE) - 1);
  const p = Math.min(page, last);
  const total = spend(rows);
  const on = rows.filter(connected);
  const off = rows.filter((r) => !connected(r));
  const next = rows.filter(renewing).sort((a, b) => a.days_to_renewal! - b.days_to_renewal!)[0];

  return (
    <>
      {header}
      <div className="grid grid-cols-1 gap-6">
        <div className="grid grid-cols-2 gap-4 lg:grid-cols-4">
          <MetricCard label="Annual spend" value={fmtMoney(total)} compare={`${rows.length} apps`} link={{ label: "View all", onClick: () => pick("all") }} note={`${rows.reduce((s, r) => s + (r.seats ?? 0), 0)} seats`} />
          <MetricCard label="With usage data" value={fmtMoney(spend(on))} compare={`${on.length} apps`} link={{ label: "View apps", onClick: () => pick("connected") }} note={share(spend(on), total)} />
          <MetricCard label="Without usage data" value={fmtMoney(spend(off))} compare={`${off.length} apps we can't check`} link={{ label: "View apps", onClick: () => pick("none") }} note={share(spend(off), total)} />
          <MetricCard
            label="Next renewal"
            value={next ? `${next.days_to_renewal} days` : "—"}
            compare={next ? `${next.app} · ${fmtDate(next.renewal_date)}` : "Nothing in the next 90 days"}
            link={next ? { label: "View apps", onClick: () => pick("renewing") } : undefined}
            note={next ? fmtMoney(next.annual_cost, true) : undefined}
          />
        </div>

        <div className="grid grid-cols-1 gap-4">
          <CountTabs value={view} onChange={pick} items={VIEWS.map((v) => ({ value: v.value, label: v.label, count: rows.filter(v.test).length }))} />
          <div className="flex flex-wrap items-center gap-2">
            <FilterChip
              label="Owner"
              value={owner}
              options={[...new Set(rows.map((r) => r.owner).filter((o): o is string => !!o))].sort()}
              onChange={(o) => {
                setOwner(o);
                setPage(0);
              }}
            />
          </div>
        </div>

        {shown.length ? (
          <Table
            rows={shown.slice(p * PAGE_SIZE, (p + 1) * PAGE_SIZE)}
            rowKey={(r) => r.app}
            onRow={(r) => navigate(`/apps/${encodeURIComponent(r.app)}`)}
            footer={
              <Pagination
                summary={shown.length <= PAGE_SIZE ? `${shown.length} result${shown.length === 1 ? "" : "s"}` : `Viewing ${p * PAGE_SIZE + 1}–${Math.min(shown.length, (p + 1) * PAGE_SIZE)} of ${shown.length} results`}
                hasPrevious={p > 0}
                hasNext={p < last}
                onPrevious={() => setPage(p - 1)}
                onNext={() => setPage(p + 1)}
              />
            }
            columns={[
              {
                key: "app",
                header: "App",
                render: (r) => (
                  <span className="flex items-center gap-2">
                    <span className="font-semibold text-text">{r.app}</span>
                    {r.connector?.sample && <Tag>Sample data</Tag>}
                  </span>
                ),
              },
              { key: "owner", header: "Owner", render: (r) => r.owner },
              { key: "spend", header: "Annual spend", align: "right", render: (r) => (r.annual_cost === null ? null : fmtMoney(r.annual_cost)) },
              { key: "seats", header: "Seats", align: "right", render: (r) => r.seats },
              {
                key: "renewal",
                header: "Renewal",
                render: (r) =>
                  r.renewal_date && (
                    <span className="inline-flex items-center gap-2">
                      {fmtDate(r.renewal_date)}
                      {renewing(r) && <Badge tone="warning">Renews in {r.days_to_renewal} days</Badge>}
                    </span>
                  ),
              },
              {
                key: "usage",
                header: "Usage data",
                render: (r) => {
                  const state = unfinished(r);
                  return state ? <Badge tone={state.tone}>{state.label}</Badge> : <Badge tone={usageTone(r)}>{r.usage_status}</Badge>;
                },
              },
              {
                key: "action",
                header: "",
                align: "right",
                render: (r) =>
                  r.connector && !unfinished(r) ? (
                    <></>
                  ) : (
                    <button
                      type="button"
                      onClick={(e) => {
                        e.stopPropagation(); // the row itself opens the app page
                        navigate(r.connector ? `/connectors/${r.connector.id}` : `/connect/${encodeURIComponent(r.app)}`);
                      }}
                      className="font-semibold text-link hover:text-text"
                    >
                      {r.connector ? "Continue setup" : "Connect usage data"}
                    </button>
                  ),
              },
            ]}
          />
        ) : (
          <EmptyState
            icon="search"
            title="No apps match these filters"
            action={
              <Button
                onClick={() => {
                  pick("all");
                  setOwner("");
                  navigate("/");
                }}
              >
                Clear filters
              </Button>
            }
          >
            Try another owner or a different search.
          </EmptyState>
        )}
      </div>
      {drawer}
    </>
  );
}
