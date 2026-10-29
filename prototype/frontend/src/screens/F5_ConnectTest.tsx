// F5 Connect + test: token instructions, write-only secrets, the live test checklist, generated code.
import { useCallback, useEffect, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { api, streamEvents, type ConnectorDetail, type PipelineEvent, type RunView } from "../api";
import { Badge, Banner, Button, Card, CodeBlock, Field, PageHeader, StatusBadge, Stepper, Tabs, Tag, TextInput, toast, type StepState } from "../components/ui";

const CHECKS = [
  { id: "login", label: "Login" },
  { id: "users", label: "Users" },
  { id: "usage", label: "Usage" },
  { id: "map", label: "Mapping" },
];

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
  const [tab, setTab] = useState("results");
  const [code, setCode] = useState<string>("");
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    const detail = await api.get<ConnectorDetail>(`/api/connectors/${id}`);
    setC(detail);
    setVariables(detail.variables ?? {});
    setOwner(detail.token_owner_email ?? "");
    if (detail.last_run) setRun(await api.get<RunView>(`/api/runs/${detail.last_run.id}`));
    api.get<string>(`/api/connectors/${id}/code`).then(setCode).catch(() => setCode(""));
  }, [id]);

  useEffect(() => {
    load();
  }, [load]);

  if (!c || !c.summary) return null;
  const s = c.summary;
  const replay = c.run_mode === "replay";
  const needsSecrets = !replay;

  const startTest = async () => {
    setError(null);
    setRunning(true);
    setEvents([]);
    try {
      if (needsSecrets || Object.keys(variables).length || owner) {
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

  const checkState = (step: string): StepState => {
    const status = run?.checklist?.[step];
    if (running) return events.some((e) => e.stage === "test" && e.status === "start") ? "running" : "waiting";
    if (!run) return "waiting";
    if (status === "ok") return "done";
    if (status === "fail") return step === "usage" && run.exit_code === 0 ? "warn" : "failed";
    return "waiting";
  };
  const passed = run && run.exit_code === 0 && !running;
  // A failure before any test ran (for example the code checks) has no run to show it.
  const lastFail = [...events].reverse().find((e) => e.stage === "done" && e.status === "fail");
  const preRunError = running ? null : lastFail?.code === "CODEGEN_FAILED" ? lastFail.message : !run && c.error ? c.error.message : null;
  const repairs = run?.summary?.repairs ?? [];
  const repairEvents = events.filter((e) => e.stage === "repair");

  return (
    <>
      <PageHeader eyebrow="Connect and test" title={c.app} badge={<StatusBadge status={c.status} />}
      >
        {c.from_library ? "From the platform library. Your own test runs on your own data first." : `Version ${c.version}`}
      </PageHeader>
      {error && <Banner tone="danger" title="That didn't work">{error}</Banner>}

      <div className="grid grid-cols-1 gap-6 lg:grid-cols-[400px_1fr]">
        <div className="space-y-4">
          <Card title="1. Connect">
            {replay ? (
              <p className="text-text-subdued">This tenant uses sample data, so no token is needed.</p>
            ) : (
              <>
                <Banner tone="info" title="This test calls the app's real API">There is no sample data for {c.app}, so paste a real token. Read-only calls only.</Banner>
                <ol className="mb-4 list-decimal space-y-1 pl-5 text-text-subdued">
                  {s.login.setup_steps.map((step) => <li key={step}>{step}</li>)}
                </ol>
                {s.login.scopes.length > 0 && (
                  <div className="mb-4">
                    <div className="caption mb-1">Give the token exactly these scopes</div>
                    <div className="flex flex-wrap gap-1">{s.login.scopes.map((x) => <Tag key={x}>✓ {x}</Tag>)}</div>
                  </div>
                )}
                <div className="space-y-3">
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
                  <Field label="Token owner's email" help="So we can warn you before this person leaves the company.">
                    <TextInput type="email" value={owner} onChange={(e) => setOwner(e.target.value)} />
                  </Field>
                </div>
              </>
            )}
            <div className="mt-4 rounded-sm bg-surface-subdued px-3 py-2 text-xs text-text-subdued">
              Encrypted. Read-only. Never shared with the AI.
            </div>
            <div className="mt-4 flex justify-end">
              <Button variant={passed ? "secondary" : "primary"} busy={running} onClick={startTest}>{run ? "Run the test again" : "Run test"}</Button>
            </div>
          </Card>
        </div>

        <div className="min-w-0">
          <Tabs
            value={tab}
            onChange={setTab}
            tabs={[{ id: "results", label: "Test results" }, { id: "code", label: "Generated code" }, { id: "log", label: "Run log", count: run?.logs?.length }]}
          />
          {tab === "results" && (
            <div className="space-y-4">
              <Card title="2. Test in the sandbox" aside={run && <Badge tone="neutral" icon={false}>{run.sandbox === "docker" ? "Docker sandbox" : "Subprocess · demo isolation only"}</Badge>}>
                <Stepper
                  steps={CHECKS.map((ch) => ({
                    label: ch.label,
                    state: checkState(ch.id),
                    detail: ch.id === "users" && run?.checklist?.users === "ok" && !running ? `${run.summary?.users} users, all pages` : ch.id === "usage" && run?.summary?.usage_sampled && !running ? "Sample (first pages only)" : undefined,
                  }))}
                />
                {repairEvents.length > 0 && running && <div className="caption">{repairEvents[repairEvents.length - 1].message}</div>}
              </Card>
              {preRunError && <Banner tone="danger" title="The test didn't run">{preRunError}</Banner>}
              {!running && !preRunError && run && run.exit_code !== 0 && (
                <Banner tone="danger" title={run.error_code === "HOST_BLOCKED" ? "Blocked: security event" : "The test didn't pass"}>{run.message ?? run.error_code}</Banner>
              )}
              {!running && run?.status === "partial" && (
                <Banner tone="warning" title="Users synced. Usage is blocked.">{run.usage_message} You can go live with users only.</Banner>
              )}
              {!running && repairs.length > 0 && (
                <Card title="Fixed automatically">
                  <ul className="space-y-1">
                    {repairs.map((r) => (
                      <li key={r.attempt}>
                        Try {r.attempt}: {r.accepted ? r.diagnosis : `rejected (${r.reason})`} <span className="caption">· {r.model}</span>
                      </li>
                    ))}
                  </ul>
                </Card>
              )}
              {passed && (
                <div className="flex justify-end">
                  <Button variant="primary" onClick={() => { toast("Test passed"); navigate(`/connectors/${id}/savings`); }}>See the savings</Button>
                </div>
              )}
            </div>
          )}
          {tab === "code" && (code ? <CodeBlock code={code} highlightItems /> : <span className="text-text-muted">No code yet</span>)}
          {tab === "log" && (
            <Card>
              {run?.logs?.length ? (
                <table className="w-full">
                  <thead>
                    <tr className="text-left text-xs text-text-subdued">
                      <th className="pb-2">Step</th><th className="pb-2">Request</th><th className="pb-2">Status</th><th className="pb-2 text-right">ms</th><th className="pb-2 text-right">Retry</th>
                    </tr>
                  </thead>
                  <tbody className="code">
                    {run.logs.map((l, i) => (
                      <tr key={i} className="border-t border-border">
                        <td className="py-1">{l.step}</td>
                        <td className="py-1">{l.method} {l.path}</td>
                        <td className="py-1"><Badge tone={l.status && l.status < 300 ? "success" : "danger"}>{l.status ?? "blocked"}</Badge></td>
                        <td className="py-1 text-right">{l.ms}</td>
                        <td className="py-1 text-right">{l.retry}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              ) : (
                <span className="text-text-muted">Run the test to see each request. Bodies and tokens are never logged.</span>
              )}
            </Card>
          )}
        </div>
      </div>
    </>
  );
}
