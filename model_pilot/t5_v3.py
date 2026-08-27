"""Model loop for the T5-v3 resident eligibility-scope protocol."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from gaworld.city.policy import PolicyEvent, UrbanPolicyChannel

from benchmark_core.model_runner import RecordedModelRunner
from exp_gm_t5_03.semantics import (
    channel_condition,
    policy_context,
    policy_signal,
    resident_directive,
)

PROMPT_PROTOCOL = "gaworld-benchmark-t5-model-v3"


def _prompt(
    *,
    resident: dict[str, Any],
    context: dict[str, Any],
    directive: dict[str, Any],
    candidate_actions: list[str],
) -> str:
    return json.dumps(
        {
            "protocol": PROMPT_PROTOCOL,
            "instruction": (
                "Return exactly one JSON object matching response_schema. "
                "Copy the registered semantic fields and resident directive; "
                "do not use markdown or add fields."
            ),
            "authorization_rules": [
                (
                    "policy_context describes the global notice and never "
                    "directly authorizes a resident action"
                ),
                (
                    "resident_directive is the sole action authority; copy "
                    "resident_directive.action exactly into action"
                ),
                (
                    "global binding=true does not authorize a resident when "
                    "resident_directive.authorized=false"
                ),
                (
                    "target_match=true under a nonbinding notice still means "
                    "authorized=false and action=keep_current"
                ),
                (
                    "resident group, current state, policy topic and candidate "
                    "action membership cannot override resident_directive"
                ),
            ],
            "task_family": "T5",
            "resident": {
                "agent_id": str(resident["agent_id"]),
                "group": str(resident["group"]),
                "current_state": dict(resident["state"]),
            },
            "policy_context": context,
            "resident_directive": directive,
            "candidate_actions": candidate_actions,
            "response_schema": {
                "notice_seen": "boolean",
                "binding": "boolean",
                "target_match": "boolean",
                "authorized": "boolean",
                "action": "string",
                "reason": "string",
            },
        },
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )


def _validator(candidate_actions: set[str]):
    def validator(payload: dict[str, Any]) -> list[str]:
        errors: list[str] = []
        expected = {
            "notice_seen",
            "binding",
            "target_match",
            "authorized",
            "action",
            "reason",
        }
        if set(payload) != expected:
            errors.append(f"keys_must_equal:{sorted(expected)}")
        for field in ("notice_seen", "binding", "target_match", "authorized"):
            if not isinstance(payload.get(field), bool):
                errors.append(f"{field}_must_be_boolean")
        if payload.get("action") not in candidate_actions:
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
    candidate_actions = {str(action) for action in actions}
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
    contexts: list[dict[str, Any]] = []
    directives: list[dict[str, Any]] = []
    submissions: list[dict[str, Any]] = []
    evidence_ids: list[str] = []
    for resident in task["residents"]:
        agent_id = str(resident["agent_id"])
        perception: dict[str, Any] | None = None
        if policy_id:
            perception = channel.perceive(policy_id, agent_id)
            perceptions.append({"agent_id": agent_id, **perception})
        context = policy_context(task, policy_state, perception)
        directive = resident_directive(task, policy_state, perception)
        contexts.append({"agent_id": agent_id, **context})
        directives.append({"agent_id": agent_id, **directive})
        response = model_runner.call_json(
            _prompt(
                resident=dict(resident),
                context=context,
                directive=directive,
                candidate_actions=sorted(candidate_actions),
            ),
            task="benchmark_t5_v3",
            agent_id=agent_id,
            validator=_validator(candidate_actions),
        )
        evidence_ids.append(response.evidence_id)
        if not response.ok:
            submissions.append(
                {"agent_id": agent_id, "ok": False, "reason": "model_response_invalid"}
            )
            continue
        adopted_policy_id = (
            policy_id
            if policy_id and context["notice_present"] and response.parsed["notice_seen"]
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
        "policy_contexts": contexts,
        "resident_directives": directives,
        "submissions": submissions,
        "events": channel.event_names(),
        "denials": channel.denials(),
        "model_call_evidence_ids": evidence_ids,
        "model_summary": model_runner.summary(),
    }


__all__ = ["PROMPT_PROTOCOL", "run_cell"]
