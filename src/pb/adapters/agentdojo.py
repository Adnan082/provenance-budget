"""AgentDojo-specific trace recording and task loading. Only benchmark-specific code
lives here — see CLAUDE.md 'Layout'.

`record_ground_truth_trace()` runs a task's known-correct tool-call sequence through
AgentDojo's own `GroundTruthPipeline` — zero model calls, fully deterministic — and
converts it into this project's trace schema via `messages_to_events()`. It's not a
substitute for recording a real agent (the ground-truth pipeline never deviates from
the correct path, so it can't produce `ASR_t`/`BTC` data on its own), but it's what
makes this adapter's message-to-trace conversion testable without an API key, and the
same `messages_to_events()` is what a real pipeline's recording will go through once
one is wired up — that path only needs to supply `messages` from a different source."""
from __future__ import annotations

from collections import deque
from collections.abc import Sequence
from typing import Any

from agentdojo.functions_runtime import FunctionsRuntime
from agentdojo.task_suite.load_suites import get_suite
from agentdojo.types import get_text_content_as_str

from pb.enforce.roles import RoleNotAssigned, assign_role
from pb.trace.record import content_address, hash_secret, truncate_repr
from pb.trace.record import TraceEvent
from pb.trace.schema import Call, RawArgument, Result, Span, TaskEnd


def _make_span(kind: str, content: str) -> Span:
    return Span(span_id=content_address(kind, content), kind=kind, content_repr=truncate_repr(content))


def _raw_argument(tool: str, param_name: str, value: object) -> RawArgument:
    text = repr(value)
    try:
        role = assign_role(tool, param_name)
    except RoleNotAssigned:
        role = None
    value_repr = hash_secret(text) if role == "credential" else truncate_repr(text)
    return RawArgument(param_name=param_name, value_repr=value_repr)


def messages_to_events(
    task_id: str,
    seed: int,
    user_prompt: str,
    messages: Sequence[dict[str, Any]],
    outcome: str,
) -> list[TraceEvent]:
    """Converts an AgentDojo message list (from any pipeline — ground truth now, a
    real agent later) into this project's trace events, in order. Tool-result
    messages are matched to the call that produced them by FIFO order within the
    message list, which is how both AgentDojo's ground-truth pipeline (always exactly
    one pending call at a time) and the standard multi-tool-call protocol (calls
    requested together, results returned in the same order) actually behave."""
    events: list[TraceEvent] = [_make_span("user_message", user_prompt)]
    pending_call_ids: deque[str] = deque()
    call_counter = 0

    for message in messages:
        role = message.get("role")
        if role == "assistant":
            for tool_call in message.get("tool_calls") or []:
                call_counter += 1
                call_id = f"{task_id}:{seed}:{call_counter}"
                arguments = tuple(
                    _raw_argument(tool_call.function, name, value)
                    for name, value in tool_call.args.items()
                )
                events.append(Call(call_id=call_id, tool=tool_call.function, arguments=arguments))
                pending_call_ids.append(call_id)
        elif role == "tool":
            if not pending_call_ids:
                raise ValueError("tool-result message with no pending call to match it to")
            call_id = pending_call_ids.popleft()
            error = message.get("error")
            if error:
                events.append(Result(call_id=call_id, result_span_id=None, error=str(error)))
                continue
            tool_call = message.get("tool_call")
            tool_name = tool_call.function if tool_call is not None else "unknown"
            text = get_text_content_as_str(message.get("content") or [])
            span = _make_span(f"tool_result:{tool_name}", text)
            events.append(span)
            events.append(Result(call_id=call_id, result_span_id=span.span_id))

    events.append(TaskEnd(task_id=task_id, seed=seed, outcome=outcome))
    return events


def record_ground_truth_trace(
    benchmark_version: str,
    suite_name: str,
    task_id: str,
    seed: int = 0,
    injections: dict[str, str] | None = None,
) -> list[TraceEvent]:
    """Runs one task's ground-truth tool-call sequence and converts it to trace
    events. No model call — see module docstring. `injections` lets the environment
    carry attacker-authored content (as AgentDojo's own injection mechanism does)
    even though the ground-truth agent won't act on it — useful for exercising
    EXTERNAL-content-in-a-tool-result spans without needing a real attack run."""
    from agentdojo.agent_pipeline.ground_truth_pipeline import GroundTruthPipeline

    suite = get_suite(benchmark_version, suite_name)
    task = suite.user_tasks[task_id]
    env = suite.load_and_inject_default_environment(injections or {})
    runtime = FunctionsRuntime(suite.tools)
    pipeline = GroundTruthPipeline(task)
    _, _, _, messages, _ = pipeline.query(task.PROMPT, runtime, env, [], {})
    return messages_to_events(
        task_id=task_id,
        seed=seed,
        user_prompt=task.PROMPT,
        messages=list(messages),
        outcome="ground_truth",
    )
