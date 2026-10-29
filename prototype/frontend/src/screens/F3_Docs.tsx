// F3 progress: Reading docs → Drafting → Checking evidence → Checking rules (live, over SSE).
import { useEffect, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { streamEvents, type PipelineEvent } from "../api";
import { Badge, Banner, Button, Card, PageHeader, Stepper, type StepState } from "../components/ui";

const STAGES = [
  { id: "fetch", label: "Reading docs" },
  { id: "draft", label: "Drafting the connector" },
  { id: "evidence", label: "Checking every answer against the docs" },
  { id: "rules", label: "Checking the safety rules" },
];

export default function BuildProgress() {
  const { id } = useParams();
  const navigate = useNavigate();
  const [events, setEvents] = useState<PipelineEvent[]>([]);

  useEffect(() => {
    let cancelled = false;
    setEvents([]);
    streamEvents(Number(id), (e) => !cancelled && setEvents((prev) => [...prev, e]));
    return () => {
      cancelled = true;
    };
  }, [id]);

  const done = events.find((e) => e.stage === "done");
  const ai = events.find((e) => e.stage === "ai");
  useEffect(() => {
    if (done?.status === "ok") {
      const t = setTimeout(() => navigate(`/connectors/${id}/found`), 700);
      return () => clearTimeout(t);
    }
  }, [done, id, navigate]);

  const state = (stage: string): { state: StepState; detail?: string } => {
    const mine = events.filter((e) => e.stage === stage);
    const last = mine[mine.length - 1];
    if (!last) return { state: done?.status === "fail" ? "waiting" : "waiting" };
    if (last.status === "start") return { state: "running", detail: last.message };
    if (last.status === "fail") return { state: "failed", detail: last.message };
    if (last.status === "warn") return { state: "warn", detail: last.message };
    return { state: "done", detail: last.message };
  };

  return (
    <>
      <PageHeader eyebrow="Build with AI" title="Building your connector" />
      <div className="max-w-[640px]">
        {ai && (
          <div className="mb-4">
            <Badge tone={ai.message === "Gemini" ? "info" : "warning"}>{ai.message === "Gemini" ? "AI: Gemini" : ai.message}</Badge>
          </div>
        )}
        <Card>
          <Stepper steps={STAGES.map((s) => ({ label: s.label, ...state(s.id) }))} />
        </Card>
        {done?.status === "fail" && (
          <div className="mt-4">
            <Banner tone="danger" title="We stopped here" action={<Button onClick={() => navigate(-1)}>Try another link</Button>}>
              {done.message}
            </Banner>
          </div>
        )}
      </div>
    </>
  );
}
