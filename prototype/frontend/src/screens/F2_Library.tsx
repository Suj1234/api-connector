// F2 Library check, and F3's docs form when the app isn't in the library.
import { useEffect, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { api, type InventoryRow } from "../api";
import { Banner, Button, Card, Field, PageHeader, TextInput } from "../components/ui";

const KNOWN_DOCS: Record<string, string> = {
  calendly: "https://developer.calendly.com/api-docs",
  zendesk: "https://developer.zendesk.com/api-reference/ticketing/users/users/",
  notion: "https://developers.notion.com/reference/get-users",
};

export default function LibraryCheck() {
  const { app = "" } = useParams();
  const navigate = useNavigate();
  const [row, setRow] = useState<InventoryRow | null>(null);
  const [appName, setAppName] = useState(app);
  const [docsUrl, setDocsUrl] = useState(KNOWN_DOCS[app.toLowerCase()] ?? "");
  const [file, setFile] = useState<File | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api.get<InventoryRow[]>("/api/inventory").then((rows) => setRow(rows.find((r) => r.app === app) ?? null));
  }, [app]);

  const create = async (fromLibrary: boolean) => {
    setBusy(true);
    setError(null);
    const form = new FormData();
    form.set("app_name", appName.trim() || app);
    if (fromLibrary && row?.library_spec_id) form.set("from_library_spec_id", String(row.library_spec_id));
    if (!fromLibrary) {
      if (docsUrl) form.set("docs_url", docsUrl.trim());
      if (file) form.set("openapi_file", file);
    }
    try {
      const { id } = await api.form<{ id: number }>("/api/connectors", form);
      navigate(fromLibrary ? `/connectors/${id}/connect` : `/connectors/${id}/build`);
    } catch (e) {
      setError((e as Error).message);
      setBusy(false);
    }
  };

  return (
    <>
      <PageHeader eyebrow="Connect usage data" title={app || "New app"} />
      {error && <Banner tone="danger" title="That didn't work">{error}</Banner>}
      {row?.in_library ? (
        <div className="max-w-[640px] space-y-4">
          <Banner tone="info" title={`${app} is in the platform library`}>
            Checked by the platform team. You paste your own token, and a test on your own data runs before anything goes live.
          </Banner>
          <Button variant="primary" busy={busy} onClick={() => create(true)}>Connect with your token</Button>
        </div>
      ) : (
        <div className="max-w-[560px]">
          <Card title="Build it with AI from the app's API docs">
            <p className="mb-4 text-text-subdued">
              The AI reads the public docs and fills in a connector form, with a quote from the docs for every answer. It never writes code and never sees your data or tokens.
            </p>
            <div className="space-y-4">
              {!app && (
                <Field label="App name">
                  <TextInput value={appName} onChange={(e) => setAppName(e.target.value)} placeholder="e.g. Acme Forms" />
                </Field>
              )}
              <Field label="API docs link" help="The public developer docs. A page about listing users is a good start.">
                <TextInput value={docsUrl} onChange={(e) => setDocsUrl(e.target.value)} placeholder="https://developer.example.com/api" type="url" />
              </Field>
              <Field label="Or upload an OpenAPI file" help="JSON or YAML. Optional; it's read first when it's there.">
                <input type="file" accept=".json,.yaml,.yml" onChange={(e) => setFile(e.target.files?.[0] ?? null)} className="text-text-subdued file:mr-3 file:h-8 file:cursor-pointer file:rounded-sm file:border file:border-solid file:border-border-strong file:bg-surface file:px-3 file:font-sans file:font-medium file:text-text-heading hover:file:bg-surface-subdued" />
              </Field>
            </div>
            <div className="mt-6 flex justify-end gap-2">
              <Button onClick={() => navigate("/")}>Cancel</Button>
              <Button variant="primary" busy={busy} disabled={!docsUrl && !file} onClick={() => create(false)}>Build with AI</Button>
            </div>
          </Card>
        </div>
      )}
    </>
  );
}
