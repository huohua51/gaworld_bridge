"""Model-driven T5-v2 explicit policy-semantics loop."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from gaworld.city.policy import PolicyEvent, UrbanPolicyChannel

from benchmark_core.model_runner import RecordedModelRunner
from exp_gm_t5_02.loop import channel_condition, policy_signal


def _registered_policy_state(
    task: dict[str, Any],
    policy_state: str,
    perception: dict[str, Any] | None,
) -> dict[str, Any]:
    if not perception or not perception.get("ok"):
        return {
            "status": "absence",
            "notice_present": False,
            "eligible": False,
            "required_action": "keep_current",
            "notice": None,
        }
    eligible = bool(perception.get("eligible"))
    return {
        "status": policy_state,
        "notice_present": True,
        "eligible": eligible,
        "required_action": (
            str(task["target_action"])
            if policy_state == "binding" and eligible
            else "keep_current"
        ),
        "notice": dict(perception["signal"]),
    }


def _prompt(
    *,
    resident: dict[str, Any],
    registered_policy_state: dict[str, Any],
    allowed_actions: list[str],
) -> str:
    return json.dumps(
        {
            "protocol": "gaworld-benchmark-t5-model-v2",
            "instruction": (
                "Follow the registered policy-semantics rules. Return exactly "
                "one JSON object matching response_schema. Do not use markdown "
                "or add fields."
            ),
            "registered_policy_rules": [
                (
                    "absence: notice_seen=false, binding=false, and "
                    "action=keep_current"
                ),
                (
                    "binding: notice_seen=true and binding=true; use exactly "
                    "required_action"
                ),
                (
                    "nonbinding: notice_seen=true, binding=false, and "
                    "action=keep_current regardless of eligibility"
                ),
                (
                    "resident group, current state, policy topic, and allowed "
                    "actions do not authorize a non-default action"
                ),
            ],
            "task_family": "T5",
            "resident": {
                "agent_id": str(resident["agent_id"]),
                "group": str(resident["group"]),
                "current_state": dict(resident["state"]),
            },
            "registered_policy_state": registered_policy_state,
            "allowed_actions": allowed_actions,
            "response_schema": {
                "notice_seen": "boolean",
                "binding": "boolean",
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
        expected = {"notice_seen", "binding", "action", "reason"}
        if set(payload) != expected:
            errors.append(f"keys_must_equal:{sorted(expected)}")
        for field in ("notice_seen", "binding"):
            if not isinstance(payload.get(field), bool):
                errors.append(f"{field}_must_be_boolean")
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
    policy_state: str,
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
    if policy_state != "absence":
        policy_id = str(task["policy_id"])
        registration = channel.register_policy(
            PolicyEvent(
                policy_id=policy_id,
                policy_version=str(task["policy_version"]),
                effective_step=int(task["effective_step"]),
                condition=channel_condition(policy_state),
                target_groups=tuple(str(item) for item in task["target_groups"]),
                signal=policy_signal(task, policy_state),
            )
        )
    effective_step = int(task["effective_step"])
    advanced = channel.advance_to(
        effective_step
        if track == "full" or policy_state == "absence"
        else effective_step - 1
    )

    perceptions: list[dict[str, Any]] = []
    submissions: list[dict[str, Any]] = []
    evidence_ids: list[str] = []
    policy_states: list[dict[str, Any]] = []
    for resident in task["residents"]:
        agent_id = str(resident["agent_id"])
        perception: dict[str, Any] | None = None
        if policy_id:
            perception = channel.perceive(policy_id, agent_id)
            perceptions.append({"agent_id": agent_id, **perception})
        state = _registered_policy_state(task, policy_state, perception)
        policy_states.append({"agent_id": agent_id, **state})
        response = model_runner.call_json(
            _prompt(
                resident=dict(resident),
                registered_policy_state=state,
                allowed_actions=sorted(allowed_actions),
            ),
            task="benchmark_t5_v2",
            agent_id=agent_id,
            validator=_validator(allowed_actions),
        )
        evidence_ids.append(response.evidence_id)
        if not response.ok:
            submissions.append(
                {"agent_id": agent_id, "ok": False, "reason": "model_response_invalid"}
            )
            continue
        adopted_policy_id = (
            policy_id
            if policy_id and state["notice_present"] and response.parsed["notice_seen"]
            else None
        )
        submitted = channel.submit_action(
            agent_id,
            str(response.parsed["action"]),
            evidence_policy_id=adopted_policy_id,
        )
        submissions.append({"agent_id": agent_id, **submitted})

    return {
        "trace_path": str(trace_path),
        "model_trace_path": str(model_runner.path),
        "trace_nonempty": trace_path.is_file() and trace_path.stat().st_size > 0,
        "policy_state": policy_state,
        "track": track,
        "policy_id": policy_id,
        "registration": registration,
        "advanced": advanced,
        "policy_active": bool(policy_id and channel.policy_active(policy_id)),
        "perceptions": perceptions,
        "registered_policy_states": policy_states,
        "submissions": submissions,
        "events": channel.event_names(),
        "denials": channel.denials(),
        "model_call_evidence_ids": evidence_ids,
        "model_summary": model_runner.summary(),
    }
