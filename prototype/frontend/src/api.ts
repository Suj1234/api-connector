// Thin client for the backend (TRD §9). Every call carries X-Tenant.

export type TenantId = "acme" | "globex" | "internal";

// One customer on screen for now; the tenant switcher comes back later (PRD §13).
let currentTenant: TenantId = "acme";

export function setTenant(t: TenantId): void {
  currentTenant = t;
  try {
    localStorage.setItem("tenant", t);
  } catch {
    /* private mode: the tenant just isn't remembered */
  }
}

export function tenant(): TenantId {
  return currentTenant;
}

let onUnauthorized: (() => void) | null = null;
export function whenLoggedOut(handler: () => void): void {
  onUnauthorized = handler;
}

export class ApiError extends Error {
  constructor(
    public status: number,
    message: string,
  ) {
    super(message);
  }
}

async function request<T>(method: string, path: string, body?: unknown, form?: FormData): Promise<T> {
  const headers: Record<string, string> = { "X-Tenant": currentTenant };
  if (body !== undefined) headers["Content-Type"] = "application/json";
  const response = await fetch(path, {
    method,
    headers,
    body: form ?? (body !== undefined ? JSON.stringify(body) : undefined),
  });
  if (response.status === 401 && path !== "/api/login") {
    onUnauthorized?.();
  }
  if (!response.ok) {
    let message = response.statusText;
    try {
      const data = await response.json();
      message = typeof data.detail === "string" ? data.detail : message;
    } catch {
      /* not JSON */
    }
    throw new ApiError(response.status, message);
  }
  const type = response.headers.get("content-type") || "";
  return (type.includes("json") ? response.json() : response.text()) as Promise<T>;
}

export const api = {
  get: <T>(path: string) => request<T>("GET", path),
  post: <T>(path: string, body?: unknown) => request<T>("POST", path, body ?? {}),
  form: <T>(path: string, form: FormData) => request<T>("POST", path, undefined, form),
  del: <T>(path: string) => request<T>("DELETE", path),
};

export type PipelineEvent = {
  stage: string;
  status: string;
  message?: string;
  code?: string;
  seq: number;
  at?: string; // when the server recorded it
  run_id?: string;
  verified_pct?: number;
  attempt?: number;
};

/** Server-sent progress events. EventSource can't send headers, so the stream is read with fetch.
 *  The server closes a stream after about 5 minutes (a hosting limit), and connections drop: until the
 *  job's "done" event arrives, it reconnects and skips the events it has already passed on. */
export async function streamEvents(connectorId: number, onEvent: (e: PipelineEvent) => void, signal?: AbortSignal): Promise<void> {
  let next = 0;
  for (let tries = 0; tries < 10 && !signal?.aborted; tries++) {
    let fresh = false;
    try {
      const response = await fetch(`/api/connectors/${connectorId}/events`, { headers: { "X-Tenant": currentTenant }, signal });
      if (!response.ok || !response.body) return;
      const reader = response.body.getReader();
      const decoder = new TextDecoder();
      let buffer = "";
      for (;;) {
        const { value, done } = await reader.read();
        if (done) break;
        buffer += decoder.decode(value, { stream: true });
        const parts = buffer.split("\n\n");
        buffer = parts.pop() ?? "";
        for (const part of parts) {
          if (!part.startsWith("data: ")) continue;
          const event = JSON.parse(part.slice(6)) as PipelineEvent;
          if (event.seq < next) continue;
          next = event.seq + 1;
          fresh = true;
          onEvent(event);
          if (event.stage === "done") return;
        }
      }
      if (!fresh) return; // a whole stream with nothing new: no job is running
    } catch {
      if (signal?.aborted) return; // the screen was closed
    }
    await new Promise((r) => setTimeout(r, 1000));
  }
}

// --- response types -----------------------------------------------------------------

export type Tenant = { id: TenantId; name: string; internal: boolean; run_mode: "live" | "replay" };
export type Status = { ai_provider: string; ai_model: string | null; sandbox: string; isolation_note: string | null };

export type InventoryRow = {
  app: string;
  owner: string | null;
  annual_cost: number | null;
  seats: number | null;
  renewal_date: string | null;
  days_to_renewal: number | null;
  usage_status: string;
  connector: { id: number; status: string; sample: boolean } | null; // sample: recorded answers, fake people
  in_library: boolean;
  library_spec_id: number | null;
  removable: "app" | "connector" | null; // what Delete removes; null for the sample apps
};

export type AppUser = {
  external_id: string;
  email: string | null;
  name: string | null;
  role: string | null;
  status: "active" | "suspended" | "deactivated" | "invited" | "unknown";
  is_admin: boolean | null;
  is_billable: boolean | null;
  license_type: string | null;
  last_active_at: string | null;
  usage_metric_value: number | null;
  usage_metric_label: string | null;
  usage_window_days: number | null;
  usage_available: boolean;
  usage_is_proxy: boolean;
  excluded_reason: string | null;
};
export type AppUsers = { as_of: string; sample: boolean; users: AppUser[] };

export type EvidenceRow = {
  field: string;
  value: unknown;
  quote: string | null;
  url: string | null;
  openapi_pointer: string | null;
  verified: boolean;
  problem: string | null;
};

export type Conflict = { field: string; values: { value: unknown; source: string }[]; chosen: unknown; reason: string };

export type RunView = {
  id: string;
  status: string;
  exit_code: number | null;
  error_code: string | null;
  usage_error_code: string | null;
  message: string | null;
  usage_message: string | null;
  summary: { users?: number; usage_sampled?: boolean; warnings?: string[]; repairs?: Repair[]; isolation?: string | null; pages?: Record<string, number> } | null;
  checklist: Record<string, string>;
  sandbox: string;
  run_mode: string;
  finished_at: string | null;
  logs?: { step: string; method: string; path: string; status: number | null; ms: number; retry: number }[];
};

export type Repair = { attempt: number; model: string; accepted: boolean; diagnosis?: string; reason?: string };

export type Summary = {
  login: {
    type: string;
    role_required: string | null;
    scopes: string[];
    setup_steps: string[];
    fields: { name: string; label: string; secret: boolean }[];
    variables: { name: string; label: string; example: string; pattern: string }[];
  };
  users: { path: string; records_path: string; pagination: string; fields: string[] };
  usage: {
    tier: string;
    tier_reason: string;
    label: string | null;
    proxy: boolean;
    fallback: string | null;
    path: string | null;
    window_days: number | null;
  };
  limits: { requests_per_minute: number; plan_note: string | null };
  host: string;
};

export type ConnectorDetail = {
  id: number;
  app: string;
  tenant: TenantId;
  status: string;
  tier: string | null;
  run_mode: "live" | "replay";
  docs_url: string | null;
  from_library: boolean;
  ai_source: string | null;
  error: { code: string; message: string } | null;
  token_owner_email: string | null;
  has_credentials: boolean;
  variables: Record<string, string>;
  summary: Summary | null;
  evidence: EvidenceRow[];
  conflicts: Conflict[];
  warnings: string[];
  version: number | null;
  versions: { version: number; created_by: string; created_at: string }[];
  evidence_pct: number | null;
  last_run: RunView | null;
  library: { status: string; id: number } | null;
  confirm_note: string | null;
  token_owner_warning: string | null;
};

export type Savings = {
  app: string;
  users: number;
  buckets: Record<"excluded" | "left" | "not_in_hr" | "inactive" | "active" | "usage_unknown", number>;
  billable_users: number;
  seats: number | null;
  never_assigned: number | null;
  price_per_seat: number | null;
  recoverable_seats: number | null;
  recoverable_annual: number | null;
  renewal_date: string | null;
  days_to_renewal: number | null;
  sso_assigned: number | null;
  mismatch_pct: number | null;
  needs_note: boolean;
  usage_label: string;
  usage_source: string;
  missing: string[];
  people: { external_id: string; name: string | null; email: string | null; bucket: string; reason: string; usage_metric_value: number | null; last_active_at: string | null }[];
  contract_source: string;
  run_mode: string;
  token_owner_warning: string | null;
};

export type LibraryRow = { id: number; app: string; version: number; tier: string; used_by: string; health: string; reviewed_by: string | null };
export type ReviewItem = { id: number; app: string; version: number; status: string; flags: string[]; tier: string; host: string; summary: Summary; code: string };
