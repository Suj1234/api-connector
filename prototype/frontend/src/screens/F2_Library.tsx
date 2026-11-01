// F2 Library check, and F3's docs form when the app isn't in the library.
// The reference Drawer over the App inventory: /connect adds an app (with the inventory details every app has),
// /connect/:app connects usage data for one already listed. Closing with unsaved input asks first.
import { useEffect, useRef, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { api, type InventoryRow } from "../api";
import { Banner, Button, ChoiceCards, DateField, Drawer, Field, Modal, TextInput, toast } from "../components/ui";

// A full web address: http(s) and a host with a dot. Whether the page opens is checked when the build reads it.
const linkOk = (v: string) => {
  try {
    const u = new URL(v.trim());
    return (u.protocol === "https:" || u.protocol === "http:") && u.hostname.includes(".");
  } catch {
    return false;
  }
};

// Today as an ISO date in the admin's own time zone: a renewal date can't be in the past.
const today = () => {
  const d = new Date();
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
};

const KNOWN_DOCS: Record<string, string> = {
  calendly: "https://developer.calendly.com/api-docs",
  zendesk: "https://developer.zendesk.com/api-reference/ticketing/users/users/",
  notion: "https://developers.notion.com/reference/get-users",
  asana: "https://developers.asana.com/reference/getusersforworkspace",
  miro: "https://developers.miro.com/reference/enterprise-get-organization-members",
  typeform: "https://www.typeform.com/developers/",
};

export default function ConnectDrawer({ onClose, onSaved }: { onClose: () => void; onSaved: () => void }) {
  const { app = "" } = useParams();
  const navigate = useNavigate();
  const startDocs = KNOWN_DOCS[app.toLowerCase()] ?? "";
  const [row, setRow] = useState<InventoryRow | null>(null);
  const [appName, setAppName] = useState("");
  const [owner, setOwner] = useState("");
  const [spend, setSpend] = useState("");
  const [seats, setSeats] = useState("");
  const [renewal, setRenewal] = useState("");
  const [source, setSource] = useState<"link" | "file">("link"); // one or the other, never both
  const [docsUrl, setDocsUrl] = useState(startDocs);
  const [docsTouched, setDocsTouched] = useState(false);
  const [file, setFile] = useState<File | null>(null);
  const fileInput = useRef<HTMLInputElement>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [confirm, setConfirm] = useState(false);

  useEffect(() => {
    if (app) api.get<InventoryRow[]>("/api/inventory").then((rows) => setRow(rows.find((r) => r.app === app) ?? null));
  }, [app]);

  useEffect(() => setError(null), [appName, owner, spend, seats, renewal, source, docsUrl, file]); // an old error goes once the form changes

  const spendOk = spend.trim() !== "" && Number(spend) >= 0;
  const seatsOk = Number.isInteger(Number(seats)) && Number(seats) >= 1;
  const detailsOk = !!appName.trim() && !!owner.trim() && spendOk && seatsOk && !!renewal;
  const ready = (source === "link" ? linkOk(docsUrl) : !!file) && (!!app || detailsOk);
  const dirty = (!app && !!(appName || owner || spend || seats || renewal)) || docsUrl !== startDocs || !!file;

  // A reload or closed tab loses the form too, so the browser asks first.
  useEffect(() => {
    if (!dirty) return;
    const warn = (e: BeforeUnloadEvent) => e.preventDefault();
    window.addEventListener("beforeunload", warn);
    return () => window.removeEventListener("beforeunload", warn);
  }, [dirty]);

  const requestClose = () => {
    if (confirm || busy) return; // Escape on the open confirm closes only the confirm
    if (dirty) setConfirm(true);
    else onClose();
  };

  const fail = (e: unknown) => {
    setError((e as Error).message);
    setBusy(false);
    setConfirm(false);
  };

  const details = () => ({ app: appName.trim(), owner: owner.trim(), annual_cost: Number(spend), seats: Number(seats), renewal_date: renewal });

  const save = async () => {
    setBusy(true);
    try {
      await api.post("/api/inventory", details());
      toast(`${appName.trim()} is in your inventory`);
      onSaved();
    } catch (e) {
      fail(e);
    }
  };

  const build = async (fromLibrary: boolean) => {
    setBusy(true);
    setError(null);
    const form = new FormData();
    if (app) form.set("app_name", app);
    else Object.entries(details()).forEach(([k, v]) => form.set(k === "app" ? "app_name" : k, String(v)));
    if (fromLibrary && row?.library_spec_id) form.set("from_library_spec_id", String(row.library_spec_id));
    if (!fromLibrary) {
      if (source === "link") form.set("docs_url", docsUrl.trim());
      else if (file) form.set("openapi_file", file);
    }
    try {
      const { id } = await api.form<{ id: number }>("/api/connectors", form);
      navigate(fromLibrary ? `/connectors/${id}/connect` : `/connectors/${id}/build`);
    } catch (e) {
      fail(e);
    }
  };

  const library = !!row?.in_library;
  return (
    <>
      <Drawer
        open
        width={480}
        eyebrow={app || undefined}
        title={app ? "Connect usage data" : "Add an app"}
        onClose={requestClose}
        footer={
          library ? (
            <Button variant="primary" busy={busy} onClick={() => build(true)}>Connect with your token</Button>
          ) : (
            <>
              <Button onClick={requestClose}>Cancel</Button>
              {!app && <Button disabled={!detailsOk || busy} onClick={save}>Save app</Button>}
              <Button variant="primary" busy={busy} disabled={!ready} onClick={() => build(false)}>Build with AI</Button>
            </>
          )
        }
      >
        {error && <Banner tone="danger" title="That didn't work">{error}</Banner>}
        {library ? (
          <Banner tone="info" title={`${app} is in the platform library`}>
            Checked by the platform team. You paste your own token, and a test on your own data runs before anything goes live.
          </Banner>
        ) : (
          <>
            {!app && (
              <>
                <Field label="App name">
                  <TextInput value={appName} onChange={(e) => setAppName(e.target.value)} placeholder="e.g. Acme Forms" maxLength={100} />
                </Field>
                <div className="grid grid-cols-2 gap-x-4 gap-y-5">
                  <Field label="Owner" help="The team that pays for it.">
                    <TextInput value={owner} onChange={(e) => setOwner(e.target.value)} placeholder="e.g. Marketing Ops" maxLength={100} />
                  </Field>
                  <Field label="Renewal date" help="When the contract renews.">
                    <DateField value={renewal} onChange={setRenewal} min={today()} />
                  </Field>
                  <Field label="Annual spend" error={spend && !spendOk ? "Enter an amount in dollars." : null}>
                    <TextInput affix="$" inputMode="decimal" value={spend} onChange={(e) => setSpend(e.target.value)} placeholder="12000" />
                  </Field>
                  <Field label="Seats" error={seats && !seatsOk ? "Enter a whole number, 1 or more." : null}>
                    <TextInput inputMode="numeric" value={seats} onChange={(e) => setSeats(e.target.value)} placeholder="50" />
                  </Field>
                </div>
              </>
            )}
            <div className="grid gap-1.5">
              <span className="font-semibold text-text">API documentation</span>
              <ChoiceCards
                label="API documentation"
                value={source}
                onChange={setSource}
                options={[
                  { value: "link", title: "Docs link", description: "The app's public API docs page" },
                  { value: "file", title: "OpenAPI file", description: "A file that lists the app's API" },
                ]}
              />
              <span className="text-xs text-text-muted">Give one of the two. The AI reads it to build the connector, and never sees your data or tokens.</span>
            </div>
            {source === "link" ? (
              <Field
                label="API docs link"
                help="For example https://developer.calendly.com/api-docs. If the docs point to an OpenAPI file, the AI finds and uses it too."
                error={docsTouched && docsUrl.trim() && !linkOk(docsUrl) ? "Enter a full link, like https://developer.example.com/api." : null}
              >
                <TextInput value={docsUrl} onChange={(e) => setDocsUrl(e.target.value)} onBlur={() => setDocsTouched(true)} placeholder="https://developer.example.com/api" type="url" />
              </Field>
            ) : (
              <Field label="OpenAPI file" help="JSON or YAML. Use it when the docs need a login, or when the app's team sent you the file.">
                <span className="flex items-center gap-3">
                  <input ref={fileInput} type="file" accept=".json,.yaml,.yml" className="hidden" onChange={(e) => setFile(e.target.files?.[0] ?? null)} />
                  <Button small onClick={() => fileInput.current?.click()}>{file ? "Change file" : "Upload file"}</Button>
                  <span className={file ? "text-text" : "text-text-muted"}>{file ? file.name : "No file chosen"}</span>
                </span>
              </Field>
            )}
          </>
        )}
      </Drawer>

      <Modal
        open={confirm}
        title="Leave without saving?"
        onClose={() => setConfirm(false)}
        footer={
          app ? (
            <>
              <Button onClick={() => setConfirm(false)}>Keep editing</Button>
              <Button variant="danger" onClick={onClose}>Discard</Button>
            </>
          ) : (
            <>
              <Button onClick={onClose}>Discard</Button>
              <Button variant="primary" busy={busy} disabled={!detailsOk} onClick={save}>Save app</Button>
            </>
          )
        }
      >
        <p className="text-text-subdued">
          {app
            ? "The docs link you changed will be lost."
            : detailsOk
              ? `Save ${appName.trim()} to your inventory and build its connector later, or discard what you typed.`
              : "What you typed will be lost. To save the app instead, fill in all its details first."}
        </p>
      </Modal>
    </>
  );
}
