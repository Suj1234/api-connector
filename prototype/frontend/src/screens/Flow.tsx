// The build flow as one full-screen task, the reference pattern for setup flows: FocusHeader on top,
// the Stepper on the left, the current step on the right. Read the docs → review → connect and test →
// savings → go live.
import { useState, type ReactNode } from "react";
import { useNavigate } from "react-router-dom";
import { api } from "../api";
import { Button, Field, FocusHeader, Modal, Stepper, Textarea } from "../components/ui";

const STEPS = [
  { id: "build", label: "Read the docs" },
  { id: "found", label: "Review what we found" },
  { id: "connect", label: "Connect and test" },
  { id: "savings", label: "Check the savings" },
  { id: "live", label: "Go live" },
] as const;
export type FlowStep = (typeof STEPS)[number]["id"];

export function FlowPage({ app, step, status, actions, substeps, title, intro, children }: {
  app: string | null;
  step: FlowStep;
  status?: ReactNode;
  actions?: ReactNode;
  substeps?: { label: string; current?: boolean }[];
  title: string;
  intro?: ReactNode;
  children: ReactNode;
}) {
  const navigate = useNavigate();
  const at = STEPS.findIndex((s) => s.id === step);
  return (
    <div className="min-h-screen bg-surface">
      <FocusHeader
        title={app ? `Connect ${app}` : "Connect an app"}
        status={status}
        actions={actions}
        onClose={() => navigate(app ? `/apps/${encodeURIComponent(app)}` : "/")}
      />
      <div className="mx-auto grid max-w-[1200px] grid-cols-1 gap-8 px-4 py-8 md:grid-cols-[200px_minmax(0,1fr)] md:px-6">
        <nav aria-label="Steps" className="md:sticky md:top-[84px] md:self-start">
          <Stepper
            steps={STEPS.map((s, i) => ({
              label: s.label,
              status: i < at ? "done" : i === at ? "active" : "pending",
              substeps: i === at ? substeps : undefined,
            }))}
          />
        </nav>
        <main className="grid min-w-0 content-start gap-6">
          <div>
            <h1 className="title">{title}</h1>
            {intro && <div className="mt-1 text-text-subdued">{intro}</div>}
          </div>
          {children}
        </main>
      </div>
    </div>
  );
}

// "This looks wrong" / "Add a hint": the AI drafts again with the admin's hint as a suggestion (F4, and F3 when a
// build stops). Then the build page shows the new run.
export function HintModal({ connectorId, open, onClose, onSent }: { connectorId: string | number; open: boolean; onClose: () => void; onSent: () => void }) {
  const [hint, setHint] = useState("");
  const [busy, setBusy] = useState(false);
  const send = async () => {
    setBusy(true);
    await api.post(`/api/connectors/${connectorId}/hint`, { text: hint });
    setBusy(false);
    setHint("");
    onSent();
  };
  return (
    <Modal
      open={open}
      title="What looks wrong?"
      onClose={onClose}
      footer={
        <>
          <Button onClick={onClose}>Cancel</Button>
          <Button variant="primary" busy={busy} disabled={!hint.trim()} onClick={send}>Re-draft with this hint</Button>
        </>
      }
    >
      <div className="grid gap-4">
        <p className="text-text-subdued">The AI drafts the form again with your hint as a suggestion. The docs still decide: every answer needs a quote from them.</p>
        <Field label="Your hint" help="Emails, links with parameters, long numbers, names and tokens are removed before the AI sees it. 500 characters at most.">
          <Textarea rows={4} maxLength={500} value={hint} onChange={(e) => setHint(e.target.value)} placeholder="For example: the users list is under /members, and the token needs the admin role." />
        </Field>
        <div>
          <div className="font-semibold text-text">Hints that help point at a fact in the docs</div>
          <ul className="mt-1 list-disc space-y-0.5 pl-5 text-text-subdued">
            <li>Where the users are: "Users come from /members, not /users."</li>
            <li>What counts as usage: "Count events each person hosted, from /events."</li>
            <li>The role or scopes: "The token needs the Owner role."</li>
            <li>A page to read: "The rate limit is on the rate-limits page."</li>
          </ul>
        </div>
      </div>
    </Modal>
  );
}
