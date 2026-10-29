// The demo login: one shared username and password, set on the server.
import { useState } from "react";
import { api } from "../api";
import { Banner, Button, Field, TextInput } from "../components/ui";

const FACTS = [
  ["Reads the app's public API docs", "AI fills a small connector spec and quotes the docs for every field."],
  ["Writes no free-form code", "Fixed templates turn the spec into code that only makes read calls to one host."],
  ["Tests before anything goes live", "Each connector runs in a sandbox and shows the seat savings first."],
];

export default function Login({ onDone }: { onDone: () => void }) {
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      await api.post("/api/login", { username, password });
      onDone();
    } catch (err) {
      setError((err as Error).message);
      setBusy(false);
    }
  };

  return (
    <div className="flex min-h-screen">
      <main className="flex w-full flex-col px-6 py-6 md:w-1/2 md:px-12">
        <div>
          <div className="overline">The platform</div>
          <div className="heading-sm">Integration builder</div>
        </div>
        <form onSubmit={submit} className="my-auto w-full max-w-[360px] py-12">
          <h1 className="title">Log in</h1>
          <p className="mb-6 mt-1 text-text-subdued">Use the username and password you were given.</p>
          {error && <Banner tone="danger">{error}</Banner>}
          <div className="space-y-4">
            <Field label="Username">
              <TextInput autoComplete="username" value={username} onChange={(e) => setUsername(e.target.value)} />
            </Field>
            <Field label="Password">
              <TextInput type="password" autoComplete="current-password" value={password} onChange={(e) => setPassword(e.target.value)} />
            </Field>
          </div>
          <div className="mt-6">
            <Button variant="primary" type="submit" busy={busy} disabled={!username || !password}>Log in</Button>
          </div>
        </form>
        <p className="caption">Prototype. Access is shared by link and can be withdrawn at any time.</p>
      </main>
      <aside className="hidden w-1/2 border-l border-border bg-surface-subdued px-12 py-6 md:flex md:flex-col md:justify-center">
        <div className="max-w-[440px]">
          <div className="overline mb-2">What it does</div>
          <h2 className="heading">Connect any SaaS app's user and usage data, without waiting for a custom integration.</h2>
          <ul className="mt-8 space-y-6">
            {FACTS.map(([title, text]) => (
              <li key={title} className="border-l-2 border-primary pl-4">
                <div className="font-medium text-text-heading">{title}</div>
                <div className="mt-0.5 text-text-subdued">{text}</div>
              </li>
            ))}
          </ul>
        </div>
      </aside>
    </div>
  );
}
