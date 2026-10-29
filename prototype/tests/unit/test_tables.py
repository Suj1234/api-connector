from __future__ import annotations

from collections.abc import Iterator

import pytest
from sqlalchemy import inspect
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.tables import Connector, Tenant, init_db, make_engine

TRD_TABLES = {
    "tenants",
    "inventory_apps",
    "connectors",
    "connector_versions",
    "library_specs",
    "credentials",
    "token_requests",
    "runs",
    "run_requests",
    "app_users",
    "crosscheck_files",
    "llm_calls",
    "benchmark_runs",
    "audit_events",
    "job_events",  # progress of AI drafts and tests, readable by any server instance
}


@pytest.fixture
def session() -> Iterator[Session]:
    engine = make_engine("sqlite://")
    init_db(engine)
    with Session(engine) as s:
        yield s


def test_all_trd_tables_exist(session: Session) -> None:
    assert set(inspect(session.get_bind()).get_table_names()) == TRD_TABLES


def test_credentials_have_no_plaintext_column(session: Session) -> None:
    columns = {c["name"] for c in inspect(session.get_bind()).get_columns("credentials")}
    assert columns == {"id", "connector_id", "ciphertext", "nonce", "key_id", "created_at"}


def test_llm_calls_store_no_prompt_text(session: Session) -> None:
    columns = {c["name"] for c in inspect(session.get_bind()).get_columns("llm_calls")}
    assert not columns & {"prompt", "prompt_text", "response", "output_text"}


def test_connector_status_is_constrained(session: Session) -> None:
    session.add(Tenant(id="acme", name="Acme"))
    session.add(Connector(tenant_id="acme", app="Calendly", status="live"))
    session.commit()
    session.add(Connector(tenant_id="acme", app="Notion", status="almost_live"))
    with pytest.raises(IntegrityError):
        session.commit()
