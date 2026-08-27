"""Build unambiguous global policy context and resident directives for T5-v3."""

from __future__ import annotations

from typing import Any

POLICY_STATES = ("absence", "binding", "nonbinding")


def channel_condition(policy_state: str) -> str:
    return {
        "binding": "real_policy",
        "nonbinding": "placebo_policy",
    }[policy_state]


def policy_signal(task: dict[str, Any], policy_state: str) -> dict[str, Any]:
    if policy_state not in {"binding", "nonbinding"}:
        raise ValueError(f"policy signal requires a notice state: {policy_state}")
    signal = dict(task["policy_signal"])
    signal.update(
        {
            "policy_state": policy_state,
            "effective_step": int(task["effective_step"]),
            "binding": policy_state == "binding",
            "policy_action": str(task["target_action"]),
            "target_groups": [str(item) for item in task["target_groups"]],
        }
    )
    return signal


def policy_context(
    task: dict[str, Any],
    policy_state: str,
    perception: dict[str, Any] | None,
) -> dict[str, Any]:
    if not perception or not perception.get("ok"):
        return {
            "status": "absence",
            "notice_present": False,
            "binding": False,
            "notice": None,
        }
    signal = dict(perception["signal"])
    return {
        "status": policy_state,
        "notice_present": True,
        "binding": policy_state == "binding",
        "notice": {
            "name": str(signal["name"]),
            "channel": str(signal["channel"]),
            "policy_action": str(signal["policy_action"]),
            "target_groups": [str(item) for item in signal["target_groups"]],
        },
    }


def resident_directive(
    task: dict[str, Any],
    policy_state: str,
    perception: dict[str, Any] | None,
) -> dict[str, Any]:
    notice_present = bool(perception and perception.get("ok"))
    target_match = bool(notice_present and perception.get("eligible"))
    authorized = bool(policy_state == "binding" and target_match)
    return {
        "target_match": target_match,
        "authorized": authorized,
        "action": str(task["target_action"]) if authorized else "keep_current",
        "authority": "sole_action_authority",
    }


def expected_actions(task: dict[str, Any], policy_state: str) -> dict[str, str]:
    target_groups = {str(item) for item in task["target_groups"]}
    return {
        str(resident["agent_id"]): (
            str(task["target_action"])
            if policy_state == "binding"
            and str(resident["group"]) in target_groups
            else "keep_current"
        )
        for resident in task["residents"]
    }


__all__ = [
    "POLICY_STATES",
    "channel_condition",
    "expected_actions",
    "policy_context",
    "policy_signal",
    "resident_directive",
]
