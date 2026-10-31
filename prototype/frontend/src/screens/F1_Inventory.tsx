// F1 App inventory: where the money decision starts.
import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { api, type InventoryRow } from "../api";
import { Badge, Banner, Button, PageHeader, Table, fmtDate, fmtMoney, type Tone } from "../components/ui";

export default function Inventory() {
  const [rows, setRows] = useState<InventoryRow[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const navigate = useNavigate();

  useEffect(() => {
    api.get<InventoryRow[]>("/api/inventory").then(setRows).catch((e: Error) => setError(e.message));
  }, []);

  const usageTone = (row: InventoryRow): Tone =>
    row.usage_status.startsWith("Connected") ? "success" : row.usage_status === "Users only" ? "warning" : "neutral";

  return (
    <>
      <PageHeader title="App inventory" actions={<Button variant="primary" onClick={() => navigate("/connect")}>Add an app</Button>}>
        Every app you pay for, and whether we can see who really uses it.
      </PageHeader>
      {error && <Banner tone="danger" title="Couldn't load the inventory">{error}</Banner>}
      {rows && (
        <Table
          rows={rows}
          rowKey={(r) => r.app}
          columns={[
            { key: "app", header: "App", render: (r) => <span className="font-medium text-text-heading">{r.app}</span> },
            { key: "owner", header: "Owner", render: (r) => r.owner ?? "—" },
            { key: "spend", header: "Annual spend", align: "right", render: (r) => fmtMoney(r.annual_cost) },
            { key: "seats", header: "Seats", align: "right", render: (r) => r.seats ?? "—" },
            {
              key: "renewal",
              header: "Renewal",
              render: (r) => (
                <div className="flex items-center gap-2">
                  <span>{fmtDate(r.renewal_date)}</span>
                  {r.days_to_renewal !== null && r.days_to_renewal <= 90 && <Badge tone="warning">Renews in {r.days_to_renewal} days</Badge>}
                </div>
              ),
            },
            {
              key: "usage",
              header: "Usage data",
              render: (r) => (
                <div className="flex items-center gap-2">
                  <Badge tone={usageTone(r)}>{r.usage_status}</Badge>
                  {r.in_library && !r.connector && <Badge tone="info">In library</Badge>}
                </div>
              ),
            },
            {
              key: "action",
              header: "",
              align: "right",
              render: (r) =>
                r.native ? null : r.connector ? (
                  <Button small onClick={() => navigate(`/connectors/${r.connector!.id}`)}>Open</Button>
                ) : (
                  <Button small onClick={() => navigate(`/connect/${encodeURIComponent(r.app)}`)}>Connect usage data</Button>
                ),
            },
          ]}
        />
      )}
    </>
  );
}
