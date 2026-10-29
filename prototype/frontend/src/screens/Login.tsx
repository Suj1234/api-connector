// The demo login: one shared username and password, set on the server.
import { useState } from "react";
import { api } from "../api";
import { Banner, Button, Field, TextInput } from "../components/ui";

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
    <div className="flex min-h-screen items-center justify-center bg-surface-subdued px-4">
      <form onSubmit={submit} className="w-[360px] rounded-md border border-border bg-surface p-6">
        <div className="overline">The platform</div>
        <h1 className="heading mb-6">Integration builder</h1>
        {error && <Banner tone="danger">{error}</Banner>}
        <div className="space-y-4">
          <Field label="Username">
            <TextInput autoComplete="username" value={username} onChange={(e) => setUsername(e.target.value)} />
          </Field>
          <Field label="Password">
            <TextInput type="password" autoComplete="current-password" value={password} onChange={(e) => setPassword(e.target.value)} />
          </Field>
        </div>
        <div className="mt-6 flex justify-end">
          <Button variant="primary" type="submit" busy={busy} disabled={!username || !password}>Log in</Button>
        </div>
      </form>
    </div>
  );
}
