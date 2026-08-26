"""Model-driven T5 policy perception and resident-action loop."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from gaworld.city.policy import PolicyEvent, UrbanPolicyChannel

from benchmark_core.model_runner import RecordedModelRunner


def _policy_signal(task: dict[str, Any], condition: str) -> dict[str, Any]:
    signal = dict(task["policy_signal"])
    if condition == "real_policy":
        signal.update(
            {
                "notice_type": "binding_rule",
                "target_action": str(task["target_action"]),
                "effective_step": int(task["effective_step"]),
            }
        )
    else:
        signal.update(
            {
                "notice_type": "matched_nonbinding_notice",
                "topic": "city notice format update",
                "effective_step": int(task["effective_step"]),
            }
        )
    return signal


def _prompt(
    *,
    resident: dict[str, Any],
    active_policy: dict[str, Any] | None,
    allowed_actions: list[str],
) -> str:
    return json.dumps(
        {
            "protocol": "gaworld-benchmark-t5-model-v1",
            "instruction": (
                "Return exactly one JSON object matching response_schema. "
                "Do not use markdown or hidden treatment assumptions."
            ),
            "task_family": "T5",
            "resident": {
                "agent_id": str(resident["agent_id"]),
                "group": str(resident["group"]),
                "current_state": dict(resident["state"]),
            },
            "active_policy": active_policy,
            "allowed_actions": allowed_actions,
            "response_schema": {
                "perceived": "boolean",
                "action": "string",
                "reason": "string",
            },
        },
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )


def _validator(allowed_actions: set[str]):
    def validator(payload: dict[str, Any]) -> list[str]:
        errors: list[str] = []
        if set(payload) != {"perceived", "action", "reason"}:
            errors.append("keys_must_equal:action,perceived,reason")
        if not isinstance(payload.get("perceived"), bool):
            errors.append("perceived_must_be_boolean")
        if payload.get("action") not in allowed_actions:
            errors.append("action_not_allowed")
        if (
            not isinstance(payload.get("reason"), str)
            or not payload.get("reason", "").strip()
        ):
            errors.append("reason_must_be_nonempty_string")
        return errors

    return validator


def run_cell(
    task: dict[str, Any],
    condition: str,
    track: str,
    out_dir: Path,
    model_runner: RecordedModelRunner,
) -> dict[str, Any]:
    out_dir.mkdir(parents=True, exist_ok=True)
    trace_path = out_dir / "policy_trace.jsonl"
    actions = dict(task["action_effects"])
    allowed_actions = {str(action) for action in actions}
    channel = UrbanPolicyChannel(str(trace_path), list(task["residents"]), actions)
    policy_id: str | None = None
    registration: dict[str, Any] | None = None
    if condition != "no_policy":
        policy_id = str(task["policy_id"])
        registration = channel.register_policy(
            PolicyEvent(
                policy_id=policy_id,
                policy_version=str(task["policy_version"]),
                effective_step=int(task["effective_step"]),
                condition=condition,
                target_groups=tuple(str(item) for item in task["target_groups"]),
                signal=_policy_signal(task, condition),
            )
        )
    effective_step = int(task["effective_step"])
    advanced = channel.advance_to(
        effective_step
        if track == "full" or condition == "no_policy"
        else effective_step - 1
    )
    perceptions: list[dict[str, Any]] = []
    model_call_evidence_ids: list[str] = []
    submissions: list[dict[str, Any]] = []
    for resident in task["residents"]:
        agent_id = str(resident["agent_id"])
        active_policy: dict[str, Any] | None = None
        if policy_id:
            perception = channel.perceive(policy_id, agent_id)
            perceptions.append({"agent_id": agent_id, **perception})
            if perception.get("ok"):
                active_policy = {
                    "policy_id": policy_id,
                    "signal": dict(perception["signal"]),
                    "eligible": bool(perception["eligible"]),
                }
        response = model_runner.call_json(
            _prompt(
                resident=dict(resident),
                active_policy=active_policy,
                allowed_actions=sorted(allowed_actions),
            ),
            task="benchmark_t5",
            agent_id=agent_id,
            validator=_validator(allowed_actions),
        )
        model_call_evidence_ids.append(response.evidence_id)
        if not response.ok:
            submissions.append(
                {"agent_id": agent_id, "ok": False, "reason": "model_response_invalid"}
            )
            continue
        adopted_policy_id = (
            policy_id if active_policy and response.parsed["perceived"] else None
        )
        submitted = channel.submit_action(
            agent_id,
            str(response.parsed["action"]),
            evidence_policy_id=adopted_policy_id,
        )
        submissions.append({"agent_id": agent_id, **submitted})

    residents = []
    for resident in task["residents"]:
        agent_id = str(resident["agent_id"])
        residents.append(
            {
                "agent_id": agent_id,
                "group": str(resident["group"]),
                "baseline": channel.baseline_of(agent_id),
                "state": channel.state_of(agent_id),
                "action": channel.action_of(agent_id),
            }
        )
    return {
        "trace_path": str(trace_path),
        "model_trace_path": str(model_runner.path),
        "trace_nonempty": trace_path.is_file() and trace_path.stat().st_size > 0,
        "condition": condition,
        "track": track,
        "policy_id": policy_id,
        "registration": registration,
        "advanced": advanced,
        "policy_active": bool(policy_id and channel.policy_active(policy_id)),
        "perceptions": perceptions,
        "submissions": submissions,
        "residents": residents,
        "events": channel.event_names(),
        "denials": channel.denials(),
        "model_call_evidence_ids": model_call_evidence_ids,
        "model_summary": model_runner.summary(),
    }
