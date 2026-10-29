// F8 Platform internal: library review queue, fleet health and the Opportunity Map (sample data).
import { useEffect, useState } from "react";
import { api, type LibraryRow, type ReviewItem } from "../api";
import { Badge, Banner, Button, Card, CodeBlock, Drawer, EmptyState, PageHeader, Table, Tabs, Tag, fmtMoney, toast } from "../components/ui";

const OPPORTUNITIES = [
  { app: "Loom", customers: 41, spend: 1_240_000 },
  { app: "Miro", customers: 38, spend: 1_980_000 },
  { app: "Lucidchart", customers: 22, spend: 610_000 },
  { app: "Typeform", customers: 19, spend: 280_000 },
];

export default function Internal() {
  const [tab, setTab] = useState("queue");
  const [queue, setQueue] = useState<ReviewItem[]>([]);
  const [library, setLibrary] = useState<LibraryRow[]>([]);
  const [open, setOpen] = useState<ReviewItem | null>(null);
  const [busy, setBusy] = useState(false);

  const load = () => {
    api.get<ReviewItem[]>("/api/library/review-queue").then(setQueue);
    api.get<LibraryRow[]>("/api/library").then(setLibrary);
  };
  useEffect(load, []);

  const decide = async (item: ReviewItem, decision: "approve" | "reject") => {
    setBusy(true);
    await api.post(`/api/library/${item.id}/${decision}`, { note: null });
    toast(decision === "approve" ? `${item.app} approved to the library` : `${item.app} rejected`);
    setOpen(null);
    setBusy(false);
    load();
  };

  const pending = queue.filter((q) => q.status === "pending_review");
  return (
    <>
      <PageHeader eyebrow="Platform team" title="Connector library" />
      <Tabs
        value={tab}
        onChange={setTab}
        tabs={[{ id: "queue", label: "Review queue", count: pending.length }, { id: "fleet", label: "Fleet health" }, { id: "map", label: "Opportunity map" }]}
      />
      {tab === "queue" &&
        (queue.length ? (
          <Table
            rows={queue}
            rowKey={(q) => q.id}
            onRow={setOpen}
            columns={[
              { key: "app", header: "App", render: (q) => <span className="font-medium text-text-heading">{q.app}</span> },
              { key: "v", header: "Version", render: (q) => `v${q.version}` },
              { key: "tier", header: "Tier", render: (q) => <Tag>{q.tier}</Tag> },
              { key: "host", header: "Host", render: (q) => <code className="code">{q.host}</code> },
              { key: "flags", header: "Needs a look", render: (q) => (q.flags.length ? <Badge tone="warning">{q.flags.length} flags</Badge> : "—") },
              { key: "status", header: "Status", render: (q) => <Badge tone={q.status === "approved" ? "success" : q.status === "rejected" ? "danger" : "info"}>{q.status === "pending_review" ? "Waiting for review" : q.status === "approved" ? "Approved" : "Rejected"}</Badge> },
            ]}
          />
        ) : (
          <EmptyState>No connectors waiting for review.</EmptyState>
        ))}
      {tab === "fleet" &&
        (library.length ? (
          <Table
            rows={library}
            rowKey={(l) => l.id}
            columns={[
              { key: "app", header: "App", render: (l) => <span className="font-medium text-text-heading">{l.app}</span> },
              { key: "v", header: "Version", render: (l) => `v${l.version}` },
              { key: "used", header: "Used by", render: (l) => l.used_by },
              { key: "health", header: "Health", render: (l) => <Badge tone={l.health === "healthy" ? "success" : "danger"}>{l.health}</Badge> },
              { key: "canary", header: "Repairs", render: () => <span className="text-text-muted">Canary first, then everyone</span> },
            ]}
          />
        ) : (
          <EmptyState>Nothing in the library yet.</EmptyState>
        ))}
      {tab === "map" && (
        <>
          <Banner tone="warning" title="Sample data">Apps with no connector, ranked by total spend × customers. Real data comes from the inventory across tenants.</Banner>
          <Table
            rows={OPPORTUNITIES}
            rowKey={(o) => o.app}
            columns={[
              { key: "app", header: "App", render: (o) => <span className="font-medium text-text-heading">{o.app}</span> },
              { key: "c", header: "Customers paying for it", align: "right", render: (o) => o.customers },
              { key: "s", header: "Total spend", align: "right", render: (o) => fmtMoney(o.spend, true) },
            ]}
          />
        </>
      )}

      <Drawer open={open !== null} title={open ? `${open.app} v${open.version}` : ""} onClose={() => setOpen(null)}>
        {open && (
          <div className="space-y-4">
            {open.flags.map((f) => <Banner key={f} tone="warning">{f}</Banner>)}
            <Card title="Summary">
              <ul className="space-y-1 text-text-subdued">
                <li>Host: <code className="code">{open.host}</code> · GET only</li>
                <li>Users: <code className="code">{open.summary.users.path}</code></li>
                <li>Usage: {open.summary.usage.label ?? "none"} ({open.summary.usage.tier})</li>
                <li>Scopes: {open.summary.login.scopes.join(", ") || "—"}</li>
              </ul>
            </Card>
            <CodeBlock code={open.code} highlightItems />
            {open.status === "pending_review" && (
              <div className="flex justify-end gap-2">
                <Button variant="danger" busy={busy} onClick={() => decide(open, "reject")}>Reject</Button>
                <Button variant="primary" busy={busy} onClick={() => decide(open, "approve")}>Approve to library</Button>
              </div>
            )}
          </div>
        )}
      </Drawer>
    </>
  );
}
