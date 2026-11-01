// The demo login: one shared email and password, set on the server. Layout: DESIGN.md §8 "Login".
import { useState } from "react";
import { api } from "../api";
import { Banner, Button, Field, Logo, TextInput } from "../components/ui";

const EMAIL = /^[^\s@]+@[^\s@]+\.[^\s@]{2,}$/;

const Eye = ({ open }: { open: boolean }) => (
  <svg aria-hidden viewBox="0 0 20 20" className="h-5 w-5" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
    <path d="M2 10s3-6 8-6 8 6 8 6-3 6-8 6-8-6-8-6z" />
    <circle cx="10" cy="10" r="2.5" />
    {!open && <path d="M3 17L17 3" />}
  </svg>
);

export default function Login({ onDone }: { onDone: () => void }) {
  const [email, setEmail] = useState("");
  const [emailTouched, setEmailTouched] = useState(false);
  const [password, setPassword] = useState("");
  const [showPassword, setShowPassword] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const emailOk = EMAIL.test(email.trim());
  const ready = emailOk && password.length > 0;

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!ready) return;
    setBusy(true);
    setError(null);
    try {
      await api.post("/api/login", { username: email.trim(), password });
      onDone();
    } catch (err) {
      setError((err as Error).message);
      setBusy(false);
    }
  };

  return (
    <div className="relative flex min-h-screen flex-col overflow-hidden bg-surface">
      <div aria-hidden className="auth-art" />

      <header className="relative px-6 py-5 md:px-10">
        <Logo onArt />
      </header>

      <main className="relative flex flex-1 items-center justify-center px-4 py-8">
        <form onSubmit={submit} noValidate className="auth-card h-fit w-full max-w-[480px] overflow-hidden rounded-md bg-surface shadow-modal">
          <div className="px-8 pb-10 pt-10 md:px-12">
            <h1 className="mb-6 text-2xl font-medium text-text-heading">Log in to your account</h1>
            {error && (
              <div className="mb-5">
                <Banner tone="danger">{error}</Banner>
              </div>
            )}
            <div className="space-y-5">
              <Field label="Email" error={emailTouched && email && !emailOk ? "Enter a valid email, like name@company.com" : null}>
                <TextInput
                  large
                  type="email"
                  autoComplete="username"
                  placeholder="name@company.com"
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  onBlur={() => setEmailTouched(true)}
                />
              </Field>
              <Field label="Password">
                <div className="relative">
                  <TextInput
                    large
                    className="pr-10"
                    type={showPassword ? "text" : "password"}
                    autoComplete="current-password"
                    value={password}
                    onChange={(e) => setPassword(e.target.value)}
                  />
                  <button
                    type="button"
                    onClick={() => setShowPassword(!showPassword)}
                    aria-label={showPassword ? "Hide password" : "Show password"}
                    className="absolute inset-y-0 right-0 flex w-10 items-center justify-center rounded-sm text-text-muted hover:text-text"
                  >
                    <Eye open={showPassword} />
                  </button>
                </div>
              </Field>
            </div>
            <div className="mt-7">
              <Button variant="primary" type="submit" block busy={busy} disabled={!ready}>{busy ? "Logging in…" : "Log in"}</Button>
            </div>
          </div>
          <p className="border-t border-border bg-surface-subdued px-8 py-4 text-center text-text-subdued">
            Access is by invite. Please reach out to Sujeet Kumar for your email and password.
          </p>
        </form>
      </main>

      <footer className="caption relative px-6 pb-6 md:px-10">© 2026 Integration builder</footer>
    </div>
  );
}
