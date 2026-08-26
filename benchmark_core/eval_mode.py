"""Capture and validate effective GAWorld evaluation-mode state."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from v0_first_batch.schema import GateResult


def _enabled(config: Mapping[str, Any], section: str) -> bool:
    block = config.get(section) or {}
    return bool(block.get("enabled")) if isinstance(block, Mapping) else False


def capture_eval_mode_evidence(config: dict[str, Any]) -> dict[str, Any]:
    """Apply eval mode and return the effective state used by an R0 gate.

    The caller must explicitly set ``config["eval_mode"]["enabled"]``. This
    function does not opt a run into evaluation mode on the caller's behalf.
    """

    from gaworld.eval_mode import apply_eval_mode_runtime, eval_mode_block

    application = apply_eval_mode_runtime(config)
    block = eval_mode_block(config)
    return {
        "enabled": bool(block.get("enabled")),
        "applied": bool(application.get("applied")),
        "changes": list(application.get("changes") or []),
        "dynamic_behavior_enabled": _enabled(config, "dynamic_behavior"),
        "routine_change_enabled": _enabled(config, "routine_change"),
        "strict_interview_json": bool(block.get("strict_interview_json")),
        "diary_fallback_disabled": bool(block.get("disable_diary_fallback")),
    }


def validate_eval_mode_evidence(evidence: Mapping[str, Any] | None) -> tuple[bool, str]:
    """Return an R0 decision from recorded effective state, not a constant."""

    if not isinstance(evidence, Mapping):
        return False, "eval_mode_evidence_missing"

    failures: list[str] = []
    if not evidence.get("enabled"):
        failures.append("eval_mode_disabled")
    if not evidence.get("applied"):
        failures.append("eval_mode_not_applied")
    if evidence.get("dynamic_behavior_enabled") is not False:
        failures.append("dynamic_behavior_not_frozen")
    if evidence.get("routine_change_enabled") is not False:
        failures.append("routine_change_not_frozen")
    if evidence.get("strict_interview_json") is not True:
        failures.append("interview_contract_not_strict")
    if evidence.get("diary_fallback_disabled") is not True:
        failures.append("diary_fallback_not_disabled")
    return (not failures, "ok" if not failures else ",".join(failures))


def eval_mode_gate(evidence: Mapping[str, Any] | None) -> GateResult:
    """Build the canonical critical R0 gate for a new experiment."""

    passed, detail = validate_eval_mode_evidence(evidence)
    return GateResult("eval_mode_on", passed, critical=True, layer="R0", detail=detail)
