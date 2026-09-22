"""Cross-checks the draft role table in enforce/roles.py against the live AgentDojo
tool signatures it claims to cover (agentdojo==0.1.35, v1 suites) — catches
transcription errors and upstream drift, not the annotation quality itself (that's the
week-2 human annotation-agreement pass, not something a test can validate)."""
from __future__ import annotations

import inspect
import typing

import pytest

from agentdojo.default_suites.v1.tools import (
    banking_client,
    calendar_client,
    cloud_drive_client,
    email_client,
    file_reader,
    slack,
    travel_booking_client,
    user_account,
    web,
)
from agentdojo.functions_runtime import Depends

from pb.enforce.roles import _ROLE_TABLE, RoleNotAssigned, assign_role

_MODULES = (
    banking_client,
    calendar_client,
    cloud_drive_client,
    email_client,
    file_reader,
    slack,
    travel_booking_client,
    user_account,
    web,
)


def _is_dependency_injected(param: inspect.Parameter) -> bool:
    return any(isinstance(arg, Depends) for arg in typing.get_args(param.annotation))


def _agent_supplied_params(fn: object) -> list[str]:
    return [
        name
        for name, param in inspect.signature(fn).parameters.items()  # type: ignore[arg-type]
        if not _is_dependency_injected(param)
    ]


def _live_tool_params() -> dict[str, list[str]]:
    tools: dict[str, list[str]] = {}
    for mod in _MODULES:
        for name, obj in inspect.getmembers(mod, inspect.isfunction):
            if obj.__module__ != mod.__name__ or name == "standardize_url":
                continue
            tools[name] = _agent_supplied_params(obj)
    return tools


def test_every_agent_supplied_param_has_a_draft_role() -> None:
    missing = [
        f"{tool}({param})"
        for tool, params in _live_tool_params().items()
        for param in params
        if (tool, param) not in _ROLE_TABLE
    ]
    assert not missing, f"missing draft role assignments: {missing}"


def test_no_stale_entries_for_params_that_no_longer_exist() -> None:
    live = _live_tool_params()
    stale = [
        f"{tool}({param})" for tool, param in _ROLE_TABLE if tool not in live or param not in live[tool]
    ]
    assert not stale, f"stale draft role assignments (tool/param no longer exists): {stale}"


def test_assign_role_raises_for_unknown_pair() -> None:
    with pytest.raises(RoleNotAssigned):
        assign_role("nonexistent_tool", "nonexistent_param")
