"""SQLite tables (TRD §10). SQLAlchemy 2.0; Postgres later with the same models."""

from __future__ import annotations

from datetime import UTC, date, datetime

from sqlalchemy import (
    JSON,
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    LargeBinary,
    String,
    Text,
    UniqueConstraint,
    create_engine,
)
from sqlalchemy.engine import Engine
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

# Lifecycle statuses (PRD §8). The UI and the code use these exact values.
CONNECTOR_STATUSES = (
    "draft",
    "testing",
    "needs_help",
    "live",
    "live_users_only",
    "needs_repair",
    "reconnect_needed",
    "paused",
)
LIBRARY_STATUSES = ("pending_review", "approved", "rejected")
RUN_MODES = ("live", "replay")
TIERS = ("T1", "T2", "T3")
USER_STATUSES = ("active", "suspended", "deactivated", "invited", "unknown")


def _now() -> datetime:
    return datetime.now(UTC)


def _one_of(column: str, values: tuple[str, ...], nullable: bool = False) -> CheckConstraint:
    allowed = ", ".join(f"'{v}'" for v in values)
    check = f"{column} IN ({allowed})"
    if nullable:
        check = f"{column} IS NULL OR {check}"
    return CheckConstraint(check, name=f"ck_{column}")


class Base(DeclarativeBase):
    pass


class Tenant(Base):
    __tablename__ = "tenants"
    __table_args__ = (_one_of("run_mode_default", RUN_MODES),)

    id: Mapped[str] = mapped_column(String(32), primary_key=True)  # acme, globex, internal
    name: Mapped[str] = mapped_column(String(100))
    is_internal: Mapped[bool] = mapped_column(Boolean, default=False)
    run_mode_default: Mapped[str] = mapped_column(String(10), default="live")


class InventoryApp(Base):
    __tablename__ = "inventory_apps"
    __table_args__ = (UniqueConstraint("tenant_id", "app"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    tenant_id: Mapped[str] = mapped_column(ForeignKey("tenants.id"))
    app: Mapped[str] = mapped_column(String(100))
    owner: Mapped[str | None] = mapped_column(String(100))
    annual_cost: Mapped[float | None] = mapped_column(Float)
    seats: Mapped[int | None] = mapped_column(Integer)
    renewal_date: Mapped[date | None] = mapped_column(Date)


class Connector(Base):
    __tablename__ = "connectors"
    __table_args__ = (
        _one_of("status", CONNECTOR_STATUSES),
        _one_of("tier", TIERS, nullable=True),
        _one_of("run_mode", RUN_MODES),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    tenant_id: Mapped[str] = mapped_column(ForeignKey("tenants.id"))
    app: Mapped[str] = mapped_column(String(100))
    status: Mapped[str] = mapped_column(String(20), default="draft")
    tier: Mapped[str | None] = mapped_column(String(2))
    current_version: Mapped[int | None] = mapped_column(Integer)
    from_library_id: Mapped[int | None] = mapped_column(ForeignKey("library_specs.id"))
    run_mode: Mapped[str] = mapped_column(String(10), default="live")
    token_owner_email: Mapped[str | None] = mapped_column(String(320))
    usage_available: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)


class ConnectorVersion(Base):
    __tablename__ = "connector_versions"
    __table_args__ = (UniqueConstraint("connector_id", "version"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    connector_id: Mapped[int] = mapped_column(ForeignKey("connectors.id"))
    version: Mapped[int] = mapped_column(Integer)
    spec_json: Mapped[dict[str, object]] = mapped_column(JSON)
    code: Mapped[str | None] = mapped_column(Text)
    code_sha256: Mapped[str | None] = mapped_column(String(64))
    created_by: Mapped[str] = mapped_column(String(100))  # "ai", "hand_written", or a person
    approved_by: Mapped[str | None] = mapped_column(String(100))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)


class LibrarySpec(Base):
    __tablename__ = "library_specs"
    __table_args__ = (
        _one_of("status", LIBRARY_STATUSES),
        _one_of("canary_status", ("none", "running", "passed", "rolled_back"), nullable=True),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    app: Mapped[str] = mapped_column(String(100))
    spec_json: Mapped[dict[str, object]] = mapped_column(JSON)  # customer-specific values stripped
    version: Mapped[int] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(String(20), default="pending_review")
    submitted_from_tenant: Mapped[str] = mapped_column(ForeignKey("tenants.id"))
    reviewed_by: Mapped[str | None] = mapped_column(String(100))
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    review_note: Mapped[str | None] = mapped_column(Text)
    used_by_count: Mapped[int] = mapped_column(Integer, default=0)
    failure_rate: Mapped[float | None] = mapped_column(Float)
    canary_status: Mapped[str | None] = mapped_column(String(20))


class Credential(Base):
    """Encrypted secrets only (AES-GCM, per-tenant key). Never plaintext, never returned by the API."""

    __tablename__ = "credentials"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    connector_id: Mapped[int] = mapped_column(ForeignKey("connectors.id"), unique=True)
    ciphertext: Mapped[bytes] = mapped_column(LargeBinary)
    nonce: Mapped[bytes] = mapped_column(LargeBinary)
    key_id: Mapped[str] = mapped_column(String(64))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)


class TokenRequest(Base):
    __tablename__ = "token_requests"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    connector_id: Mapped[int] = mapped_column(ForeignKey("connectors.id"))
    one_time_code_hash: Mapped[str] = mapped_column(String(64), unique=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class Run(Base):
    __tablename__ = "runs"
    __table_args__ = (
        _one_of("mode", ("test", "full")),
        _one_of("run_mode", RUN_MODES),
        _one_of("status", ("running", "ok", "partial", "error"), nullable=False),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    connector_id: Mapped[int] = mapped_column(ForeignKey("connectors.id"))
    version: Mapped[int] = mapped_column(Integer)
    mode: Mapped[str] = mapped_column(String(10))
    run_mode: Mapped[str] = mapped_column(String(10))
    sandbox: Mapped[str] = mapped_column(String(20))  # docker | subprocess
    status: Mapped[str] = mapped_column(String(10), default="running")
    exit_code: Mapped[int | None] = mapped_column(Integer)
    error_code: Mapped[str | None] = mapped_column(String(40))
    usage_error_code: Mapped[str | None] = mapped_column(String(40))
    summary: Mapped[dict[str, object] | None] = mapped_column(JSON)
    repair_try: Mapped[int] = mapped_column(Integer, default=0)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class RunRequest(Base):
    """One redacted request log line (TRD §7). Never bodies, never tokens."""

    __tablename__ = "run_requests"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    run_id: Mapped[str] = mapped_column(ForeignKey("runs.id"))
    step: Mapped[str] = mapped_column(String(20))
    method: Mapped[str] = mapped_column(String(10))
    path: Mapped[str] = mapped_column(String(500))
    status: Mapped[int | None] = mapped_column(Integer)
    ms: Mapped[int | None] = mapped_column(Integer)
    records: Mapped[int | None] = mapped_column(Integer)
    retry: Mapped[int] = mapped_column(Integer, default=0)


class AppUser(Base):
    """Canonical fields (TRD §5) + tenant + connector."""

    __tablename__ = "app_users"
    __table_args__ = (
        UniqueConstraint("connector_id", "external_id"),
        _one_of("status", USER_STATUSES),
        _one_of("usage_source", ("app", "sso_fallback"), nullable=True),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    tenant_id: Mapped[str] = mapped_column(ForeignKey("tenants.id"))
    connector_id: Mapped[int] = mapped_column(ForeignKey("connectors.id"))
    external_id: Mapped[str] = mapped_column(String(300))
    email: Mapped[str | None] = mapped_column(String(320), index=True)
    name: Mapped[str | None] = mapped_column(String(300))
    role: Mapped[str | None] = mapped_column(String(100))
    status: Mapped[str] = mapped_column(String(20))
    is_admin: Mapped[bool | None] = mapped_column(Boolean)
    license_type: Mapped[str | None] = mapped_column(String(100))
    is_billable: Mapped[bool | None] = mapped_column(Boolean)
    last_active_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    usage_metric_label: Mapped[str | None] = mapped_column(String(200))
    usage_metric_value: Mapped[float | None] = mapped_column(Float)
    usage_window_days: Mapped[int | None] = mapped_column(Integer)
    usage_available: Mapped[bool] = mapped_column(Boolean, default=False)
    usage_is_proxy: Mapped[bool] = mapped_column(Boolean, default=False)
    usage_source: Mapped[str | None] = mapped_column(String(20))
    excluded_reason: Mapped[str | None] = mapped_column(String(50))
    source: Mapped[dict[str, object]] = mapped_column(JSON)


class CrosscheckFile(Base):
    __tablename__ = "crosscheck_files"
    __table_args__ = (_one_of("kind", ("hris", "sso", "contract")),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    tenant_id: Mapped[str] = mapped_column(ForeignKey("tenants.id"))
    kind: Mapped[str] = mapped_column(String(10))
    filename: Mapped[str] = mapped_column(String(200))
    content: Mapped[str] = mapped_column(Text)
    uploaded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)


class LlmCall(Base):
    """Cost and timing only. No prompt text (TRD §8.2)."""

    __tablename__ = "llm_calls"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    connector_id: Mapped[int | None] = mapped_column(ForeignKey("connectors.id"))
    purpose: Mapped[str] = mapped_column(String(20))  # draft | evidence_reask | repair | benchmark
    model: Mapped[str] = mapped_column(String(60))
    input_tokens: Mapped[int] = mapped_column(Integer)
    output_tokens: Mapped[int] = mapped_column(Integer)
    ms: Mapped[int] = mapped_column(Integer)
    cost_usd: Mapped[float] = mapped_column(Float)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)


class BenchmarkRun(Base):
    """One row per draft in the model benchmark (EVAL §2)."""

    __tablename__ = "benchmark_runs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    batch_id: Mapped[str] = mapped_column(String(36), index=True)
    app: Mapped[str] = mapped_column(String(100))
    model: Mapped[str] = mapped_column(String(60))
    run_no: Mapped[int] = mapped_column(Integer)
    schema_valid: Mapped[bool] = mapped_column(Boolean)
    evidence_verified_pct: Mapped[float | None] = mapped_column(Float)
    test_pass: Mapped[bool] = mapped_column(Boolean)
    user_count_match: Mapped[bool | None] = mapped_column(Boolean)
    usage_match: Mapped[bool | None] = mapped_column(Boolean)
    repairs: Mapped[int] = mapped_column(Integer, default=0)
    cost_usd: Mapped[float] = mapped_column(Float, default=0.0)
    seconds: Mapped[float] = mapped_column(Float, default=0.0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)


class AuditEvent(Base):
    """SHOULD (TRD §1). Security events (exit code 8) always land here."""

    __tablename__ = "audit_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    tenant_id: Mapped[str] = mapped_column(ForeignKey("tenants.id"))
    actor: Mapped[str] = mapped_column(String(100))
    action: Mapped[str] = mapped_column(String(60))
    target: Mapped[str | None] = mapped_column(String(200))
    detail: Mapped[dict[str, object] | None] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)


def make_engine(url: str = "sqlite:///./data/app.db") -> Engine:
    return create_engine(url)


def init_db(engine: Engine) -> None:
    Base.metadata.create_all(engine)
