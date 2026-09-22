"""Tests for enforce/contracts.py and enforce/monitor.py — see CLAUDE.md 'Conventions':
the monitor gets property tests."""
from __future__ import annotations

from pathlib import Path

import pytest

from pb.enforce.contracts import Contract, load_contracts
from pb.enforce.monitor import evaluate
from pb.trace.schema import ROLE_VALUES, ArgumentFact, Role, Trust

POLICY_PATH = Path(__file__).resolve().parents[1] / "contracts" / "policy.yaml"


def _fact(role: Role, trust: Trust, param: str = "x") -> ArgumentFact:
    return ArgumentFact(call_id="c1", param_name=param, value_repr="v", trust=trust, role=role)


def test_policy_yaml_loads() -> None:
    contracts = load_contracts(POLICY_PATH)
    assert len(contracts) == 6
    assert {c.role for c in contracts} == set(ROLE_VALUES)


def test_load_contracts_rejects_unknown_role(tmp_path: Path) -> None:
    bad = tmp_path / "bad.yaml"
    bad.write_text("rules:\n  - role: nope\n    min_trust: TRUSTED\n    on_violation: block\n")
    with pytest.raises(ValueError):
        load_contracts(bad)


def test_load_contracts_rejects_missing_field(tmp_path: Path) -> None:
    bad = tmp_path / "bad.yaml"
    bad.write_text("rules:\n  - role: target\n    min_trust: TRUSTED\n")
    with pytest.raises(ValueError):
        load_contracts(bad)


def test_evaluate_allows_when_no_contract_governs_role() -> None:
    contracts = (Contract(role="target", min_trust="TRUSTED", on_violation="block"),)
    facts = (_fact("content", "EXTERNAL"),)
    assert evaluate("any_tool", facts, contracts) == "allow"


def test_evaluate_blocks_on_violation() -> None:
    contracts = (Contract(role="target", min_trust="TRUSTED", on_violation="block"),)
    facts = (_fact("target", "EXTERNAL"),)
    assert evaluate("any_tool", facts, contracts) == "block"


def test_evaluate_allows_when_trust_sufficient() -> None:
    contracts = (Contract(role="target", min_trust="USER", on_violation="block"),)
    facts = (_fact("target", "TRUSTED"),)
    assert evaluate("any_tool", facts, contracts) == "allow"


def test_evaluate_tool_scoped_contract_only_applies_to_named_tool() -> None:
    contracts = (Contract(role="target", min_trust="TRUSTED", on_violation="block", tool="send_money"),)
    facts = (_fact("target", "EXTERNAL"),)
    assert evaluate("other_tool", facts, contracts) == "allow"
    assert evaluate("send_money", facts, contracts) == "block"


def test_evaluate_takes_most_restrictive_verdict_across_arguments() -> None:
    contracts = (
        Contract(role="control", min_trust="USER", on_violation="escalate"),
        Contract(role="target", min_trust="USER", on_violation="block"),
    )
    facts = (
        _fact("control", "EXTERNAL", param="a"),
        _fact("target", "EXTERNAL", param="b"),
    )
    assert evaluate("any_tool", facts, contracts) == "block"


def test_draft_policy_matches_documented_shape() -> None:
    contracts = load_contracts(POLICY_PATH)
    by_role = {c.role: c for c in contracts}
    assert by_role["credential"].min_trust == "TRUSTED"
    assert by_role["credential"].on_violation == "block"
    assert by_role["content"].on_violation == "allow"
