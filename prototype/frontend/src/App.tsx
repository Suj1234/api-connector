import { useEffect, useState } from "react";
import { NavLink, Navigate, Outlet, Route, Routes, useLocation, useNavigate, useSearchParams } from "react-router-dom";
import { api, whenLoggedOut, type Status } from "./api";
import { Icon, Logo, SearchInput, ToastHost, cx } from "./components/ui";
import Inventory from "./screens/F1_Inventory";
import AppPage from "./screens/AppPage";
import BuildProgress from "./screens/F3_Docs";
import Found from "./screens/F4_Found";
import ConnectTest from "./screens/F5_ConnectTest";
import SavingsPreview from "./screens/F6_Savings";
import Detail from "./screens/F7_Detail";
import ConnectorRouter from "./screens/ConnectorRouter";
import Login from "./screens/Login";

// The reference AppShell: Sidebar, TopBar, page. One customer on screen; the tenant switcher,
// Library and review queue are built but hidden for now (PRD §15).
type Session = { required: boolean; logged_in: boolean };

export default function App() {
  const [session, setSession] = useState<Session | null>(null);
  const [status, setStatus] = useState<Status | null>(null);

  useEffect(() => {
    whenLoggedOut(() => setSession({ required: true, logged_in: false }));
    api.get<Session>("/api/session").then(setSession);
  }, []);

  const signedIn = session !== null && (!session.required || session.logged_in);
  useEffect(() => {
    if (signedIn) api.get<Status>("/api/status").then(setStatus).catch(() => setStatus(null));
  }, [signedIn]);

  if (session === null) return null;
  if (!signedIn) return <Login onDone={() => setSession({ required: true, logged_in: true })} />;

  const logOut = async () => {
    await api.post("/api/logout").catch(() => undefined);
    setSession({ required: true, logged_in: false });
  };

  return (
    <>
      <Routes>
        {/* The build flow is one full-screen task (Flow.tsx); everything else sits in the app shell. */}
        <Route path="/connectors/:id/build" element={<BuildProgress />} />
        <Route path="/connectors/:id/found" element={<Found />} />
        <Route path="/connectors/:id/connect" element={<ConnectTest />} />
        <Route path="/connectors/:id/savings" element={<SavingsPreview />} />
        <Route element={<Shell status={status} onLogOut={session.required ? logOut : undefined} />}>
          <Route path="/" element={<Inventory />} />
          {/* The Add an app / Connect usage data drawer opens over the inventory. */}
          <Route path="/connect" element={<Inventory />} />
          <Route path="/connect/:app" element={<Inventory />} />
          <Route path="/apps/:app" element={<AppPage />} />
          <Route path="/connectors/:id" element={<ConnectorRouter />} />
          <Route path="/connectors/:id/detail" element={<Detail />} />
          <Route path="*" element={<Navigate to="/" />} />
        </Route>
      </Routes>
      <ToastHost />
    </>
  );
}

function Shell({ status, onLogOut }: { status: Status | null; onLogOut?: () => void }) {
  return (
    <div className="flex min-h-screen">
      <Sidebar status={status} />
      <div className="flex min-w-0 flex-1 flex-col">
        <TopBar onLogOut={onLogOut} />
        <main className="flex-1 px-6 pb-8 pt-2">
          <Outlet />
        </main>
        <footer className="px-6 py-4 text-xs text-text-muted">© 2026 Integration builder</footer>
      </div>
    </div>
  );
}

const modelName = (s: Status) =>
  s.ai_provider === "gemini" && s.ai_model ? s.ai_model.split("-").map((w) => w[0].toUpperCase() + w.slice(1)).join(" ") : "Recorded answers";

// Reference Sidebar: 244px, 30px items with icons, blurple current page, footer item at the bottom.
function Sidebar({ status }: { status: Status | null }) {
  const { pathname } = useLocation();
  const connecting = pathname.startsWith("/connect/") || pathname === "/connect" || pathname.startsWith("/apps/"); // still the inventory
  return (
    <nav aria-label="Main" className="sticky top-0 flex h-screen w-[244px] shrink-0 flex-col gap-5 border-r border-border bg-surface px-3 py-4">
      <div className="px-2">
        <Logo />
      </div>
      <div className="grid gap-0.5">
        <NavLink
          to="/"
          end
          className={({ isActive }) =>
            cx("flex h-[30px] items-center gap-2 rounded-sm px-2 hover:bg-surface-subdued", isActive || connecting ? "font-semibold text-link" : "font-medium text-text")
          }
        >
          <Icon name="grid" className={cx("h-4 w-4", connecting || pathname === "/" ? "text-link" : "text-text-subdued")} />
          App inventory
        </NavLink>
      </div>
      {status && (
        <div className="mt-auto grid gap-0.5">
          <div className="px-2 pb-1 text-xs text-text-subdued">AI model</div>
          <div className="flex h-[30px] items-center gap-2 px-2 font-medium text-text">
            <Icon name="bulb" className="h-4 w-4 text-text-subdued" />
            {modelName(status)}
          </div>
        </div>
      )}
    </nav>
  );
}

// Reference TopBar: 60px, search on the left. The search filters the App inventory.
function TopBar({ onLogOut }: { onLogOut?: () => void }) {
  const [params] = useSearchParams();
  const { pathname } = useLocation();
  const navigate = useNavigate();
  const q = pathname === "/" ? (params.get("q") ?? "") : "";
  return (
    <header className="flex h-[60px] shrink-0 items-center gap-4 bg-surface px-6">
      <div className="max-w-[560px] flex-1">
        <SearchInput
          value={q}
          placeholder="Search apps or owners"
          onChange={(v) => navigate(v ? `/?q=${encodeURIComponent(v)}` : "/", { replace: pathname === "/" })}
        />
      </div>
      {onLogOut && (
        <button type="button" onClick={onLogOut} className="ml-auto h-7 rounded-sm px-2 text-[13px] font-semibold text-text-subdued hover:bg-surface-subdued">
          Log out
        </button>
      )}
    </header>
  );
}
