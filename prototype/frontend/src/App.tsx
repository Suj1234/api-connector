import { createContext, useCallback, useContext, useEffect, useState, type ReactNode } from "react";
import { NavLink, Navigate, Route, Routes, useNavigate } from "react-router-dom";
import { api, setTenant, tenant as currentTenant, type Status, type Tenant, type TenantId } from "./api";
import { ToastHost, cx } from "./components/ui";
import Inventory from "./screens/F1_Inventory";
import LibraryCheck from "./screens/F2_Library";
import BuildProgress from "./screens/F3_Docs";
import Found from "./screens/F4_Found";
import ConnectTest from "./screens/F5_ConnectTest";
import SavingsPreview from "./screens/F6_Savings";
import Detail from "./screens/F7_Detail";
import Internal from "./screens/F8_Internal";
import LibraryList from "./screens/Library";
import ConnectorRouter from "./screens/ConnectorRouter";

type Ctx = { tenant: TenantId; tenants: Tenant[]; status: Status | null; replay: boolean; refreshKey: number };
const AppContext = createContext<Ctx>({ tenant: "acme", tenants: [], status: null, replay: true, refreshKey: 0 });
export const useApp = () => useContext(AppContext);

export default function App() {
  const [tenantId, setTenantId] = useState<TenantId>(currentTenant());
  const [tenants, setTenants] = useState<Tenant[]>([]);
  const [status, setStatus] = useState<Status | null>(null);
  const [refreshKey, setRefreshKey] = useState(0);
  const navigate = useNavigate();

  useEffect(() => {
    api.get<Tenant[]>("/api/tenants").then(setTenants).catch(() => setTenants([]));
    api.get<Status>("/api/status").then(setStatus).catch(() => setStatus(null));
  }, []);

  const switchTenant = useCallback(
    (id: TenantId) => {
      setTenant(id);
      setTenantId(id);
      setRefreshKey((k) => k + 1);
      navigate(id === "internal" ? "/internal" : "/");
    },
    [navigate],
  );

  const current = tenants.find((t) => t.id === tenantId);
  const replay = current?.run_mode === "replay" && tenantId !== "internal";

  return (
    <AppContext.Provider value={{ tenant: tenantId, tenants, status, replay, refreshKey }}>
      {replay && (
        <div className="bg-demo px-6 py-1.5 text-center text-xs font-medium text-white" role="status">
          Demo data: recorded responses, fake people. No calls reach the real app.
        </div>
      )}
      <div className="flex min-h-screen">
        <Sidebar internal={tenantId === "internal"} />
        <div className="flex min-w-0 flex-1 flex-col">
          <TopBar tenants={tenants} tenantId={tenantId} onSwitch={switchTenant} status={status} />
          <main className="mx-auto w-full max-w-[1200px] flex-1 px-6 py-6" key={refreshKey}>
            <Routes>
              <Route path="/" element={tenantId === "internal" ? <Navigate to="/internal" /> : <Inventory />} />
              <Route path="/connect/:app" element={<LibraryCheck />} />
              <Route path="/connectors/:id" element={<ConnectorRouter />} />
              <Route path="/connectors/:id/build" element={<BuildProgress />} />
              <Route path="/connectors/:id/found" element={<Found />} />
              <Route path="/connectors/:id/connect" element={<ConnectTest />} />
              <Route path="/connectors/:id/savings" element={<SavingsPreview />} />
              <Route path="/connectors/:id/detail" element={<Detail />} />
              <Route path="/library" element={<LibraryList />} />
              <Route path="/internal" element={<Internal />} />
              <Route path="*" element={<Navigate to="/" />} />
            </Routes>
          </main>
        </div>
      </div>
      <ToastHost />
    </AppContext.Provider>
  );
}

function Sidebar({ internal }: { internal: boolean }) {
  const items = internal
    ? [{ to: "/internal", label: "Review queue" }, { to: "/library", label: "Library" }]
    : [{ to: "/", label: "App inventory" }, { to: "/library", label: "Library" }];
  return (
    <nav className="w-[240px] shrink-0 border-r border-border bg-surface px-3 py-4" aria-label="Main">
      <div className="mb-6 px-3">
        <div className="overline">The platform</div>
        <div className="heading-sm">Integration builder</div>
      </div>
      <ul className="space-y-0.5">
        {items.map((item) => (
          <li key={item.to}>
            <NavLink
              to={item.to}
              end
              className={({ isActive }) =>
                cx("block rounded-sm px-3 py-1.5 font-medium", isActive ? "bg-primary-subtle text-primary" : "text-text-subdued hover:bg-surface-subdued")
              }
            >
              {item.label}
            </NavLink>
          </li>
        ))}
      </ul>
    </nav>
  );
}

function TopBar({ tenants, tenantId, onSwitch, status }: { tenants: Tenant[]; tenantId: TenantId; onSwitch: (t: TenantId) => void; status: Status | null }) {
  const mode = (t: Tenant) => (t.internal ? "Platform team" : t.run_mode === "replay" ? "Demo data" : "Live");
  return (
    <header className="flex h-14 items-center justify-between border-b border-border px-6">
      <label className="flex items-center gap-2">
        <span className="caption">Tenant</span>
        <select
          value={tenantId}
          onChange={(e) => onSwitch(e.target.value as TenantId)}
          className="h-8 rounded-sm border border-border-strong bg-surface px-2 font-medium text-text-heading"
          aria-label="Switch tenant"
        >
          {tenants.map((t) => (
            <option key={t.id} value={t.id}>
              {t.internal ? t.name : `${t.name} · ${mode(t)}`}
            </option>
          ))}
        </select>
      </label>
      <div className="flex items-center gap-4 text-xs text-text-muted">
        {status && (
          <>
            <span>AI: {status.ai_provider === "gemini" ? `Gemini (${status.ai_model})` : "recorded answers (no model call)"}</span>
            <span>
              Sandbox: {status.sandbox === "docker" ? "Docker" : "subprocess"}
              {status.isolation_note && <span className="ml-1 font-medium text-warning-fg">· {status.isolation_note}</span>}
            </span>
          </>
        )}
      </div>
    </header>
  );
}

export function Section({ children }: { children: ReactNode }) {
  return <div className="space-y-4">{children}</div>;
}
