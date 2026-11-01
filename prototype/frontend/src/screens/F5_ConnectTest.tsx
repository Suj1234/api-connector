// F5 Connect and test: the token (write-only; none with sample data), the test in the sandbox, what the generated
// code covers (the assignment's six items), the code itself and every request it made.
import { useCallback, useEffect, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { api, streamEvents, type AppUsers, type ConnectorDetail, type PipelineEvent, type RunView } from "../api";
import { Badge, Banner, Button, Card, CodeBlock, DetailsList, Field, Icon, Metric, RequestLog, Tabs, Tag, TextInput, Timeline, pagingLabel, toast, type TimelineItem } from "../components/ui";
import { duration } from "./F3_Docs";
import { FlowPage } from "./Flow";

const AUTH_LABEL: Record<string, string> = {
  bearer_token: "API token",
  basic: "Username and token",
  api_key_header: "API key in a header",
  oauth_client_credentials: "OAuth client credentials",
};
const secondsBetween = (a?: string, b?: string) => (a && b ? Math.max(0, Math.round((Date.parse(b) - Date.parse(a)) / 1000)) : 0);

export default function ConnectTest() {
  const { id } = useParams();
  const navigate = useNavigate();
  const [c, setC] = useState<ConnectorDetail | null>(null);
  const [secrets, setSecrets] = useState<Record<string, string>>({});
  const [variables, setVariables] = useState<Record<string, string>>({});
  const [owner, setOwner] = useState("");
  const [events, setEvents] = useState<PipelineEvent[]>([]);
  const [running, setRunning] = useState(false);
  const [run, setRun] = useState<RunView | null>(null);
  const [users, setUsers] = useState<AppUsers | null>(null);
  const [tab, setTab] = useState("test");
  const [code, setCode] = useState<string>("");
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    const detail = await api.get<ConnectorDetail>(`/api/connectors/${id}`);
    setC(detail);
    setVariables(detail.variables ?? {});
    setOwner(detail.token_owner_email ?? "");
    if (detail.last_run) setRun(await api.get<RunView>(`/api/runs/${detail.last_run.id}`));
    if (detail.last_run?.exit_code === 0) api.get<AppUsers>(`/api/connectors/${id}/users`).then(setUsers).catch(() => setUsers(null));
    api.get<string>(`/api/connectors/${id}/code`).then(setCode).catch(() => setCode(""));
  }, [id]);

  useEffect(() => {
    load();
  }, [load]);

  if (!c || !c.summary) return null;
  const s = c.summary;
  const replay = c.run_mode === "replay";

  const startTest = async () => {
    setError(null);
    setRunning(true);
    setEvents([]);
    setTab("test");
    try {
      if (!replay || Object.keys(variables).length || owner) {
        await api.post(`/api/connectors/${id}/credentials`, { secrets, variables, token_owner_email: owner || null });
        setSecrets({});
      }
      await api.post(`/api/connectors/${id}/test`, {});
      await streamEvents(Number(id), (e) => setEvents((prev) => [...prev, e]));
      await load();
    } catch (e) {
      setError((e as Error).message);
    }
    setRunning(false);
  };

  const passed = !!run && run.exit_code === 0 && !running;
  // A live test needs the token (and any account value) once; after that it's saved.
  const missing = !replay && !c.has_credentials && (s.login.fields.some((f) => !secrets[f.name]?.trim()) || s.login.variables.some((v) => !variables[v.name]?.trim()));
  // A failure before any test ran (for example the code checks) has no run to show it.
  const lastFail = [...events].reverse().find((e) => e.stage === "done" && e.status === "fail");
  const preRunError = running ? null : lastFail?.code === "CODEGEN_FAILED" ? lastFail.message : !run && c.error ? c.error.message : null;
  const repairs = run?.summary?.repairs ?? [];
  const logs = run?.logs ?? [];
  const active = users?.users.filter((u) => (u.usage_metric_value ?? 0) > 0 || u.last_active_at).length;

  // While it runs: what the server reports, newest first. After: the four checks of the last run.
  const live: TimelineItem[] = [];
  for (const e of events) {
    const begun = (stage: string) => [...events].reverse().find((x) => x.stage === stage && x.status === "start" && x.seq < e.seq);
    if (e.stage === "codegen") {
      if (e.status === "start") live.push({ title: "Writing the connector code", busy: true });
      else live[live.length - 1] = { title: e.status === "ok" ? "Code written; it passes ruff and mypy --strict" : "The generated code failed its checks", tone: e.status === "ok" ? "success" : "danger", time: `Took ${duration(secondsBetween(begun("codegen")?.at, e.at))}` };
    } else if (e.stage === "test") {
      if (e.status === "start") live.push({ title: "Running it in the sandbox", busy: true });
      else live[live.length - 1] = { title: e.status === "ok" ? `Test passed: ${e.message}` : `Test failed: ${e.message}`, tone: e.status === "ok" ? "success" : "danger", time: `Took ${duration(secondsBetween(begun("test")?.at, e.at))}` };
    } else if (e.stage === "repair") {
      if (e.status === "start") live.push({ title: e.message ?? "Fixing automatically", busy: true });
      else live[live.length - 1] = { title: e.status === "ok" ? `Fixed: ${e.message}` : "The proposed fix was rejected", tone: e.status === "ok" ? "success" : "warning" };
    }
  }
  const usageCheck = run?.checklist?.usage;
  const checks: TimelineItem[] = run
    ? [
        { title: "Login", tone: run.checklist?.login === "ok" ? "success" : run.checklist?.login === "fail" ? "danger" : "neutral", time: run.checklist?.login === "ok" ? `Signed in with ${AUTH_LABEL[s.login.type] ?? s.login.type}` : undefined },
        { title: "Users", tone: run.checklist?.users === "ok" ? "success" : run.checklist?.users === "fail" ? "danger" : "neutral", time: run.checklist?.users === "ok" ? `${run.summary?.users} users, ${run.summary?.pages?.users ?? 1} pages` : undefined },
        {
          title: "Usage",
          tone: usageCheck === "ok" ? "success" : run.exit_code === 0 ? "warning" : usageCheck === "fail" ? "danger" : "neutral",
          time:
            usageCheck === "ok"
              ? `${s.usage.label ?? "Usage"}${run.summary?.usage_sampled ? ", first pages only in a test" : ""}`
              : run.exit_code === 0 && usageCheck === undefined
                ? "Not in this app's API: uses the last login from SSO"
                : run.exit_code === 0
                  ? run.usage_message ?? "Blocked by the token's role, scope or plan"
                  : undefined,
        },
        { title: "Mapping into the standard user record", tone: run.checklist?.map === "ok" ? "success" : run.checklist?.map === "fail" ? "danger" : "neutral", time: run.checklist?.map === "ok" ? "Every user fits" : undefined },
      ]
    : [];

  return (
    <FlowPage
      app={c.app}
      step="connect"
      status={`${passed ? "Tested" : "Draft"} · version ${c.version ?? 1}`}
      actions={passed && <Button variant="primary" onClick={() => { toast("Test passed"); navigate(`/connectors/${id}/savings`); }}>Continue</Button>}
      title="Connect and test"
      intro={
        replay ? (
          <span className="inline-flex flex-wrap items-center gap-2">
            The test runs the generated code on recorded {c.app} answers with fake people. <Tag>Sample data</Tag>
          </span>
        ) : (
          `The test calls ${c.app}'s real API, with read-only requests only.`
        )
      }
    >
      {error && <Banner tone="danger" title="That didn't work">{error}</Banner>}
      {c.from_library && <Banner tone="info" title="From the platform library">Your own test runs on your own data first.</Banner>}

      <div>
        <Tabs
          value={tab}
          onChange={setTab}
          tabs={[
            { id: "test", label: "Test" },
            { id: "code", label: "Generated code" },
            { id: "log", label: "Run log", count: logs.length || undefined },
          ]}
        />

        {tab === "test" && (
          <div className="grid gap-4">
            <Card title="Connect">
              {replay ? (
                <p className="text-text-subdued">No token is needed: this company uses sample data. With a real account, you'd paste a token here that has the role and scopes from the review.</p>
              ) : (
                <div className="grid gap-4">
                  {s.login.setup_steps.length > 0 && (
                    <div>
                      <div className="font-semibold text-text">Create the token in {c.app}</div>
                      <ol className="mt-1 list-decimal space-y-0.5 pl-5 text-text-subdued">
                        {s.login.setup_steps.map((step) => <li key={step}>{step}</li>)}
                      </ol>
                    </div>
                  )}
                  {s.login.scopes.length > 0 && (
                    <div>
                      <div className="font-semibold text-text">Give it exactly these scopes</div>
                      <div className="mt-1 flex flex-wrap gap-1">{s.login.scopes.map((x) => <Tag key={x}>{x}</Tag>)}</div>
                    </div>
                  )}
                  <div className="grid gap-4 md:grid-cols-2">
                    {s.login.variables.map((v) => (
                      <Field key={v.name} label={v.label} help={`For example: ${v.example}`}>
                        <TextInput value={variables[v.name] ?? ""} onChange={(e) => setVariables({ ...variables, [v.name]: e.target.value })} />
                      </Field>
                    ))}
                    {s.login.fields.map((f) => (
                      <Field key={f.name} label={f.label}>
                        <TextInput
                          type={f.secret ? "password" : "text"}
                          autoComplete="off"
                          value={secrets[f.name] ?? ""}
                          placeholder={c.has_credentials ? "Saved. Paste again to replace." : ""}
                          onChange={(e) => setSecrets({ ...secrets, [f.name]: e.target.value })}
                        />
                      </Field>
                    ))}
                    <Field label="Token owner's email" optional help="So we can warn you before this person leaves the company.">
                      <TextInput type="email" value={owner} onChange={(e) => setOwner(e.target.value)} />
                    </Field>
                  </div>
                </div>
              )}
              <div className="mt-4 flex flex-wrap items-center justify-between gap-3 border-t border-border pt-4">
                <span className="inline-flex items-center gap-2 text-text-muted">
                  <Icon name="lock" className="h-4 w-4" />
                  Encrypted, read-only, never shared with the AI.
                </span>
                {missing && <span className="ml-auto text-text-muted">Fill in every field above to run the test.</span>}
                <Button variant={passed ? "secondary" : "primary"} busy={running} disabled={missing} onClick={startTest}>
                  {run ? "Run the test again" : "Run test"}
                </Button>
              </div>
            </Card>

            <Card
              title="Test in the sandbox"
              aside={<Badge tone="neutral" icon={false}>Demo isolation (subprocess)</Badge>}
            >
              <p className="mb-4 text-text-subdued">
                The code runs where it can only reach <code className="code">{s.host}</code>. If a step fails in a way the AI can fix, it proposes a small change to the form (up to 3 tries) and the test runs again.
              </p>
              {running || (events.length > 0 && !run) ? (
                <Timeline items={live.length ? [...live].reverse() : [{ title: "Starting…", busy: true }]} />
              ) : run ? (
                <Timeline items={checks} />
              ) : (
                <span className="text-text-muted">Not run yet.</span>
              )}
            </Card>

            {preRunError && <Banner tone="danger" title="The test didn't run">{preRunError}</Banner>}
            {!running && !preRunError && run && run.exit_code !== 0 && (
              <Banner tone="danger" title={run.error_code === "HOST_BLOCKED" ? "Blocked: a call to another host" : "The test didn't pass"}>{run.message ?? run.error_code}</Banner>
            )}
            {!running && run?.status === "partial" && (
              <Banner tone="warning" title="Users synced. Usage is blocked.">{run.usage_message} You can go live with users only.</Banner>
            )}

            {passed && (
              <>
                <Card title="Results">
                  <div className="grid grid-cols-2 gap-6 md:grid-cols-4">
                    <Metric label="Users found" value={run.summary?.users ?? "—"} compare={replay ? "Sample data" : `From ${c.app}'s API`} />
                    <Metric label="With activity" value={active ?? "—"} compare={s.usage.label ?? "No usage in the API"} />
                    <Metric label="Pages read" value={(run.summary?.pages?.users ?? 0) + (run.summary?.pages?.usage ?? 0)} compare="Users and usage" />
                    <Metric label="Requests" value={logs.length} compare="All read-only" />
                  </div>
                </Card>
                <Card title="What the generated code covers">
                  <DetailsList
                    layout="rows"
                    items={[
                      ["API client", <Covered key="1" text={`One client for ${s.host}, read-only (GET only)`} />],
                      ["Authentication", <Covered key="2" text={`${AUTH_LABEL[s.login.type] ?? s.login.type}, kept out of logs`} />],
                      ["Users and usage", <Covered key="3" text={`${run.summary?.users} users; usage: ${s.usage.label ?? "SSO last login"}`} />],
                      ["Error handling", <Covered key="4" text={`Retries server errors and waits when rate-limited; ${logs.filter((l) => l.retry > 0).length} retries in this run`} />],
                      ["Pagination", <Covered key="5" text={`${pagingLabel(s.users.pagination)}; ${run.summary?.pages?.users ?? 1} pages of users`} />],
                      ["Logging", <Covered key="6" text={`${logs.length} requests logged, without bodies or tokens`} />],
                    ]}
                  />
                  <div className="mt-3">
                    <Button small onClick={() => setTab("code")}>See the code</Button>
                  </div>
                </Card>
              </>
            )}

            {!running && repairs.length > 0 && (
              <Card title="Fixed automatically">
                <Timeline
                  items={repairs.map((r) => ({
                    title: r.accepted ? r.diagnosis ?? "Fixed" : "The proposed fix was rejected",
                    time: `Try ${r.attempt} · ${r.model}${r.accepted ? "" : ` · ${r.reason ?? ""}`}`,
                    tone: r.accepted ? "success" : "warning",
                  }))}
                />
              </Card>
            )}
          </div>
        )}

        {tab === "code" &&
          (code ? (
            <div className="grid gap-3">
              <p className="text-text-subdued">Written by our templates from the reviewed form. The highlighted lines mark the six parts the assignment asks for.</p>
              <CodeBlock code={code} highlightItems />
            </div>
          ) : (
            <span className="text-text-muted">No code yet. Run the test to write it.</span>
          ))}

        {tab === "log" && (
          <Card title="Every request the test made" aside={<span className="text-text-muted">Bodies and tokens are never logged</span>}>
            {logs.length ? (
              <RequestLog entries={logs.map((l) => ({ status: l.status, method: l.method, path: l.path, time: `${l.step} · ${l.ms} ms${l.retry ? ` · retry ${l.retry}` : ""}` }))} />
            ) : (
              <span className="text-text-muted">Run the test to see each request.</span>
            )}
          </Card>
        )}
      </div>
    </FlowPage>
  );
}

function Covered({ text }: { text: string }) {
  return (
    <span className="flex items-start justify-between gap-3">
      <span>{text}</span>
      <Badge tone="success">Done</Badge>
    </span>
  );
}
