"""Milestone 1 done-criteria (CLAUDE.md) plus the P5 rule edges (TRD §3)."""

from __future__ import annotations

import copy
import json
from pathlib import Path
from typing import Any

import pytest

from app.services.spec_validator import RULES_REJECTED, SCHEMA_INVALID, load_schema, validate_spec

SPECS = Path(__file__).resolve().parents[2] / "specs" / "examples"


def load(name: str) -> dict[str, Any]:
    spec: dict[str, Any] = json.loads((SPECS / f"{name}.json").read_text())
    return spec


def messages(spec: dict[str, Any]) -> str:
    return "\n".join(f"{i.code} {i.pointer}: {i.message}" for i in validate_spec(spec).issues)


# --- the three TRD §4 specs -------------------------------------------------


@pytest.mark.parametrize("name", ["zendesk", "calendly", "notion"])
def test_example_specs_validate(name: str) -> None:
    result = validate_spec(load(name))
    assert result.ok, messages(load(name))


def test_both_schemas_are_valid_json_schema() -> None:
    load_schema("connector_spec.schema.json")
    load_schema("draft_spec.schema.json")


# --- read-only --------------------------------------------------------------


def test_delete_is_rejected() -> None:
    spec = load("calendly")
    spec["streams"]["users"]["method"] = "DELETE"
    result = validate_spec(spec)
    assert result.error_code == RULES_REJECTED
    assert any(i.pointer == "/streams/users/method" for i in result.issues)


@pytest.mark.parametrize("method", ["POST", "PUT", "PATCH", "get"])
def test_other_non_get_methods_are_rejected(method: str) -> None:
    spec = load("calendly")
    spec["bootstrap"][0]["method"] = method
    assert validate_spec(spec).error_code == RULES_REJECTED


# --- host -------------------------------------------------------------------


def test_another_host_is_rejected() -> None:
    spec = load("calendly")
    spec["base_url"] = "https://evil.example.com"
    result = validate_spec(spec)
    assert result.error_code == RULES_REJECTED
    assert any(i.pointer == "/base_url" for i in result.issues)


def test_token_url_on_another_host_is_rejected() -> None:
    spec = load("zendesk")
    spec["auth"]["token_url"] = "https://login.evil.example.com/oauth/tokens"
    assert validate_spec(spec).error_code == RULES_REJECTED


@pytest.mark.parametrize(
    "url",
    [
        "http://api.calendly.com",  # not https
        "https://api.calendly.com@evil.com",  # userinfo trick
        "https://api.calendly.com:8443",  # port
        "https://api.calendly.com.evil.com",  # suffix trick
        "https://api.calendly.com?x=1",  # query string
    ],
)
def test_base_url_tricks_are_rejected(url: str) -> None:
    spec = load("calendly")
    spec["base_url"] = url
    assert validate_spec(spec).error_code == RULES_REJECTED, url


@pytest.mark.parametrize(
    "host",
    [
        "93.184.216.34",  # IP literal
        "{subdomain}",  # the variable would pick the whole host
        "api.{domain}.com",  # placeholder not in the left-most label
        "x{subdomain}.zendesk.com",  # placeholder only part of the label
        "localhost",  # no fixed domain
    ],
)
def test_bad_host_patterns_are_rejected(host: str) -> None:
    spec = load("zendesk")
    spec["app"]["api_host_pattern"] = host
    spec["variables"].append(
        {"name": "domain", "label": "d", "example": "acme", "required": True, "pattern": "^[a-z]+$"}
    )
    assert validate_spec(spec).error_code == RULES_REJECTED, host


@pytest.mark.parametrize("pattern", ["^.+$", "^[a-z.]+$", "^[a-z]*$", "[a-z]+"])
def test_loose_host_variable_patterns_are_rejected(pattern: str) -> None:
    spec = load("zendesk")
    spec["variables"][0]["pattern"] = pattern
    assert validate_spec(spec).error_code == RULES_REJECTED, pattern


def test_variable_example_must_match_pattern() -> None:
    spec = load("zendesk")
    spec["variables"][0]["example"] = "Not Valid!"
    assert validate_spec(spec).error_code == RULES_REJECTED


@pytest.mark.parametrize("path", ["https://evil.com/users", "//evil.com/users", "/users/../../admin", "users"])
def test_bad_paths_are_rejected(path: str) -> None:
    spec = load("notion")
    spec["streams"]["users"]["path"] = path
    assert validate_spec(spec).error_code == RULES_REJECTED, path


# --- placeholders and secrets ---------------------------------------------------


def test_secret_in_query_is_rejected() -> None:
    spec = load("calendly")
    spec["streams"]["users"]["query"]["token"] = "{secrets.token}"
    assert validate_spec(spec).error_code == RULES_REJECTED


def test_secret_in_path_is_rejected() -> None:
    spec = load("notion")
    spec["streams"]["users"]["path"] = "/users/{secrets.token}"
    assert validate_spec(spec).error_code == RULES_REJECTED


def test_secret_in_default_header_is_rejected() -> None:
    spec = load("notion")
    spec["default_headers"]["X-Token"] = "{secrets.token}"
    assert validate_spec(spec).error_code == RULES_REJECTED


def test_secret_in_token_url_is_rejected() -> None:
    spec = load("zendesk")
    spec["auth"]["token_url"] = "https://{subdomain}.zendesk.com/oauth/tokens/{secrets.client_secret}"
    assert validate_spec(spec).error_code == RULES_REJECTED


def test_secret_must_name_an_auth_field() -> None:
    spec = load("notion")
    spec["auth"]["bearer_template"] = "{secrets.password}"
    assert validate_spec(spec).error_code == RULES_REJECTED


@pytest.mark.parametrize("value", ["{unknown}", "{now_plus_days:5}", "{ org_uri }", "{}"])
def test_unknown_or_invalid_placeholders_are_rejected(value: str) -> None:
    spec = load("calendly")
    spec["streams"]["usage"]["query"]["status"] = value
    assert validate_spec(spec).error_code == RULES_REJECTED, value


def test_bootstrap_extract_is_not_usable_before_it_exists() -> None:
    spec = load("calendly")
    spec["bootstrap"][0]["query"] = {"organization": "{org_uri}"}
    assert validate_spec(spec).error_code == RULES_REJECTED


def test_time_placeholders_are_allowed() -> None:
    spec = load("calendly")
    assert spec["streams"]["usage"]["query"]["max_start_time"] == "{now}"
    assert validate_spec(spec).ok


# --- schema layer ---------------------------------------------------------------


def test_bad_jmespath_is_schema_invalid() -> None:
    spec = load("notion")
    spec["streams"]["users"]["records_path"] = "results[?type=="
    result = validate_spec(spec)
    assert result.error_code == SCHEMA_INVALID


def test_ai_spec_needs_evidence() -> None:
    spec = load("notion")
    spec["origin"] = "ai"
    assert validate_spec(spec).error_code == SCHEMA_INVALID
    url = "https://developers.notion.com/reference/get-users"
    spec["evidence"] = {"/streams/users/path": {"url": url, "quote": "List all users"}}
    assert validate_spec(spec).ok, messages(spec)


def test_long_evidence_quote_is_schema_invalid() -> None:
    spec = load("notion")
    spec["evidence"] = {"/streams/users/path": {"url": "https://x.example.com", "quote": " ".join(["word"] * 26)}}
    assert validate_spec(spec).error_code == SCHEMA_INVALID


def test_t2_needs_a_usage_stream() -> None:
    spec = load("calendly")
    spec["streams"]["usage"] = None
    assert validate_spec(spec).error_code == SCHEMA_INVALID


def test_users_field_map_needs_external_id() -> None:
    spec = load("notion")
    del spec["streams"]["users"]["field_map"]["external_id"]
    assert validate_spec(spec).error_code == SCHEMA_INVALID


def test_rules_still_run_when_schema_fails() -> None:
    spec = load("calendly")
    del spec["warnings"]  # schema error
    spec["streams"]["users"]["method"] = "DELETE"  # rule error
    assert validate_spec(spec).error_code == RULES_REJECTED


def test_garbage_does_not_crash() -> None:
    for junk in [None, [], "spec", 42, {"streams": "x", "auth": [], "bootstrap": {}}]:
        assert not validate_spec(junk).ok


def test_validation_does_not_change_the_spec() -> None:
    spec = load("zendesk")
    before = copy.deepcopy(spec)
    validate_spec(spec)
    assert spec == before
