import { useEffect, useState } from "react";
import { api, type LibraryRow } from "../api";
import { Badge, EmptyState, PageHeader, Table, Tag } from "../components/ui";

export default function LibraryList() {
  const [rows, setRows] = useState<LibraryRow[] | null>(null);
  useEffect(() => {
    api.get<LibraryRow[]>("/api/library").then(setRows);
  }, []);
  return (
    <>
      <PageHeader title="Platform library">Connectors checked by the platform team. You connect with your own token; your own test always runs first.</PageHeader>
      {rows &&
        (rows.length ? (
          <Table
            rows={rows}
            rowKey={(r) => r.id}
            columns={[
              { key: "app", header: "App", render: (r) => <span className="font-medium text-text-heading">{r.app}</span> },
              { key: "tier", header: "Usage tier", render: (r) => <Tag>{r.tier}</Tag> },
              { key: "v", header: "Version", render: (r) => `v${r.version}` },
              { key: "used", header: "Used by", render: (r) => r.used_by },
              { key: "health", header: "Health", render: (r) => <Badge tone="success">{r.health}</Badge> },
            ]}
          />
        ) : (
          <EmptyState>Nothing in the library yet. Connectors appear here after the platform team approves them.</EmptyState>
        ))}
    </>
  );
}
