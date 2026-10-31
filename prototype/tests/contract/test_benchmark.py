"""The benchmark harness itself works: the golden specs, fed back as the "model", score perfectly."""

from __future__ import annotations

from benchmark.__main__ import score, summarise


def test_oracle_scores_the_golden_spec_perfectly() -> None:
    row = score("calendly", "oracle", 1)
    assert (row.schema_valid, row.test_pass, row.user_count_match, row.usage_match) == (True, True, True, True)
    assert row.repairs == 0 and row.error == ""
    assert "We use" not in summarise([row])  # the oracle is a harness check, never a recommendation
