"""Execute one deterministic T5 policy response cell."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from gaworld.city.policy import PolicyEvent, UrbanPolicyChannel


def run_cell(
    task: dict[str, Any], condition: str, track: str, out_dir: Path
) -> dict[str, Any]:
    out_dir.mkdir(parents=True, exist_ok=True)
    trace_path = out_dir / "policy_trace.jsonl"
    channel = UrbanPolicyChannel(
        str(trace_path), list(task["residents"]), dict(task["action_effects"])
    )
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
                signal=dict(task["policy_signal"]),
            )
        )

    effective_step = int(task["effective_step"])
    advanced = channel.advance_to(
        effective_step
        if track == "full" or condition == "no_policy"
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
        if condition == "real_policy" and eligible:
            action = str(task["target_action"])
        submitted = channel.submit_action(
            agent_id, action, evidence_policy_id=evidence_policy_id
        )
        actions.append({"agent_id": agent_id, **submitted})

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
    changed = [
        resident for resident in residents if resident["state"] != resident["baseline"]
    ]
    return {
        "trace_path": str(trace_path),
        "trace_nonempty": trace_path.is_file() and trace_path.stat().st_size > 0,
        "condition": condition,
        "track": track,
        "policy_id": policy_id,
        "registration": registration,
        "advanced": advanced,
        "policy_active": bool(policy_id and channel.policy_active(policy_id)),
        "perceptions": perceptions,
        "actions": actions,
        "residents": residents,
        "changed_agent_ids": [resident["agent_id"] for resident in changed],
        "behavior_change_rate": len(changed) / len(residents),
        "events": channel.event_names(),
        "denials": channel.denials(),
    }
