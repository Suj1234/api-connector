"""Database session and demo seed data (TRD §10, §12)."""

from __future__ import annotations

import json
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import date
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from app.config import PROTOTYPE, get
from app.models.tables import CrosscheckFile, InventoryApp, Tenant, init_db, make_engine

ACME_FILES = PROTOTYPE / "fixtures" / "acme"

TENANTS = [
    ("acme", "Acme", False, "replay"),
    ("globex", "Globex", False, "live"),
    ("internal", "Platform team", True, "replay"),
]
INVENTORY = {
    "acme": [
        ("Calendly", "Marketing Ops", 14400, 60, "2026-12-26"),
        ("Zendesk", "Support", 38000, 40, "2027-02-15"),
        ("Notion", "IT", 12000, 100, "2027-03-31"),
        ("Slack", "IT", 52000, 140, "2027-05-01"),
        ("Zoom", "IT", 21000, 120, "2027-06-30"),
    ],
    "globex": [
        ("Calendly", "Sales Ops", 9600, 40, "2027-01-20"),
        ("Zendesk", "Customer Care", 24000, 25, "2027-04-10"),
        ("Notion", "Engineering", 8000, 60, "2027-02-28"),
    ],
}
NATIVE = {"Slack", "Zoom"}  # already connected by the platform's own connectors (shown, not built)


class Database:
    def __init__(self, url: str | None = None) -> None:
        url = url or get("DATABASE_URL", "sqlite:///./data/app.db")
        if url.startswith("sqlite:///./"):
            path = PROTOTYPE / url.removeprefix("sqlite:///./")
            path.parent.mkdir(parents=True, exist_ok=True)
            url = f"sqlite:///{path}"
        self.engine: Engine = make_engine(url)
        init_db(self.engine)
        self.factory = sessionmaker(self.engine, expire_on_commit=False)

    @contextmanager
    def session(self) -> Iterator[Session]:
        with self.factory() as session:
            yield session

    def seed(self) -> None:
        with self.session() as s:
            if s.scalar(select(Tenant).limit(1)) is not None:
                return
            for tenant_id, name, internal, mode in TENANTS:
                s.add(Tenant(id=tenant_id, name=name, is_internal=internal, run_mode_default=mode))
            for tenant_id, apps in INVENTORY.items():
                for app, owner, cost, seats, renewal in apps:
                    s.add(
                        InventoryApp(
                            tenant_id=tenant_id, app=app, owner=owner, annual_cost=cost, seats=seats,
                            renewal_date=date.fromisoformat(renewal),
                        )
                    )  # fmt: skip
            for kind, name in (("hris", "hris.csv"), ("sso", "sso.csv"), ("contract", "contract.json")):
                s.add(CrosscheckFile(tenant_id="acme", kind=kind, filename=name, content=_read(ACME_FILES / name)))
            s.commit()


def _read(path: Path) -> str:
    return path.read_text() if path.exists() else ""


def contract_for(content: str, app: str) -> dict[str, object] | None:
    try:
        items = json.loads(content)
    except ValueError:
        return None
    for item in items if isinstance(items, list) else [items]:
        if str(item.get("app", "")).lower() == app.lower():
            return dict(item)
    return None
