"""Backend API (TRD §9). Every call carries X-Tenant: acme | globex | internal (no real login)."""

from __future__ import annotations

import asyncio
import base64
import copy
import hashlib
import hmac
import json
import os
import re
import threading
import time
import traceback
import uuid
from collections.abc import AsyncIterator, Awaitable, Callable
from datetime import UTC, date, datetime
from typing import Annotated, Any
from urllib.parse import urlsplit

from fastapi import Depends, FastAPI, File, Form, Header, HTTPException, Request, Response, UploadFile
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse, PlainTextResponse, StreamingResponse
from pydantic import BaseModel
from sqlalchemy import delete, func, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.config import DOCS_CACHE, PROTOTYPE, get, on_vercel, writable_data_dir
from app.db import INVENTORY, Database
from app.models.tables import (
    AppUser,
    AuditEvent,
    Connector,
    ConnectorVersion,
    Credential,
    CrosscheckFile,
    InventoryApp,
    JobEvent,
    LibrarySpec,
    LlmCall,
    Run,
    RunRequest,
    Tenant,
    TokenRequest,
)
from app.services import ai_source, evidence_check, savings
from app.services.codegen import render, slug_for
from app.services.docs_fetcher import DocsBundle, Fetcher
from app.services.hints import scrub_hint
from app.services.pipeline import Pipeline, PipelineError, Settings
from app.services.sandbox import DEMO_ISOLATION_LABEL, SANDBOX
from app.services.ssrf_guard import SSRFBlockedError, check_url
from app.services.vault import Sealed, Vault
from runtime import helpers as h

REPLAY = PROTOTYPE / "fixtures" / "replay"
EXAMPLES = PROTOTYPE / "specs" / "examples"
SAMPLE_APPS = ("Zendesk", "Notion", "Slack")  # connected on sample data in a fresh database (PRD §0)
SAMPLE_SOURCE = "Hand-written spec"  # how a sample app's connector is labelled; Delete leaves it alone
TENANTS = ("acme", "globex", "internal")
LIBRARY_MIN_SHOWN = 5
PLAIN = {
    "AUTH_REJECTED": "The token was rejected. Create a new one and reconnect.",
    "PERMISSION_OR_SCOPE": "This token can't read this data. It needs: {scopes} and the role {role}.",
    "PAID_ONLY": "Your {app} plan doesn't include this data. Users will still sync.",
    "WRONG_REQUEST": "We used the wrong request. We tried to fix it automatically.",
    "MAPPING_FAILED": "The app's data didn't match what we expected. We tried to fix it automatically.",
    "PAGINATION_LOOP": "Paging didn't work the way the docs describe. We tried to fix it automatically.",
    "CURSOR_EXPIRED": "Paging didn't work the way the docs describe. We tried to fix it automatically.",
    "RATE_LIMITED_OUT": "The app is limiting requests. Retry in a few minutes.",
    "TIMEOUT": "The app was too slow to answer. Retry later.",
    "SERVER_ERROR": "The app is having problems right now. Retry later.",
    "UNREACHABLE": "We couldn't reach {host} from the sandbox. Check that this machine can reach the internet, then retry.",
    "HOST_BLOCKED": "Blocked: the connector tried to reach a server other than {host}. Nothing was sent. The platform team has been alerted.",
    "RULES_REJECTED": "This draft broke a safety rule ({detail}), so we discarded it. No code was generated or run.",
    "DOCS_UNREADABLE": "We couldn't read these docs. Upload the app's OpenAPI file or try another docs link.",
    "SSRF_BLOCKED": "That link points to a private or internal address. Use the app's public docs link.",
    "SCHEMA_INVALID": "The AI's draft didn't fit the connector format, even after one retry. Check that the link is the app's API reference, then add a hint and try again.",
    "LLM_ERROR": "The AI service didn't answer: {detail}",
    "BAD_INPUT": "Some connection details are missing or wrong ({detail}). Add them under Connect, then test again.",
    "BAD_LINK": "Paste the docs link in full, starting with https://, with no spaces.",
    "DOCS_WRONG_APP": "These docs never mention {detail}. Check that the link is {detail}'s API docs, or upload its OpenAPI file.",
    "DOCS_NOT_API": "These pages don't look like an API reference: {detail}. Use the link to the app's API reference, or upload its OpenAPI file.",
    "NO_USERS_API": "{detail}'s API doesn't list your company's users: the only user endpoint in these docs returns just the token's own account. Look in its docs for an admin or members endpoint, or keep using SSO data for {detail}.",
    "NO_DEMO_DATA": "There is no demo data for this app, so the test needs its real API and a token.",
    "CODEGEN_FAILED": "The generated code failed its checks. The platform team has been told.",
}  # fmt: skip


class State:
    def __init__(self) -> None:
        self.db = Database()
        fresh = self.db.seed()
        self.vault = Vault(_vault_key())
        self.bundles: dict[int, DocsBundle] = {}
        if fresh and get("SAMPLE_APPS", "1") == "1":
            if on_vercel():
                # Vercel pauses a function between requests, so a background thread stalls. The first visit after
                # a fresh database waits about a minute instead, once.
                _prebuild_samples(self)
            else:
                threading.Thread(target=_prebuild_samples, args=(self,), daemon=True).start()

    def settings(self) -> Settings:
        return Settings()


def _vault_key() -> str:
    key = get("VAULT_KEY")
    if key:
        return key
    if on_vercel():
        # Every server instance must derive the same key. Without VAULT_KEY it comes from the demo
        # login; changing DEMO_PASSWORD then also retires every token saved under the old one.
        seed = f"vault|{get('DEMO_USERNAME')}|{get('DEMO_PASSWORD')}".encode()
        return base64.b64encode(hashlib.sha256(seed).digest()).decode()
    # Local development only: a generated key kept beside the database, never committed.
    path = writable_data_dir() / ".vault_key"
    path.parent.mkdir(parents=True, exist_ok=True)
    if not path.exists():
        path.write_text(Vault.new_master_key())
        os.chmod(path, 0o600)
    return path.read_text().strip()


app = FastAPI(title="Integration builder prototype")


@app.exception_handler(Exception)
async def unexpected_error(request: Request, error: Exception) -> JSONResponse:
    # One short line: hosted logs cut long tracebacks off before the error itself.
    origin = traceback.extract_tb(error.__traceback__)[-1]
    print(
        f"UNEXPECTED {request.url.path}: {type(error).__name__}: {str(error)[:500]} at {origin.filename}:{origin.lineno}"
    )
    return JSONResponse({"detail": "Something went wrong on our side."}, status_code=500)


@app.exception_handler(RequestValidationError)
async def invalid_request(request: Request, error: RequestValidationError) -> JSONResponse:
    """One plain sentence naming the fields, instead of the framework's list (which echoes the values)."""
    fields = sorted({str(e["loc"][-1]).replace("_", " ") for e in error.errors() if e.get("loc")})
    return JSONResponse({"detail": f"Check these fields: {', '.join(fields)}."}, status_code=422)


app.add_middleware(CORSMiddleware, allow_origins=["http://localhost:5173"], allow_methods=["*"], allow_headers=["*"])
_state: State | None = None

# --- login (one shared demo login, set on the server: DEMO_USERNAME / DEMO_PASSWORD) ------------

SESSION_COOKIE = "session"
SESSION_HOURS = 12
OPEN_PATHS = {"/api/login", "/api/session", "/api/logout"}


def _login_required() -> bool:
    return bool(get("DEMO_PASSWORD"))


def _logins() -> list[tuple[str, str]]:
    # TEST_USERNAME / TEST_PASSWORD: an optional second login for automated end-to-end tests.
    pairs = [(get("DEMO_USERNAME"), get("DEMO_PASSWORD")), (get("TEST_USERNAME"), get("TEST_PASSWORD"))]
    return [(user, password) for user, password in pairs if user and password]


def _session_key() -> bytes:
    # Changing (or removing) either password changes the key, so every old session stops working at once.
    secrets = "|".join(f"{user}|{password}" for user, password in _logins())
    return hashlib.sha256(f"{_vault_key()}|{secrets}".encode()).digest()


def _sign(expires: int) -> str:
    mac = hmac.new(_session_key(), str(expires).encode(), hashlib.sha256).hexdigest()
    return f"{expires}.{mac}"


def _valid(token: str | None) -> bool:
    if not token or "." not in token:
        return False
    expires, _, _ = token.partition(".")
    return expires.isdigit() and int(expires) > time.time() and hmac.compare_digest(token, _sign(int(expires)))


@app.middleware("http")
async def require_login(request: Request, call_next: Callable[[Request], Awaitable[Response]]) -> Response:
    path = request.url.path
    locked = _login_required() and path.startswith("/api/") and path not in OPEN_PATHS
    if locked and not _valid(request.cookies.get(SESSION_COOKIE)):
        return JSONResponse({"detail": "Please log in"}, status_code=401)
    return await call_next(request)


class Login(BaseModel):
    username: str
    password: str


@app.post("/api/login")
def login(body: Login, request: Request) -> JSONResponse:
    matches = [
        hmac.compare_digest(body.username.encode(), user.encode()) & hmac.compare_digest(body.password.encode(), password.encode())
        for user, password in _logins()
    ]  # fmt: skip
    if not _login_required() or not any(matches):
        time.sleep(0.5)  # slows down password guessing
        raise HTTPException(401, "Wrong username or password")
    response = JSONResponse({"logged_in": True})
    https = request.headers.get("x-forwarded-proto", request.url.scheme) == "https"
    response.set_cookie(
        SESSION_COOKIE, _sign(int(time.time()) + SESSION_HOURS * 3600), max_age=SESSION_HOURS * 3600,
        httponly=True, samesite="lax", secure=https,
    )  # fmt: skip
    return response


@app.get("/api/session")
def session_status(request: Request) -> dict[str, bool]:
    return {"required": _login_required(), "logged_in": _valid(request.cookies.get(SESSION_COOKIE))}


@app.post("/api/logout")
def logout() -> JSONResponse:
    response = JSONResponse({"logged_in": False})
    response.delete_cookie(SESSION_COOKIE)
    return response


_state_lock = threading.Lock()


def state() -> State:
    global _state
    with _state_lock:  # the first requests arrive together; only one may create the tables
        if _state is None:
            _state = State()
    return _state


def tenant_header(x_tenant: Annotated[str, Header()] = "acme") -> str:
    if x_tenant not in TENANTS:
        raise HTTPException(400, "Unknown tenant")
    return x_tenant


Tenant_ = Annotated[str, Depends(tenant_header)]
State_ = Annotated[State, Depends(state)]


def _internal(tenant: str) -> None:
    if tenant != "internal":
        raise HTTPException(403, "Platform team only")


def _connector(s: Session, tenant: str, connector_id: int) -> Connector:
    connector = s.get(Connector, connector_id)
    if connector is None or (connector.tenant_id != tenant and tenant != "internal"):
        raise HTTPException(404, "No such connector")
    return connector


def _latest(s: Session, connector_id: int) -> ConnectorVersion | None:
    return s.scalar(
        select(ConnectorVersion)
        .where(ConnectorVersion.connector_id == connector_id)
        .order_by(ConnectorVersion.version.desc())
        .limit(1)
    )


def _message(code: str | None, spec: dict[str, Any] | None = None, detail: str = "", host: str = "") -> str | None:
    if not code:
        return None
    template = PLAIN.get(code, code)
    auth = (spec or {}).get("auth", {})
    if code == "BAD_INPUT":  # the field's label ("API token"), not its name ("access_token")
        for field in auth.get("fields", []):
            detail = re.sub(rf"\b{re.escape(field['name'])}\b", field["label"], detail)
    return template.format(
        scopes=", ".join(auth.get("scopes", [])) or "no special scopes",
        role=auth.get("role_required") or "admin",
        app=(spec or {}).get("app", {}).get("name", "the app"),
        host=host or (spec or {}).get("app", {}).get("api_host_pattern", "its own host"),
        detail=detail,
    )


def _library_for(s: Session, app_name: str) -> LibrarySpec | None:
    return s.scalar(
        select(LibrarySpec)
        .where(LibrarySpec.app == app_name, LibrarySpec.status == "approved")
        .order_by(LibrarySpec.version.desc())
        .limit(1)
    )


# --- tenants, inventory, library --------------------------------------------------------------


@app.get("/api/tenants")
def tenants(st: State_) -> list[dict[str, Any]]:
    with st.db.session() as s:
        return [
            {"id": t.id, "name": t.name, "internal": t.is_internal, "run_mode": t.run_mode_default}
            for t in s.scalars(select(Tenant))
        ]


@app.get("/api/status")
def status(st: State_) -> dict[str, Any]:
    settings = st.settings()
    provider = ai_source.provider()
    return {
        "ai_provider": provider,
        "ai_model": settings.draft_model if provider == "gemini" else None,
        "sandbox": SANDBOX,
        "isolation_note": DEMO_ISOLATION_LABEL,
    }


@app.get("/api/inventory")
def inventory(tenant: Tenant_, st: State_) -> list[dict[str, Any]]:
    today = datetime.now(UTC).date()  # renewals are calendar dates, even for sample data
    with st.db.session() as s:
        rows = []
        for item in s.scalars(select(InventoryApp).where(InventoryApp.tenant_id == tenant)):
            connectors = _connectors_of(s, tenant, item.app)
            connector = connectors[0] if connectors else None
            library = _library_for(s, item.app)
            usage_status = "No usage data"
            if connector is not None and connector.status.startswith("live"):
                usage_status = "Connected" if connector.status == "live" else "Users only"
            rows.append(
                {
                    "app": item.app,
                    "owner": item.owner,
                    "annual_cost": item.annual_cost,
                    "seats": item.seats,
                    "renewal_date": item.renewal_date.isoformat() if item.renewal_date else None,
                    "days_to_renewal": (item.renewal_date - today).days if item.renewal_date else None,
                    "usage_status": usage_status,
                    "connector": {
                        "id": connector.id,
                        "status": connector.status,
                        "sample": connector.run_mode == "replay",
                    }
                    if connector
                    else None,
                    "in_library": library is not None,
                    "library_spec_id": library.id if library else None,
                    "removable": _removable(connectors, tenant, item.app),
                }
            )
        # Apps the admin added themselves (not in the spend data): newest connector per app.
        listed = {row["app"] for row in rows}
        for connector in s.scalars(
            select(Connector).where(Connector.tenant_id == tenant).order_by(Connector.id.desc())
        ):
            if connector.app in listed:
                continue
            listed.add(connector.app)
            status = connector.status
            rows.append(
                {
                    "app": connector.app, "owner": None, "annual_cost": None, "seats": None,
                    "renewal_date": None, "days_to_renewal": None,
                    "usage_status": "Connected" if status == "live" else "Users only" if status == "live_users_only" else "No usage data",
                    "connector": {"id": connector.id, "status": status, "sample": connector.run_mode == "replay"},
                    "in_library": False, "library_spec_id": None,
                    "removable": _removable(_connectors_of(s, tenant, connector.app), tenant, connector.app),
                }
            )  # fmt: skip
        return rows


@app.get("/api/library")
def library(st: State_) -> list[dict[str, Any]]:
    with st.db.session() as s:
        out = []
        for spec in s.scalars(select(LibrarySpec).where(LibrarySpec.status == "approved")):
            used = len(
                list(
                    s.scalars(
                        select(Connector).where(Connector.from_library_id == spec.id, Connector.status.like("live%"))
                    )
                )
            )
            out.append(
                {
                    "id": spec.id,
                    "app": spec.app,
                    "version": spec.version,
                    "tier": spec.spec_json.get("app", {}).get("tier"),
                    "used_by": str(used) if used >= LIBRARY_MIN_SHOWN else "fewer than 5",
                    "health": "healthy" if not spec.failure_rate else f"{spec.failure_rate:.0%} failing",
                    "reviewed_by": spec.reviewed_by,
                }
            )
        return out


# --- connectors ---------------------------------------------------------------------------


class NewApp(BaseModel):
    app: str
    owner: str | None = None
    annual_cost: float | None = None
    seats: int | None = None
    renewal_date: date | None = None


def _add_to_inventory(
    s: Session,
    tenant: str,
    app_name: str,
    owner: str | None,
    annual_cost: float | None,
    seats: int | None,
    renewal_date: date | None,
) -> None:
    """Add an app the spend data doesn't have yet, with the same details every inventory app has."""
    app_name, owner = app_name.strip(), (owner or "").strip()
    if not app_name or len(app_name) > 100:
        raise HTTPException(422, "Give the app's name (up to 100 characters)")
    # Chained comparisons are False for NaN, so NaN and infinity are refused too.
    if (
        not owner
        or len(owner) > 100
        or annual_cost is None
        or not 0 <= annual_cost <= 1e9
        or seats is None
        or not 1 <= seats <= 1_000_000
        or renewal_date is None
    ):
        raise HTTPException(
            422, "Give the owner, the annual spend, the number of seats (at least 1) and the renewal date"
        )
    if renewal_date < date.today():
        raise HTTPException(422, "The renewal date has passed. Give the next one.")
    same = s.scalar(
        select(InventoryApp).where(InventoryApp.tenant_id == tenant, func.lower(InventoryApp.app) == app_name.lower())
    )
    if same is not None:
        raise HTTPException(
            409, f"{same.app} is already in your inventory. Open its row to connect it or see its users."
        )
    s.add(
        InventoryApp(
            tenant_id=tenant, app=app_name, owner=owner, annual_cost=annual_cost, seats=seats, renewal_date=renewal_date,
        )
    )  # fmt: skip


@app.post("/api/inventory")
def add_inventory_app(body: NewApp, tenant: Tenant_, st: State_) -> dict[str, Any]:
    """The drawer's Save app: into the inventory, without building a connector yet."""
    with st.db.session() as s:
        _add_to_inventory(s, tenant, body.app, body.owner, body.annual_cost, body.seats, body.renewal_date)
        s.commit()
    return {"app": body.app.strip()}


@app.post("/api/connectors")
async def create_connector(
    tenant: Tenant_,
    st: State_,
    app_name: Annotated[str, Form()],
    docs_url: Annotated[str | None, Form()] = None,
    from_library_spec_id: Annotated[int | None, Form()] = None,
    openapi_file: Annotated[UploadFile | None, File()] = None,
    owner: Annotated[str | None, Form()] = None,
    annual_cost: Annotated[float | None, Form()] = None,
    seats: Annotated[int | None, Form()] = None,
    renewal_date: Annotated[date | None, Form()] = None,
) -> dict[str, Any]:
    openapi = await openapi_file.read() if openapi_file is not None else None
    app_name, docs_url = app_name.strip(), (docs_url or "").strip()
    if not app_name or len(app_name) > 100:
        raise HTTPException(422, "Give the app's name (up to 100 characters)")
    parts = urlsplit(docs_url)
    if docs_url and (parts.scheme not in ("http", "https") or not parts.hostname or any(c.isspace() for c in docs_url)):
        raise HTTPException(422, PLAIN["BAD_LINK"])
    if from_library_spec_id is None and not docs_url and openapi is None:
        raise HTTPException(400, "Paste the app's API docs link or upload its OpenAPI file")
    adding = any(v is not None for v in (owner, annual_cost, seats, renewal_date))  # "Add an app"
    with st.db.session() as s:
        t = s.get(Tenant, tenant)
        if adding:
            _add_to_inventory(s, tenant, app_name, owner, annual_cost, seats, renewal_date)
        connector = Connector(
            tenant_id=tenant, app=app_name, status="draft", docs_url=docs_url or None,
            run_mode=_run_mode_for(t, app_name), variables={},
        )  # fmt: skip
        s.add(connector)
        s.flush()
        connector_id = connector.id
        if from_library_spec_id is not None:
            spec = s.get(LibrarySpec, from_library_spec_id)
            if spec is None or spec.status != "approved":
                raise HTTPException(404, "Not in the library")
            connector.from_library_id = spec.id
            connector.tier = spec.spec_json["app"]["tier"]
            s.add(
                ConnectorVersion(
                    connector_id=connector_id, version=1, spec_json=copy.deepcopy(spec.spec_json),
                    created_by="library", approved_by=spec.reviewed_by,
                )
            )  # fmt: skip
            connector.job_kind, connector.job_state = "library", "done"
            s.commit()
            _emit(st, connector_id, {"stage": "library", "status": "ok", "message": "From the platform library"})
            _emit(st, connector_id, {"stage": "done", "status": "ok"})
            return {"id": connector_id}
        s.commit()
    _start_draft(st, connector_id, app_name, docs_url, openapi, None)
    return {"id": connector_id}


# --- jobs: queued by a POST, run by the request that streams their progress -------------------

JOB_TIMEOUT_S = 290  # stays inside a serverless request limit (300 s on Vercel)


def _queue(st: State, connector_id: int, kind: str, args: dict[str, Any]) -> None:
    with st.db.session() as s:
        s.execute(delete(JobEvent).where(JobEvent.connector_id == connector_id))
        c = s.get(Connector, connector_id)
        assert c is not None
        c.job_kind, c.job_state, c.job_args, c.job_started_at = kind, "queued", args, None
        s.commit()


def _emit(st: State, connector_id: int, event: dict[str, Any]) -> None:
    for _ in range(5):
        with st.db.session() as s:
            last = s.scalar(
                select(JobEvent.seq).where(JobEvent.connector_id == connector_id).order_by(JobEvent.seq.desc()).limit(1)
            )
            seq = 0 if last is None else last + 1
            # "at": the screens show how long each step took.
            data = {**event, "seq": seq, "at": datetime.now(UTC).isoformat()}
            s.add(JobEvent(connector_id=connector_id, seq=seq, data=data))
            try:
                s.commit()
                return
            except IntegrityError:
                s.rollback()  # another writer took this seq; try the next one


def _events_since(st: State, connector_id: int, seq: int) -> list[dict[str, Any]]:
    with st.db.session() as s:
        rows = s.scalars(
            select(JobEvent).where(JobEvent.connector_id == connector_id, JobEvent.seq >= seq).order_by(JobEvent.seq)
        )
        return [dict(r.data) for r in rows]


def _claim(st: State, connector_id: int) -> str | None:
    """The first stream to arrive runs the job; a stuck job (its server instance died) is taken over."""
    with st.db.session() as s:
        c = s.get(Connector, connector_id)
        if c is None or c.job_kind is None or c.job_state == "done":
            return None
        started = (
            c.job_started_at.replace(tzinfo=UTC)
            if c.job_started_at and c.job_started_at.tzinfo is None
            else c.job_started_at
        )
        stale = (
            c.job_state == "running"
            and started is not None
            and (datetime.now(UTC) - started).total_seconds() > JOB_TIMEOUT_S + 30
        )
        if c.job_state != "queued" and not stale:
            return None
        claimed = s.execute(
            update(Connector)
            .where(Connector.id == connector_id, Connector.job_state == c.job_state)
            .values(job_state="running", job_started_at=datetime.now(UTC))
        )
        s.commit()
        return c.job_kind if claimed.rowcount == 1 else None  # type: ignore[attr-defined]


def _run_job(st: State, connector_id: int, kind: str) -> None:
    with st.db.session() as s:
        c = s.get(Connector, connector_id)
        assert c is not None
        args = dict(c.job_args or {})
    try:
        if kind == "draft":
            _run_draft(st, connector_id, args)
        elif kind == "test":
            _run_test(st, connector_id, args)
    except Exception as error:  # noqa: BLE001 - a job must always end with a "done" event
        print(f"JOB_FAILED {kind} connector={connector_id}: {type(error).__name__}: {str(error)[:300]}")
        _fail(st, connector_id, "SERVER_ERROR", type(error).__name__)
    finally:
        with st.db.session() as s:
            c = s.get(Connector, connector_id)
            if c is not None:
                c.job_state = "done"
                s.commit()


def _run_mode_for(t: Tenant | None, app_name: str) -> str:
    """Demo-data tenants replay the recordings we have; any other app (a surprise app) runs live."""
    mode = t.run_mode_default if t else "live"
    if mode == "replay" and not (REPLAY / slug_for(app_name) / "recording.json").exists():
        return "live"
    return mode


def _start_draft(
    st: State, connector_id: int, app_name: str, docs_url: str, openapi: bytes | None, hint: str | None
) -> None:
    openapi_text = base64.b64encode(openapi).decode() if openapi else None
    _queue(
        st, connector_id, "draft", {"app_name": app_name, "docs_url": docs_url, "openapi": openapi_text, "hint": hint}
    )


def _run_draft(st: State, connector_id: int, args: dict[str, Any]) -> None:
    app_name, docs_url, hint = args["app_name"], args["docs_url"], args.get("hint")
    openapi = base64.b64decode(args["openapi"]) if args.get("openapi") else None

    def emit(event: dict[str, Any]) -> None:
        _emit(st, connector_id, event)

    if docs_url:
        try:
            check_url(docs_url)  # first, in every mode: no offline shortcut may skip it
        except SSRFBlockedError as error:
            _fail(st, connector_id, "SSRF_BLOCKED", str(error))
            return
    try:
        llm, label = ai_source.llm_for(app_name)
    except Exception as error:  # noqa: BLE001
        _fail(st, connector_id, "LLM_ERROR", str(error))
        return
    with st.db.session() as s:
        c = s.get(Connector, connector_id)
        assert c is not None
        c.ai_source = label
        s.commit()
    emit({"stage": "ai", "status": "info", "message": label})
    pipe = Pipeline(llm, Fetcher(), emit, st.settings())
    bundle = st.bundles.get(connector_id)
    if bundle is None and label != "Gemini":
        bundle = _offline_bundle(docs_url)
    try:
        outcome = pipe.draft(app_name, docs_url, openapi, hint, bundle)
    except PipelineError as error:
        with st.db.session() as s:  # a stopped build's AI calls still count in its cost
            for call in error.calls:
                s.add(LlmCall(connector_id=connector_id, **call.__dict__))
            s.commit()
        _fail(st, connector_id, error.code, error.message)
        return
    except Exception as error:  # noqa: BLE001
        _fail(st, connector_id, "LLM_ERROR", f"{type(error).__name__}")
        return
    st.bundles[connector_id] = outcome.bundle
    if label == "Gemini":
        ai_source.save_recording(app_name, outcome.raw_draft)
    with st.db.session() as s:
        connector = s.get(Connector, connector_id)
        assert connector is not None
        latest = _latest(s, connector_id)
        report = {
            "verified": outcome.evidence.verified,
            "failed": outcome.evidence.failed,
            "dropped": outcome.dropped,
            "pct": round(outcome.evidence.verified_pct, 1),
        }
        s.add(
            ConnectorVersion(
                connector_id=connector_id, version=(latest.version + 1) if latest else 1, spec_json=outcome.spec,
                created_by="ai", evidence_report=report, llm_cost_usd=sum(c.cost_usd for c in outcome.llm_calls),
            )
        )  # fmt: skip
        for call in outcome.llm_calls:
            s.add(LlmCall(connector_id=connector_id, **call.__dict__))
        connector.status, connector.tier = "draft", outcome.spec["app"]["tier"]
        connector.error_code = connector.error_message = None
        s.commit()
    emit({"stage": "done", "status": "ok"})


def _offline_bundle(docs_url: str) -> DocsBundle | None:
    """Recorded mode without network: use cached docs if we have them, else let the fetcher try."""
    for cached in DOCS_CACHE.glob("*.json"):
        data = json.loads(cached.read_text())
        if data.get("start_url") == docs_url:
            from app.services.docs_fetcher import DocPage

            return DocsBundle(
                docs_url, [DocPage(**p) for p in data["pages"]], data.get("openapi"), data.get("openapi_url")
            )
    try:
        return Fetcher().fetch(docs_url, 20)
    except Exception:  # noqa: BLE001 - offline demo: evidence will show as unproved, honestly
        return DocsBundle(docs_url)


def _fail(st: State, connector_id: int, code: str, message: str) -> None:
    with st.db.session() as s:
        connector = s.get(Connector, connector_id)
        if connector is not None:
            connector.status, connector.error_code, connector.error_message = "needs_help", code, message
            s.commit()
    _emit(
        st, connector_id, {"stage": "done", "status": "fail", "code": code, "message": _message(code, detail=message)}
    )


@app.get("/api/connectors/{connector_id}/events")
async def events(connector_id: int, tenant: Tenant_, st: State_) -> StreamingResponse:
    with st.db.session() as s:
        _connector(s, tenant, connector_id)
    kind = _claim(st, connector_id)
    worker = threading.Thread(target=_run_job, args=(st, connector_id, kind), daemon=True) if kind else None
    if worker is not None:
        worker.start()

    async def stream() -> AsyncIterator[str]:
        seq = 0
        deadline = time.monotonic() + JOB_TIMEOUT_S + 10
        while time.monotonic() < deadline:
            for event in await asyncio.to_thread(_events_since, st, connector_id, seq):
                seq = event["seq"] + 1
                yield f"data: {json.dumps(event)}\n\n"
                if event["stage"] == "done":
                    return
            if worker is None and not await asyncio.to_thread(_job_pending, st, connector_id):
                return  # nothing running anywhere and nothing left to send
            await asyncio.sleep(0.3)

    return StreamingResponse(stream(), media_type="text/event-stream", headers={"Cache-Control": "no-cache"})


def _job_pending(st: State, connector_id: int) -> bool:
    with st.db.session() as s:
        c = s.get(Connector, connector_id)
        return c is not None and c.job_state in ("queued", "running")


@app.get("/api/connectors/{connector_id}")
def connector_detail(connector_id: int, tenant: Tenant_, st: State_) -> dict[str, Any]:
    with st.db.session() as s:
        c = _connector(s, tenant, connector_id)
        version = _latest(s, connector_id)
        spec = version.spec_json if version else None
        run = s.get(Run, c.last_run_id) if c.last_run_id else None
        submitted = s.scalar(
            select(LibrarySpec).where(LibrarySpec.app == c.app, LibrarySpec.submitted_from_tenant == c.tenant_id)
        )
        versions = list(
            s.scalars(
                select(ConnectorVersion)
                .where(ConnectorVersion.connector_id == connector_id)
                .order_by(ConnectorVersion.version)
            )
        )
        # A repaired version keeps the AI draft's evidence report: the repair changed a few paths, not the proof.
        report = next((v.evidence_report for v in reversed(versions) if v.evidence_report), None)
        return {
            "id": c.id,
            "app": c.app,
            "tenant": c.tenant_id,
            "status": c.status,
            "tier": c.tier,
            "run_mode": c.run_mode,
            "docs_url": c.docs_url,
            "from_library": c.from_library_id is not None,
            "ai_source": c.ai_source,
            "error": {"code": c.error_code, "message": _message(c.error_code, spec, c.error_message or "")}
            if c.error_code
            else None,
            "token_owner_email": c.token_owner_email,
            "has_credentials": s.scalar(select(Credential).where(Credential.connector_id == c.id)) is not None,
            "variables": c.variables,
            "summary": _summary(spec) if spec else None,
            "evidence": _evidence(spec, report) if spec else [],
            "conflicts": (spec or {}).get("conflicts", []),
            "warnings": (spec or {}).get("warnings", []),
            "version": version.version if version else None,
            "versions": [
                {"version": v.version, "created_by": v.created_by, "created_at": _utc_iso(v.created_at)}
                for v in versions
            ],
            "evidence_pct": (report or {}).get("pct"),
            "last_run": _run_view(run, spec) if run else None,
            "library": {"status": submitted.status, "id": submitted.id} if submitted else None,
            "confirm_note": c.confirm_note,
            "token_owner_warning": _token_owner_warning(s, c),
        }


def _token_owner_warning(s: Session, c: Connector) -> str | None:
    """SC-13: warn before the person who owns the token leaves (HRIS)."""
    owner = (c.token_owner_email or "").lower()
    if not owner:
        return None
    hris = s.scalar(
        select(CrosscheckFile).where(CrosscheckFile.tenant_id == c.tenant_id, CrosscheckFile.kind == "hris")
    )
    row = savings.parse_files(c.app, hris.content if hris else None, None, None).hris.get(owner)
    if row is None or row.get("employment_status") != "terminated":
        return None
    when = row.get("termination_date") or "soon"
    return f"The token owner ({owner}) leaves on {when}. Switch to a service account before then."


def _summary(spec: dict[str, Any]) -> dict[str, Any]:
    auth, users, usage = spec["auth"], spec["streams"]["users"], spec["streams"]["usage"]
    usage_def = spec["usage_definition"]
    return {
        "login": {
            "type": auth["type"],
            "role_required": auth.get("role_required"),
            "scopes": auth.get("scopes", []),
            "setup_steps": auth.get("setup_steps", []),
            "fields": auth["fields"],
            "variables": spec.get("variables", []),
        },
        "users": {
            "path": users["path"],
            "records_path": users["records_path"],
            "pagination": users["pagination"]["type"],
            "fields": sorted(users["field_map"]),
        },
        "usage": {
            "tier": spec["app"]["tier"],
            "tier_reason": spec["app"]["tier_reason"],
            "label": usage_def.get("metric_label"),
            "proxy": usage_def.get("proxy"),
            "fallback": usage_def.get("fallback"),
            "path": usage["path"] if usage else None,
            "window_days": usage["aggregate"]["window_days"] if usage else None,
        },
        "limits": {
            "requests_per_minute": spec["rate_limit"]["requests_per_minute"],
            "plan_note": spec["rate_limit"].get("plan_note"),
        },
        "host": spec["app"]["api_host_pattern"],
    }


def _value_at(spec: dict[str, Any], pointer: str) -> Any:
    node: Any = spec
    for part in pointer.strip("/").split("/"):
        node = node.get(part) if isinstance(node, dict) else None
    return node


def _evidence(spec: dict[str, Any], report: dict[str, Any] | None) -> list[dict[str, Any]]:
    out = []
    verified = set((report or {}).get("verified", []))
    failed = (report or {}).get("failed", {})
    for pointer in evidence_check.required_pointers(spec):
        item = evidence_check._evidence_for(spec.get("evidence", {}), pointer)  # noqa: SLF001
        out.append(
            {
                "field": pointer,
                "value": _value_at(spec, pointer),
                "quote": (item or {}).get("quote"),
                "url": (item or {}).get("url"),
                "openapi_pointer": (item or {}).get("pointer"),
                "verified": pointer in verified,
                "problem": failed.get(pointer) if spec.get("origin") == "ai" else "hand-written (no evidence needed)",
            }
        )
    return out


class Hint(BaseModel):
    text: str


@app.post("/api/connectors/{connector_id}/hint")
def hint(connector_id: int, body: Hint, tenant: Tenant_, st: State_) -> dict[str, Any]:
    with st.db.session() as s:
        c = _connector(s, tenant, connector_id)
        names = [u.name or "" for u in s.scalars(select(AppUser).where(AppUser.tenant_id == tenant))]
        secrets = list(_secrets(s, st, c).values())
        app_name, docs_url = c.app, c.docs_url or ""
        # An uploaded OpenAPI file is drafted from again; it is kept with the last draft job.
        previous = (c.job_args or {}).get("openapi") if c.job_kind == "draft" else None
    scrubbed = scrub_hint(body.text, secrets, names)  # empty: "Try again" with the same docs and no hint
    _start_draft(
        st, connector_id, app_name, docs_url, base64.b64decode(previous) if previous else None, scrubbed or None
    )
    return {"scrubbed_hint": scrubbed}


class Credentials(BaseModel):
    secrets: dict[str, str] = {}
    variables: dict[str, str] = {}
    token_owner_email: str | None = None


@app.post("/api/connectors/{connector_id}/credentials")
def credentials(connector_id: int, body: Credentials, tenant: Tenant_, st: State_) -> dict[str, Any]:
    """Write-only: secrets are sealed in the vault and never returned or logged."""
    with st.db.session() as s:
        c = _connector(s, tenant, connector_id)
        # A field left empty keeps the value saved before ("Run the test again" sends no token).
        kept = _secrets(s, st, c)
        sealed = st.vault.seal(tenant, connector_id, {**kept, **{k: v for k, v in body.secrets.items() if v}})
        s.execute(delete(Credential).where(Credential.connector_id == connector_id))
        s.add(
            Credential(
                connector_id=connector_id, ciphertext=sealed.ciphertext, nonce=sealed.nonce, key_id=sealed.key_id
            )
        )
        c.variables = {k: v.strip() for k, v in body.variables.items()}
        c.token_owner_email = (body.token_owner_email or "").strip().lower() or None
        s.commit()
    return {"saved": True}


def _secrets(s: Session, st: State, c: Connector) -> dict[str, str]:
    cred = s.scalar(select(Credential).where(Credential.connector_id == c.id))
    if cred is None:
        return {}
    return st.vault.open(c.tenant_id, c.id, Sealed(cred.ciphertext, cred.nonce, cred.key_id))


class TestRequest(BaseModel):
    run_mode: str | None = None


@app.post("/api/connectors/{connector_id}/test")
def test(connector_id: int, body: TestRequest, tenant: Tenant_, st: State_) -> dict[str, Any]:
    with st.db.session() as s:
        c = _connector(s, tenant, connector_id)
        if c.job_kind == "test" and c.job_state in ("queued", "running"):
            return {"run_id": (c.job_args or {})["run_id"]}  # a second click joins the test already running
        version = _latest(s, connector_id)
        if version is None:
            raise HTTPException(409, "Nothing to test yet")
        run_mode = body.run_mode or c.run_mode
        if (
            run_mode == "replay"
            and not (REPLAY / slug_for(version.spec_json["app"]["name"]) / "recording.json").exists()
        ):
            raise HTTPException(409, _message("NO_DEMO_DATA"))
        c.status = "testing"
        s.commit()
    run_id = str(uuid.uuid4())
    _queue(st, connector_id, "test", {"run_id": run_id, "run_mode": run_mode, "tenant": tenant})
    return {"run_id": run_id}


def _run_test(st: State, connector_id: int, args: dict[str, Any]) -> None:
    run_id, run_mode, tenant = args["run_id"], args["run_mode"], args["tenant"]
    with st.db.session() as s:
        c = s.get(Connector, connector_id)
        version = _latest(s, connector_id)
        assert c is not None and version is not None
        spec = copy.deepcopy(version.spec_json)
        payload: dict[str, Any] = {
            "run_mode": run_mode,
            "variables": dict(c.variables or {}),
            "context": {"tenant": tenant, "run_id": run_id, "connector": slug_for(c.app), "version": version.version},
        }
        if run_mode == "replay":
            payload["replay_file"] = str(REPLAY / slug_for(spec["app"]["name"]) / "recording.json")
        else:
            payload["secrets"] = _secrets(s, st, c)  # decrypted only here, for the sandbox's stdin
        start_version = version.version

    def emit(event: dict[str, Any]) -> None:
        _emit(st, connector_id, event)

    try:
        llm, _ = ai_source.llm_for(spec["app"]["name"])
    except Exception:  # noqa: BLE001 - tests still run; only repairs need the model
        llm = ai_source.RecordedLLM(spec["app"]["name"])
    pipe = Pipeline(llm, Fetcher(), emit, st.settings())
    started = datetime.now(UTC)
    try:
        outcome = pipe.test(spec, payload, st.bundles.get(connector_id), start_version)
    except PipelineError as error:
        _fail(st, connector_id, error.code, error.message)
        return
    result = outcome.result
    summary = result.result
    with st.db.session() as s:
        c = s.get(Connector, connector_id)
        assert c is not None
        final_version = start_version + sum(1 for r in outcome.repairs if r["accepted"])
        if final_version != start_version:
            s.add(
                ConnectorVersion(
                    connector_id=connector_id, version=final_version, spec_json=outcome.spec,
                    created_by="repair", code=outcome.code,
                )
            )  # fmt: skip
        for call in outcome.llm_calls:
            s.add(LlmCall(connector_id=connector_id, **call.__dict__))
        kept = [line for line in result.lines if line.get("type") in ("progress", "log", "result")]
        s.add(
            Run(
                id=run_id, connector_id=connector_id, version=final_version, mode="test",
                run_mode=run_mode, sandbox=result.sandbox,
                status=summary.get("status", "error") if summary.get("status") in ("ok", "partial", "error") else "error",
                exit_code=result.exit_code, error_code=summary.get("error_code"),
                usage_error_code=summary.get("usage_error_code"),
                summary={
                    **summary.get("summary", {}), "repairs": outcome.repairs, "isolation": result.isolation_note,
                    "detail": summary.get("error_detail"),
                },
                repair_try=len(outcome.repairs), started_at=started, finished_at=datetime.now(UTC), lines=kept,
            )
        )  # fmt: skip
        c.last_run_id = run_id
        if result.exit_code == 0:
            s.execute(delete(AppUser).where(AppUser.connector_id == connector_id))
            for record in result.records:
                s.add(_app_user(tenant, connector_id, record))
            c.status, c.error_code, c.error_message = "testing", None, None
            c.usage_available = any(r.get("usage_available") for r in result.records)
        else:
            code = summary.get("error_code") or "SERVER_ERROR"
            c.error_code, c.error_message = code, summary.get("error_detail") or code
            c.status = "needs_help" if result.exit_code in (4, 6, 8) else "testing"
            if result.exit_code == 8:
                s.add(
                    AuditEvent(
                        tenant_id=tenant, actor="sandbox", action="security.host_blocked",
                        target=c.app, detail={"run_id": run_id},
                    )
                )  # fmt: skip
        s.commit()
    emit({"stage": "done", "status": "ok" if result.exit_code == 0 else "fail", "run_id": run_id})


def _prebuild_samples(st: State) -> None:
    """Acme's sample apps: each hand-written spec is turned into code and tested on its recorded answers by the
    same steps as any connector, so the users on the app page were pulled by the generated code."""
    for app_name in SAMPLE_APPS:
        spec = json.loads((EXAMPLES / f"{slug_for(app_name)}.json").read_text())
        with st.db.session() as s:
            c = Connector(
                tenant_id="acme", app=app_name, status="testing", tier=spec["app"]["tier"], run_mode="replay",
                docs_url=spec["app"]["docs_url"], variables={}, ai_source=SAMPLE_SOURCE,
            )  # fmt: skip
            s.add(c)
            s.flush()
            s.add(ConnectorVersion(connector_id=c.id, version=1, spec_json=spec, created_by="hand_written"))
            s.commit()
            connector_id = c.id
        try:
            _run_test(st, connector_id, {"run_id": str(uuid.uuid4()), "run_mode": "replay", "tenant": "acme"})
        except Exception:  # noqa: BLE001 - one app failing must not stop the others
            traceback.print_exc()
            continue
        with st.db.session() as s:
            tested = s.get(Connector, connector_id)
            run = s.get(Run, tested.last_run_id) if tested and tested.last_run_id else None
            if tested is not None and run is not None and run.exit_code == 0:  # same rule as going live by hand
                tested.status = "live" if tested.usage_available and run.status != "partial" else "live_users_only"
                s.commit()


def _app_user(tenant: str, connector_id: int, record: dict[str, Any]) -> AppUser:
    fields = {k: v for k, v in record.items() if k != "source"}
    for key in ("last_active_at",):
        if fields.get(key):
            fields[key] = h.parse_time(fields[key])
    return AppUser(tenant_id=tenant, connector_id=connector_id, source=record.get("source", {}), **fields)


@app.get("/api/runs/{run_id}")
def run_detail(run_id: str, tenant: Tenant_, st: State_) -> dict[str, Any]:
    with st.db.session() as s:
        run = s.get(Run, run_id)
        if run is None:
            raise HTTPException(404, "No such run")
        c = _connector(s, tenant, run.connector_id)
        version = _latest(s, c.id)
        return _run_view(run, version.spec_json if version else None, full=True)


def _utc_iso(moment: datetime) -> str:
    """SQLite gives the time back without its zone; without "+00:00" a browser reads UTC as local time."""
    return (moment if moment.tzinfo else moment.replace(tzinfo=UTC)).isoformat()


def _run_view(run: Run, spec: dict[str, Any] | None, full: bool = False) -> dict[str, Any]:
    lines = run.lines or []
    checklist: dict[str, str] = {}
    for line in lines:
        if line.get("type") == "progress":
            checklist[str(line["step"])] = str(line["status"])
    view: dict[str, Any] = {
        "id": run.id,
        "status": run.status,
        "exit_code": run.exit_code,
        "error_code": run.error_code,
        "usage_error_code": run.usage_error_code,
        "message": _message(run.error_code, spec, (run.summary or {}).get("detail") or ""),
        "usage_message": _message(run.usage_error_code, spec),
        "summary": run.summary,
        "checklist": checklist,
        "sandbox": run.sandbox,
        "run_mode": run.run_mode,
        "finished_at": _utc_iso(run.finished_at) if run.finished_at else None,
    }
    if full:
        view["logs"] = [line for line in lines if line.get("type") == "log"]
    return view


# --- cross-check and savings ---------------------------------------------------------------


@app.post("/api/crosscheck/upload")
async def upload(
    tenant: Tenant_,
    st: State_,
    hris: Annotated[UploadFile | None, File(alias="hris.csv")] = None,
    sso: Annotated[UploadFile | None, File(alias="sso.csv")] = None,
    contract: Annotated[UploadFile | None, File(alias="contract.json")] = None,
) -> dict[str, Any]:
    saved = []
    with st.db.session() as s:
        for kind, upload_file in (("hris", hris), ("sso", sso), ("contract", contract)):
            if upload_file is None:
                continue
            content = (await upload_file.read()).decode("utf-8")
            s.execute(delete(CrosscheckFile).where(CrosscheckFile.tenant_id == tenant, CrosscheckFile.kind == kind))
            s.add(CrosscheckFile(tenant_id=tenant, kind=kind, filename=upload_file.filename or kind, content=content))
            saved.append(kind)
        s.commit()
    return {"saved": saved}


@app.get("/api/connectors/{connector_id}/savings")
def savings_preview(connector_id: int, tenant: Tenant_, st: State_) -> dict[str, Any]:
    with st.db.session() as s:
        c = _connector(s, tenant, connector_id)
        version = _latest(s, connector_id)
        if version is None:
            raise HTTPException(409, "No connector yet")
        files = {
            f.kind: f.content for f in s.scalars(select(CrosscheckFile).where(CrosscheckFile.tenant_id == c.tenant_id))
        }
        users = [_user_dict(u) for u in s.scalars(select(AppUser).where(AppUser.connector_id == connector_id))]
        # The inventory's seats, spend and renewal (what the admin typed in Add an app, or the spend data) come
        # first, so the app page and the savings agree; the contract file only fills in an app it lacks.
        contract = files.get("contract")
        item = s.scalar(select(InventoryApp).where(InventoryApp.tenant_id == c.tenant_id, InventoryApp.app == c.app))
        from_inventory = item is not None and bool(item.seats)
        if item is not None and from_inventory:
            contract = json.dumps(
                [{"app": c.app, "seats": item.seats, "annual_cost": item.annual_cost,
                  "renewal_date": item.renewal_date.isoformat() if item.renewal_date else None}]
            )  # fmt: skip
        parsed = savings.parse_files(c.app, files.get("hris"), files.get("sso"), contract)
        # Activity is judged on the sample data's own date; days to renewal count from the real date.
        today = datetime(2026, 10, 29, 9, tzinfo=UTC) if c.run_mode == "replay" else datetime.now(UTC)
        result = savings.compute(c.app, users, version.spec_json, parsed, c.token_owner_email, today)
        out = result.to_dict()
        if out["renewal_date"]:
            out["days_to_renewal"] = (date.fromisoformat(out["renewal_date"]) - datetime.now(UTC).date()).days
        out["contract_source"] = "your inventory" if from_inventory else "contract.json"
        out["run_mode"] = c.run_mode
        out["token_owner_warning"] = _token_owner_warning(s, c)
        return out


def _user_dict(u: AppUser) -> dict[str, Any]:
    return {
        "external_id": u.external_id, "email": u.email, "name": u.name, "role": u.role, "status": u.status,
        "is_admin": u.is_admin, "is_billable": u.is_billable, "license_type": u.license_type,
        "last_active_at": u.last_active_at.replace(tzinfo=UTC).isoformat() if u.last_active_at else None,
        "usage_metric_value": u.usage_metric_value, "usage_metric_label": u.usage_metric_label,
        "usage_window_days": u.usage_window_days, "usage_available": u.usage_available,
        "usage_is_proxy": u.usage_is_proxy, "excluded_reason": u.excluded_reason,
    }  # fmt: skip


@app.get("/api/connectors/{connector_id}/users")
def connector_users(connector_id: int, tenant: Tenant_, st: State_) -> dict[str, Any]:
    """The users and usage the generated connector retrieved on its last good run (the app page's Users tab)."""
    with st.db.session() as s:
        c = _connector(s, tenant, connector_id)
        users = s.scalars(
            select(AppUser).where(AppUser.connector_id == connector_id).order_by(AppUser.name, AppUser.email)
        )
        as_of = datetime(2026, 10, 29, 9, tzinfo=UTC) if c.run_mode == "replay" else datetime.now(UTC)
        return {"as_of": as_of.isoformat(), "sample": c.run_mode == "replay", "users": [_user_dict(u) for u in users]}


class Confirm(BaseModel):
    accept: bool
    users_only: bool = False
    note: str | None = None


@app.post("/api/connectors/{connector_id}/confirm")
def confirm(connector_id: int, body: Confirm, tenant: Tenant_, st: State_) -> dict[str, Any]:
    preview = savings_preview(connector_id, tenant, st)
    with st.db.session() as s:
        c = _connector(s, tenant, connector_id)
        run = s.get(Run, c.last_run_id) if c.last_run_id else None
        if not body.accept or run is None or run.exit_code != 0:
            raise HTTPException(409, "A passing test is needed before going live")
        if preview["needs_note"] and not (body.note or "").strip():
            raise HTTPException(422, "The user count differs from SSO by more than 2%. Add a note to confirm.")
        users_only = body.users_only or run.status == "partial" or not c.usage_available
        c.status = "live_users_only" if users_only else "live"
        c.confirm_note = (body.note or "").strip() or None
        s.commit()
        return {"status": c.status}


# --- library ---------------------------------------------------------------------------------


@app.post("/api/connectors/{connector_id}/submit-to-library")
def submit(connector_id: int, tenant: Tenant_, st: State_) -> dict[str, Any]:
    with st.db.session() as s:
        c = _connector(s, tenant, connector_id)
        version = _latest(s, connector_id)
        if version is None or not c.status.startswith("live"):
            raise HTTPException(409, "Only a live, healthy connector can be submitted")
        spec = copy.deepcopy(version.spec_json)
        flags = _review_flags(spec)
        latest = s.scalar(
            select(LibrarySpec).where(LibrarySpec.app == c.app).order_by(LibrarySpec.version.desc()).limit(1)
        )
        entry = LibrarySpec(
            app=c.app, spec_json=spec, version=(latest.version + 1) if latest else 1, status="pending_review",
            submitted_from_tenant=c.tenant_id, flags=flags,
        )  # fmt: skip
        s.add(entry)
        s.commit()
        return {"library_spec_id": entry.id, "status": entry.status, "flags": flags}


def _review_flags(spec: dict[str, Any]) -> list[str]:
    """The spec holds no customer values (secrets, subdomains, users stay with the tenant); these need a human look."""
    flags = []
    for target, value in spec["streams"]["users"]["field_map"].items():
        path = value if isinstance(value, str) else value.get("path", "")
        if "custom" in str(path).lower():
            flags.append(f"Custom field path in {target}: {path}")
    if spec.get("origin") == "ai":
        flags.append("AI-drafted: check the evidence quotes")
    for warning in spec.get("warnings", []):
        if warning.startswith("Not proved by the docs"):
            flags.append(warning)
    return flags


@app.get("/api/library/review-queue")
def review_queue(tenant: Tenant_, st: State_) -> list[dict[str, Any]]:
    _internal(tenant)
    with st.db.session() as s:
        return [
            {
                "id": e.id, "app": e.app, "version": e.version, "status": e.status, "flags": e.flags or [],
                "submitted_from": "a customer tenant", "tier": e.spec_json["app"]["tier"],
                "host": e.spec_json["app"]["api_host_pattern"],
                "summary": _summary(e.spec_json),
                "code": render(e.spec_json, e.version),
            }
            for e in s.scalars(select(LibrarySpec).order_by(LibrarySpec.id.desc()))
        ]  # fmt: skip


class Review(BaseModel):
    note: str | None = None


@app.post("/api/library/{spec_id}/{decision}")
def review(spec_id: int, decision: str, body: Review, tenant: Tenant_, st: State_) -> dict[str, Any]:
    _internal(tenant)
    if decision not in ("approve", "reject"):
        raise HTTPException(404, "Unknown action")
    with st.db.session() as s:
        entry = s.get(LibrarySpec, spec_id)
        if entry is None or entry.status != "pending_review":
            raise HTTPException(409, "Not waiting for review")
        entry.status = "approved" if decision == "approve" else "rejected"
        entry.reviewed_by, entry.reviewed_at, entry.review_note = "platform engineer", datetime.now(UTC), body.note
        s.commit()
        return {"status": entry.status}


# --- code, data card, actions ------------------------------------------------------------------


@app.get("/api/connectors/{connector_id}/code", response_class=PlainTextResponse)
def code(connector_id: int, tenant: Tenant_, st: State_) -> str:
    with st.db.session() as s:
        _connector(s, tenant, connector_id)
        version = _latest(s, connector_id)
        if version is None:
            raise HTTPException(409, "No connector yet")
        return version.code or render(version.spec_json, version.version)


@app.get("/api/connectors/{connector_id}/data-card", response_class=PlainTextResponse)
def data_card(connector_id: int, tenant: Tenant_, st: State_) -> str:
    with st.db.session() as s:
        c = _connector(s, tenant, connector_id)
        version = _latest(s, connector_id)
        if version is None:
            raise HTTPException(409, "No connector yet")
        spec = version.spec_json
        summary = _summary(spec)
        paths = [spec["streams"]["users"]["path"]] + (
            [spec["streams"]["usage"]["path"]] if spec["streams"]["usage"] else []
        )
        evidence = sorted({e.get("url", "") for e in spec.get("evidence", {}).values() if e.get("url")})
        lines = [
            f"# Data card: {c.app} connector v{version.version}",
            "",
            f"- **Host:** {summary['host']} (https only; the sandbox blocks every other host)",
            f"- **Calls:** GET only: {', '.join(p for p in [b['path'] for b in spec['bootstrap']] + paths)}",
            f"- **Login:** {summary['login']['type']}; scopes: {', '.join(summary['login']['scopes']) or 'none'}; role: {summary['login']['role_required'] or '—'}",
            "- **Fields stored:** id, email, name, role, status, admin flag, licence, last active, usage value",
            "- **Not stored:** raw API responses, tokens in clear text (AES-GCM vault, per-customer key)",
            "- **Retention:** user records are deleted with the connector (Delete app)",
            "- **Egress:** one host per run; the sandbox refuses any other host",
            f"- **Plan / role needs:** {'; '.join(spec.get('warnings', [])) or '—'}",
            "",
            "**Evidence links:**",
            *(f"- {url}" for url in evidence),
        ]  # fmt: skip
        return "\n".join(lines) + "\n"


@app.post("/api/connectors/{connector_id}/pause")
def pause(connector_id: int, tenant: Tenant_, st: State_) -> dict[str, Any]:
    with st.db.session() as s:
        c = _connector(s, tenant, connector_id)
        c.status = "paused"
        s.commit()
        return {"status": c.status}


@app.delete("/api/connectors/{connector_id}")
def remove(connector_id: int, tenant: Tenant_, st: State_) -> dict[str, Any]:
    with st.db.session() as s:
        _connector(s, tenant, connector_id)
        _drop_connector(s, st, connector_id)
        s.commit()
    return {"deleted": True}


@app.delete("/api/inventory/{app_name}")
def delete_app(app_name: str, tenant: Tenant_, st: State_) -> dict[str, Any]:
    """Delete app: an app the admin added goes with everything built for it, so it can be added again. A starting
    app keeps its row and loses its connector ("Remove connector"); the sample apps can't be removed."""
    with st.db.session() as s:
        row = s.scalar(select(InventoryApp).where(InventoryApp.tenant_id == tenant, InventoryApp.app == app_name))
        connectors = _connectors_of(s, tenant, app_name)
        if row is None and not connectors:
            raise HTTPException(404, f"There's no app called {app_name} in your inventory.")
        what = _removable(connectors, tenant, app_name)
        if what is None:
            raise HTTPException(
                409,
                f"{app_name} is a sample app, so it stays for everyone who opens this link."
                if connectors
                else f"{app_name} has no connector to remove.",
            )
        if any(_busy(c) for c in connectors):
            raise HTTPException(409, f"{app_name} is still building or testing. Wait for it to finish, then try again.")
        for c in connectors:
            _drop_connector(s, st, c.id)
        if what == "app" and row is not None:
            s.delete(row)
        s.commit()
    return {"deleted": what}


def _connectors_of(s: Session, tenant: str, app_name: str) -> list[Connector]:
    query = select(Connector).where(Connector.tenant_id == tenant, Connector.app == app_name)
    return list(s.scalars(query.order_by(Connector.id.desc())))


def _removable(connectors: list[Connector], tenant: str, app_name: str) -> str | None:
    """What Delete removes: "app" for an app the admin added, "connector" for a starting app someone built a
    connector for, None for the sample apps (one visitor must not break the demo for the next)."""
    if any(c.ai_source == SAMPLE_SOURCE for c in connectors):
        return None
    if app_name.lower() not in {name.lower() for name, *_ in INVENTORY.get(tenant, [])}:
        return "app"
    return "connector" if connectors else None


def _busy(c: Connector) -> bool:
    """A build or test is running now. One past its time limit (its server instance died) doesn't count."""
    started = c.job_started_at
    if started is not None and started.tzinfo is None:
        started = started.replace(tzinfo=UTC)
    return (
        c.job_state == "running"
        and started is not None
        and (datetime.now(UTC) - started).total_seconds() <= JOB_TIMEOUT_S + 30
    )


def _drop_connector(s: Session, st: State, connector_id: int) -> None:
    """A connector and everything built for it: versions, runs, users, its token, progress and AI call records."""
    s.execute(delete(RunRequest).where(RunRequest.run_id.in_(select(Run.id).where(Run.connector_id == connector_id))))
    for table in (AppUser, Credential, TokenRequest, ConnectorVersion, Run, JobEvent, LlmCall):
        s.execute(delete(table).where(table.connector_id == connector_id))
    s.execute(delete(Connector).where(Connector.id == connector_id))
    st.bundles.pop(connector_id, None)


# --- static frontend (built) -------------------------------------------------------------------

FRONTEND = PROTOTYPE / "frontend" / "dist"


@app.get("/{path:path}", include_in_schema=False)
def frontend(path: str) -> FileResponse:
    """Serves the built UI; unknown paths get index.html so deep links work on refresh."""
    if path.startswith("api/") or not FRONTEND.exists():
        raise HTTPException(404, "Not found")
    file = (FRONTEND / path).resolve()
    if path and file.is_file() and FRONTEND.resolve() in file.parents:
        return FileResponse(file)
    return FileResponse(FRONTEND / "index.html")
