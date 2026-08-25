"""Cell-level result schema and gate-then-score composition."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass
class GateResult:
    gate_id: str
    passed: bool
    critical: bool = True
    layer: str = "R0"
    detail: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class CriterionResult:
    criterion_id: str
    layer: str
    scorer: str
    evaluable: bool
    score: float | None
    max_score: float = 1.0
    passed: bool | None = None
    critical: bool = False
    weight: float = 1.0
    evidence_ids: list[str] = field(default_factory=list)
    detail: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


_EMPTY_FIRST_ERROR = {None, "", "none"}


def cover_first_error(result: dict[str, Any]) -> dict[str, Any]:
    """FullPass=0 时 first_error 不得为 none。不改 FullPass，不重算历史冻结文件。"""
    if result.get("full_pass") != 0:
        return result
    profile = dict(result.get("process_profile") or {})
    extra = dict(result.get("extra") or {})
    err = profile.get("first_error")
    if err in _EMPTY_FIRST_ERROR:
        err = extra.get("first_error")
    if err in _EMPTY_FIRST_ERROR:
        err = "unexplained_failure"
        extra["first_error_enumerator_gap"] = True
    profile["first_error"] = err
    extra["first_error"] = err
    result["process_profile"] = profile
    result["extra"] = extra
    return result


def compose(
    *,
    workflow_id: str,
    instance_id: str,
    measurement_gates: list[GateResult],
    artifact_gates: list[GateResult],
    criteria: list[CriterionResult],
    process_profile: dict[str, Any] | None = None,
    extra: dict[str, Any] | None = None,
) -> dict[str, Any]:
    measurement_valid = all(g.passed for g in measurement_gates if g.critical)
    if not measurement_valid:
        return {
            "workflow_id": workflow_id,
            "instance_id": instance_id,
            "measurement_valid": False,
            "full_pass": None,
            "task_score": None,
            "ranking_eligible": False,
            "status": "measurement_invalid",
            "gates": [g.to_dict() for g in measurement_gates + artifact_gates],
            "criteria": [c.to_dict() for c in criteria],
            "process_profile": process_profile or {},
            "extra": extra or {},
        }

    hard_fail = any(g.critical and not g.passed for g in artifact_gates)
    if hard_fail:
        return cover_first_error(
            {
                "workflow_id": workflow_id,
                "instance_id": instance_id,
                "measurement_valid": True,
                "full_pass": 0,
                "task_score": 0.0,
                "ranking_eligible": True,
                "status": "artifact_gate_failed",
                "gates": [g.to_dict() for g in measurement_gates + artifact_gates],
                "criteria": [c.to_dict() for c in criteria],
                "process_profile": process_profile or {},
                "extra": extra or {},
            }
        )

    scored = [c for c in criteria if c.evaluable and c.score is not None]
    weight_sum = sum(c.weight for c in scored) or 1.0
    task_score = sum((c.score or 0.0) / c.max_score * c.weight for c in scored) / weight_sum
    critical_ok = all(
        (c.passed is True) for c in criteria if c.critical and c.evaluable
    )
    full_pass = int(critical_ok and all(g.passed for g in artifact_gates if g.critical))
    return cover_first_error(
        {
            "workflow_id": workflow_id,
            "instance_id": instance_id,
            "measurement_valid": True,
            "full_pass": full_pass,
            "task_score": round(task_score, 4),
            "ranking_eligible": True,
            "status": "scored",
            "gates": [g.to_dict() for g in measurement_gates + artifact_gates],
            "criteria": [c.to_dict() for c in criteria],
            "process_profile": process_profile or {},
            "extra": extra or {},
        }
    )


def summarize_workflow(workflow_id: str, cells: list[dict[str, Any]]) -> dict[str, Any]:
    valid = [c for c in cells if c.get("measurement_valid")]
    scored = [c for c in valid if c.get("full_pass") is not None]
    coverage = len(valid) / len(cells) if cells else 0.0
    full_pass_rate = (
        sum(int(c["full_pass"]) for c in scored) / len(scored) if scored else None
    )
    mean_task_score = (
        sum(float(c["task_score"]) for c in scored) / len(scored) if scored else None
    )
    return {
        "workflow_id": workflow_id,
        "requested": len(cells),
        "measurement_valid": len(valid),
        "coverage": round(coverage, 4),
        "full_pass_rate": None if full_pass_rate is None else round(full_pass_rate, 4),
        "mean_task_score": None if mean_task_score is None else round(mean_task_score, 4),
        "ranking_eligible": coverage >= 0.9 and mean_task_score is not None,
        "cells": cells,
    }
