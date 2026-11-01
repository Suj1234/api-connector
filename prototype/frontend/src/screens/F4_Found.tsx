// F4 Review what we found: the AI's answers by section, each with its proof from the docs (the evidence drawer),
// what the templates write instead of the AI, and a hint to re-draft when something looks wrong.
import { useEffect, useRef, useState, type ReactNode } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { api, type ConnectorDetail, type EvidenceRow } from "../api";
import { Badge, Banner, Button, Card, DetailsList, Drawer, Icon, Tag, cx, pagingLabel } from "../components/ui";
import { FlowPage, HintModal } from "./Flow";

const AUTH_LABEL: Record<string, string> = {
  bearer_token: "API token (bearer)",
  basic: "Username and password or token",
  api_key_header: "API key in a header",
  oauth_client_credentials: "OAuth client credentials",
};
const TIER: Record<string, string> = {
  T1: "T1: each user record has a last-activity date",
  T2: "T2: counted from separate activity records",
  T3: "T3: the API has no usage data",
};
// Evidence pointers in plain words; anything else shows its pointer.
const FIELD: Record<string, string> = {
  "/base_url": "API address",
  "/auth/type": "Sign-in method",
  "/rate_limit/requests_per_minute": "Rate limit",
  "/streams/users/path": "Users endpoint",
  "/streams/users/records_path": "Where users sit in the answer",
  "/streams/users/pagination": "Users paging",
  "/streams/usage/path": "Usage endpoint",
  "/streams/usage/records_path": "Where usage records sit",
  "/streams/usage/pagination": "Usage paging",
  "/streams/usage/aggregate": "How usage is counted",
  "/bootstrap/0/path": "First call (finds the account)",
};
const fieldLabel = (pointer: string) =>
  FIELD[pointer] ?? (pointer.startsWith("/streams/users/field_map/") ? `User field: ${pointer.split("/").pop()}` : pointer);
// An answer in words: paging by its type (and where the next page is), other objects as "key: value" pairs.
const show = (v: unknown): string | null => {
  if (v === null || v === undefined) return null;
  if (typeof v !== "object") return String(v);
  const o = v as Record<string, unknown>;
  const rest = Object.entries(o).filter(([k, x]) => k !== "type" && x !== null && x !== undefined);
  const parts = rest.map(([k, x]) => `${k.replace(/_/g, " ")}: ${typeof x === "object" ? JSON.stringify(x) : String(x)}`).join(" · ");
  return typeof o.type === "string" ? `${pagingLabel(o.type)}${parts ? ` · ${parts}` : ""}` : parts;
};

export default function Found() {
  const { id } = useParams();
  const navigate = useNavigate();
  const [c, setC] = useState<ConnectorDetail | null>(null);
  const [focus, setFocus] = useState<string | null>(null); // the evidence drawer: open, on this field
  const [hintOpen, setHintOpen] = useState(false);

  useEffect(() => {
    api.get<ConnectorDetail>(`/api/connectors/${id}`).then(setC);
  }, [id]);

  if (!c) return null;
  if (!c.summary) {
    return (
      <FlowPage app={c.app} step="found" status="Stopped" title="We couldn't build this connector">
        {c.error && <Banner tone="danger" title="What went wrong">{c.error.message}</Banner>}
        <div>
          <Button variant="primary" onClick={() => navigate(`/connect/${encodeURIComponent(c.app)}`)}>Try another link</Button>
        </div>
      </FlowPage>
    );
  }
  const s = c.summary;
  const proved = c.evidence.filter((e) => e.verified).length;
  const unproved = c.warnings.filter((w) => w.startsWith("Not proved"));
  const warnings = c.warnings.filter((w) => !w.startsWith("Not proved"));
  const byField = new Map(c.evidence.map((e) => [e.field, e]));
  const fields = c.evidence.filter((e) => e.field.startsWith("/streams/users/field_map/"));

  // A small proof badge next to an answer; it opens that answer's quote.
  const proof = (pointer: string) => {
    const e = byField.get(pointer);
    if (!e) return null;
    return (
      <button type="button" onClick={() => setFocus(pointer)} className="ml-2 align-middle focus-visible:shadow-focus focus-visible:outline-none">
        <Badge tone={e.verified ? "success" : "warning"}>{e.verified ? "Proved" : "Not proved"}</Badge>
      </button>
    );
  };
  const value = (text: ReactNode, pointer?: string) => (
    <span>
      {text}
      {pointer && proof(pointer)}
    </span>
  );

  return (
    <FlowPage
      app={c.app}
      step="found"
      status={`Draft · version ${c.version ?? 1}`}
      actions={
        <>
          <Button onClick={() => setHintOpen(true)}>This looks wrong</Button>
          <Button variant="primary" onClick={() => navigate(`/connectors/${id}/connect`)}>Looks right</Button>
        </>
      }
      title="Review what we found"
      intro={
        <>
          The AI read {c.app}'s docs and filled in the connector form. {proved} of {c.evidence.length} answers are proved by a quote from the docs.{" "}
          <button type="button" className="font-semibold text-link hover:underline" onClick={() => setFocus("")}>See all the evidence</button>
        </>
      }
    >
      {c.ai_source && c.ai_source !== "Gemini" && (
        <Banner tone="warning" title={c.ai_source}>This draft didn't come from a live AI call in this session.</Banner>
      )}
      {unproved.length > 0 && (
        <Banner tone="warning" title="Some answers aren't proved by the docs yet">Check them in the evidence. The test will still catch anything wrong.</Banner>
      )}
      {c.conflicts.length > 0 && (
        <Banner tone="info" title={`${c.conflicts.length === 1 ? "Two sources disagree" : "Sources disagree"}, and we chose the vendor's own docs`} action={<Button small onClick={() => setFocus("")}>See why</Button>} />
      )}

      <div className="grid gap-4">
        <Card title="Login">
          <DetailsList
            layout="rows"
            items={[
              ["Sign-in method", value(AUTH_LABEL[s.login.type] ?? s.login.type, "/auth/type")],
              ["Role needed", s.login.role_required],
              ["Scopes", s.login.scopes.length ? <span className="flex flex-wrap gap-1">{s.login.scopes.map((x) => <Tag key={x}>{x}</Tag>)}</span> : "None listed"],
              ["Setup", s.login.setup_steps.length ? `${s.login.setup_steps.length} ${s.login.setup_steps.length === 1 ? "step" : "steps"}, shown when you connect` : null],
            ]}
          />
        </Card>
        <Card title="Users">
          <DetailsList
            layout="rows"
            items={[
              ["Endpoint", value(<code className="code">GET {s.users.path}</code>, "/streams/users/path")],
              ["Paging", value(pagingLabel(s.users.pagination), "/streams/users/pagination")],
              [
                "Fields read",
                <span key="f" className="flex flex-wrap gap-1">
                  {s.users.fields.map((f) => <Tag key={f}>{f}</Tag>)}
                  {fields.length > 0 && <span className="ml-1">{proof(fields.find((e) => !e.verified)?.field ?? fields[0].field)}</span>}
                </span>,
              ],
            ]}
          />
        </Card>
        <Card title="Usage" aside={<Badge tone={s.usage.tier === "T3" ? "warning" : "info"} icon={false}>{s.usage.tier}</Badge>}>
          <DetailsList
            layout="rows"
            items={[
              ["What it measures", s.usage.label ? <span>{s.usage.label}{s.usage.proxy && <span className="ml-2"><Tag>proxy</Tag></span>}</span> : "Nothing in the API"],
              ["Where it comes from", TIER[s.usage.tier]],
              ["Endpoint", s.usage.path ? value(<code className="code">GET {s.usage.path}</code>, "/streams/usage/path") : null],
              ["Time window", s.usage.window_days ? `Last ${s.usage.window_days} days` : null],
              ["If the API has none", s.usage.fallback === "sso_last_login" ? "Last login from SSO, labelled “from SSO, not from the app”" : null],
            ]}
          />
        </Card>
        <Card title="Limits">
          <DetailsList
            layout="rows"
            items={[
              ["Rate limit", value(`${s.limits.requests_per_minute} requests per minute`, "/rate_limit/requests_per_minute")],
              ["Plan note", s.limits.plan_note],
              ["API address", value(<code className="code">{s.host}</code>, "/base_url")],
            ]}
          />
        </Card>
      </div>

      {warnings.length > 0 && (
        <Banner tone="warning" title="Things to know before you connect">
          <ul className="mt-1 list-disc space-y-1 pl-5">
            {warnings.map((w) => <li key={w}>{w}</li>)}
          </ul>
        </Banner>
      )}
      <Banner tone="info" icon="code" title="Written by our templates, not by the AI">
        The API client, error handling (retries and waiting when rate-limited), the paging loop and logging. You'll see all of it in the generated code on the next step.
      </Banner>

      <EvidenceDrawer c={c} focus={focus} onClose={() => setFocus(null)} />

      <HintModal connectorId={id ?? ""} open={hintOpen} onClose={() => setHintOpen(false)} onSent={() => navigate(`/connectors/${id}/build`)} />
    </FlowPage>
  );
}

// The proof behind every answer: the quote, the page it came from, and whether we found it there.
function EvidenceDrawer({ c, focus, onClose }: { c: ConnectorDetail; focus: string | null; onClose: () => void }) {
  const focused = useRef<HTMLLIElement | null>(null);
  useEffect(() => {
    focused.current?.scrollIntoView({ block: "center" });
  }, [focus]);
  const proved = c.evidence.filter((e) => e.verified).length;
  // The answer that was clicked comes first.
  const rows: EvidenceRow[] = focus ? [...c.evidence].sort((a, b) => Number(b.field === focus) - Number(a.field === focus)) : c.evidence;
  return (
    <Drawer open={focus !== null} width={520} eyebrow={`${proved} of ${c.evidence.length} proved`} title="Evidence from the docs" onClose={onClose}>
      <p className="text-text-subdued">
        Each answer carries a quote of 25 words or fewer and the page it came from. We look for the quote on that page; it passes when it matches at least 90%, ignoring case and spacing. For the API address, the endpoints and the rate limit, the page must also show that value: the host, every part of the path, or the number.
      </p>
      {c.conflicts.map((cf) => (
        <Banner key={cf.field} tone="info" title={`Sources disagree on ${fieldLabel(cf.field)}`}>
          <ul className="mt-1 space-y-0.5">
            {cf.values.map((v) => (
              <li key={v.source}>
                {String(v.value)} ·{" "}
                <a href={v.source} target="_blank" rel="noreferrer" className="text-link hover:underline">{new URL(v.source).hostname}</a>
              </li>
            ))}
          </ul>
          <div className="mt-1">We used {String(cf.chosen)}. {cf.reason}</div>
        </Banner>
      ))}
      <ul className="grid">
        {rows.map((e) => (
          <li
            key={e.field}
            ref={e.field === focus ? focused : undefined}
            className={cx("grid gap-1.5 border-b border-border py-4 first:pt-0 last:border-0", e.field === focus && "-mx-2 rounded-sm bg-primary-subtle px-2 first:pt-3")}
          >
            <div className="flex items-center justify-between gap-2">
              <span className="font-semibold text-text">{fieldLabel(e.field)}</span>
              {e.verified ? <Badge tone="success">Proved</Badge> : <Badge tone="warning">Not proved</Badge>}
            </div>
            {show(e.value) && <code className="code break-all text-text">{show(e.value)}</code>}
            {e.quote && <blockquote className="border-l-2 border-border-strong pl-3 text-text-subdued">"{e.quote}"</blockquote>}
            {e.openapi_pointer && <div className="caption">OpenAPI: {e.openapi_pointer}</div>}
            {e.url && (
              <a className="inline-flex items-center gap-1 text-xs text-link hover:underline" href={e.url} target="_blank" rel="noreferrer">
                <span className="truncate">{e.url.replace(/^https?:\/\//, "")}</span>
                <Icon name="external" className="h-3 w-3" />
              </a>
            )}
            {!e.verified && e.problem && <div className="text-xs text-warning-fg">{e.problem}</div>}
          </li>
        ))}
      </ul>
    </Drawer>
  );
}
