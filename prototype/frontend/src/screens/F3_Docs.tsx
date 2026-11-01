// F3 Build: reading the docs → drafting → checking evidence → checking rules, live over SSE.
// Each step says in plain words what is happening; the activity list shows what happened and when.
import { useEffect, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { api, streamEvents, type ConnectorDetail, type PipelineEvent } from "../api";
import { Banner, Button, Card, Spinner, Timeline, cx, type TimelineItem } from "../components/ui";
import { FlowPage, HintModal } from "./Flow";

const STAGES = [
  {
    id: "fetch",
    label: "Reading the docs",
    explain: "Opening the docs link and the pages it links to on the same site (up to 60), and looking for an OpenAPI file. Nothing goes to the AI yet.",
  },
  {
    id: "draft",
    label: "Drafting the connector",
    explain: "The AI reads the most useful parts of the docs and fills in the connector form: how to log in, where the users are, how paging works and what counts as usage. Every answer must quote the docs.",
  },
  {
    id: "evidence",
    label: "Checking the evidence",
    explain: "Checking that every quote really is on the page it came from. If one isn't, the AI is asked once more.",
  },
  {
    id: "rules",
    label: "Checking the safety rules",
    explain: "The connector may only read data, only call the app's own address, and never put a secret in a link.",
  },
];

const seconds = (from?: string, to?: string | number) => (from ? Math.max(0, Math.round(((typeof to === "number" ? to : to ? Date.parse(to) : Date.now()) - Date.parse(from)) / 1000)) : 0);
export const duration = (s: number) => (s < 60 ? `${s} s` : `${Math.floor(s / 60)} min ${s % 60} s`);

export default function BuildProgress() {
  const { id } = useParams();
  const navigate = useNavigate();
  const [c, setC] = useState<ConnectorDetail | null>(null);
  const [events, setEvents] = useState<PipelineEvent[]>([]);
  const [now, setNow] = useState(Date.now());
  const [run, setRun] = useState(0); // a new draft (Try again, a hint) starts a new stream
  const [hintOpen, setHintOpen] = useState(false);

  useEffect(() => {
    api.get<ConnectorDetail>(`/api/connectors/${id}`).then(setC);
    const closed = new AbortController();
    setEvents([]);
    streamEvents(Number(id), (e) => setEvents((prev) => [...prev, e]), closed.signal);
    return () => closed.abort();
  }, [id, run]);

  const tryAgain = async () => {
    await api.post(`/api/connectors/${id}/hint`, { text: "" });
    setRun((n) => n + 1);
  };

  const done = events.find((e) => e.stage === "done");
  // A file-only build has no link to open.
  const explain = (s: (typeof STAGES)[number]) => (s.id === "fetch" && c && !c.docs_url ? "Reading the OpenAPI file you uploaded. Nothing goes to the AI yet." : s.explain);
  // These stops are about the docs themselves: a hint or the same docs again can't help, another link can.
  const docsProblem = ["DOCS_WRONG_APP", "DOCS_NOT_API", "DOCS_UNREADABLE", "SSRF_BLOCKED", "NO_USERS_API"].includes(done?.code ?? "");
  const anotherLink = () => navigate(c ? `/connect/${encodeURIComponent(c.app)}` : "/");
  useEffect(() => {
    if (done) return;
    const t = setInterval(() => setNow(Date.now()), 1000);
    return () => clearInterval(t);
  }, [done]);
  useEffect(() => {
    if (done?.status === "ok") {
      const t = setTimeout(() => navigate(`/connectors/${id}/found`), 1200);
      return () => clearTimeout(t);
    }
  }, [done, id, navigate]);

  const started = events[0]?.at;
  const ai = events.find((e) => e.stage === "ai");
  const last = (stage: string) => events.filter((e) => e.stage === stage).pop();
  const state = (stage: string) => {
    const e = last(stage);
    return !e ? "waiting" : e.status === "start" ? "running" : e.status === "fail" ? "failed" : "done";
  };
  const currentIndex = Math.max(0, STAGES.findIndex((s) => state(s.id) !== "done"));
  const current = STAGES[currentIndex];
  const failed = done?.status === "fail";
  const elapsed = seconds(started, done?.at ?? now);

  // Newest first, as the reference Timeline lists events.
  const activity: TimelineItem[] = [];
  if (ai) activity.push({ title: `AI model: ${ai.message}`, time: "Started", icon: "bulb" });
  for (const s of STAGES) {
    const begin = events.find((e) => e.stage === s.id && e.status === "start");
    const end = events.find((e) => e.stage === s.id && e.status !== "start");
    if (end) {
      activity.push({
        title: `${s.label}: ${end.message || (end.status === "fail" ? "failed" : "done")}`,
        time: `Took ${duration(seconds(begin?.at, end.at))}`,
        tone: end.status === "fail" ? "danger" : end.status === "warn" ? "warning" : "success",
      });
    } else if (begin && !done) {
      activity.push({ title: `${s.label}…`, time: `${duration(seconds(begin.at, now))} so far`, busy: true });
    }
  }
  activity.reverse();

  return (
    <FlowPage
      app={c?.app ?? null}
      step="build"
      status={c && (failed ? "Stopped" : done ? "Draft ready" : "Building")}
      substeps={STAGES.map((s, i) => ({ label: s.label, current: !done && i === currentIndex }))}
      title={c ? `Building the ${c.app} connector` : "Building your connector"}
      intro="This usually takes 1 to 2 minutes. You can leave this page; the build keeps going."
    >
      {failed ? (
        <Banner
          tone="danger"
          title={`We stopped at ${current.label.toLowerCase()}`}
          action={
            docsProblem ? (
              <Button small variant="primary" onClick={anotherLink}>Use another docs link</Button>
            ) : (
              <>
                <Button small onClick={() => setHintOpen(true)}>Add a hint</Button>
                <Button small onClick={tryAgain}>Try again</Button>
              </>
            )
          }
        >
          {done?.message}
          {!docsProblem && (
            <>
              {" "}
              <button type="button" className="font-semibold text-link hover:underline" onClick={anotherLink}>
                Use another docs link
              </button>
            </>
          )}
        </Banner>
      ) : done ? (
        <Banner tone="success" title={`Done in ${duration(elapsed)}`}>Opening what we found…</Banner>
      ) : (
        <Card>
          <div className="flex items-start gap-3">
            <Spinner large />
            <div className="min-w-0 flex-1">
              <div className="flex flex-wrap items-baseline justify-between gap-x-4">
                <h2 className="text-base font-bold text-text-heading">
                  Step {currentIndex + 1} of {STAGES.length}: {current.label}
                </h2>
                <span className="text-text-muted">{duration(elapsed)} so far</span>
              </div>
              <p className="mt-1 text-text-subdued">{explain(current)}</p>
            </div>
          </div>
          {/* The reference bar: one segment per step, 2px apart. */}
          <div className="mt-4 flex h-2 gap-0.5 overflow-hidden rounded-[2px]" role="img" aria-label={`Step ${currentIndex + 1} of ${STAGES.length}`}>
            {STAGES.map((s, i) => (
              <span key={s.id} className={cx("block h-full flex-1", i < currentIndex ? "bg-primary" : i === currentIndex ? "bg-primary-tint" : "bg-border")} />
            ))}
          </div>
        </Card>
      )}

      <Card title="What each step does">
        <ol className="grid gap-3">
          {STAGES.map((s, i) => (
            <li key={s.id} className="grid grid-cols-[16px_1fr] gap-3">
              <span className="pt-0.5 text-[13px] font-semibold text-text-muted">{i + 1}</span>
              <div>
                <div className="font-semibold text-text">{s.label}</div>
                <div className="text-text-subdued">{explain(s)}</div>
              </div>
            </li>
          ))}
        </ol>
      </Card>

      <HintModal connectorId={id ?? ""} open={hintOpen} onClose={() => setHintOpen(false)} onSent={() => { setHintOpen(false); setRun((n) => n + 1); }} />

      {activity.length > 0 && (
        <Card title="Activity">
          <Timeline items={activity} />
        </Card>
      )}
    </FlowPage>
  );
}
