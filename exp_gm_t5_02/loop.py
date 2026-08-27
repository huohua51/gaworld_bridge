"""Execute one deterministic T5-v2 policy-semantics cell."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from gaworld.city.policy import PolicyEvent, UrbanPolicyChannel


def channel_condition(policy_state: str) -> str:
    """Map v2 public semantics onto the channel's versioned condition enum."""
    return {
        "binding": "real_policy",
        "nonbinding": "placebo_policy",
    }[policy_state]


def policy_signal(task: dict[str, Any], policy_state: str) -> dict[str, Any]:
    signal = dict(task["policy_signal"])
    signal.update(
        {
            "policy_state": policy_state,
            "effective_step": int(task["effective_step"]),
            "binding": policy_state == "binding",
            "required_action": (
                str(task["target_action"])
                if policy_state == "binding"
                else "keep_current"
            ),
        }
    )
    return signal


def run_cell(
    task: dict[str, Any], policy_state: str, track: str, out_dir: Path
) -> dict[str, Any]:
    out_dir.mkdir(parents=True, exist_ok=True)
    trace_path = out_dir / "policy_trace.jsonl"
    channel = UrbanPolicyChannel(
        str(trace_path), list(task["residents"]), dict(task["action_effects"])
    )
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
    actions: list[dict[str, Any]] = []
    for resident in task["residents"]:
        agent_id = str(resident["agent_id"])
        evidence_policy_id: str | None = None
        eligible = False
        if policy_id:
            perception = channel.perceive(policy_id, agent_id)
            perceptions.append({"agent_id": agent_id, **perception})
            if perception.get("ok"):
                evidence_policy_id = policy_id
                eligible = bool(perception.get("eligible"))
        action = "keep_current"
        if policy_state == "binding" and eligible:
            action = str(task["target_action"])
        submitted = channel.submit_action(
            agent_id, action, evidence_policy_id=evidence_policy_id
        )
        actions.append({"agent_id": agent_id, **submitted})

    return {
        "trace_path": str(trace_path),
        "trace_nonempty": trace_path.is_file() and trace_path.stat().st_size > 0,
        "policy_state": policy_state,
        "track": track,
        "policy_id": policy_id,
        "registration": registration,
        "advanced": advanced,
        "policy_active": bool(policy_id and channel.policy_active(policy_id)),
        "perceptions": perceptions,
        "actions": actions,
        "events": channel.event_names(),
        "denials": channel.denials(),
    }
