"""Read frozen OA-01 need_change_gate cells. Do not rescore them with OA-02."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from v0_first_batch.paths import BRIDGE_ROOT

OA01_FROZEN = BRIDGE_ROOT / "output" / "exp_gm_oa_01_20260824" / "cell_table.json"
BASELINE_PROTOCOL = "need_change_gate"


def load_oa01_need_change_gate() -> list[dict[str, Any]]:
    payload = json.loads(OA01_FROZEN.read_text(encoding="utf-8"))
    cells = (payload.get("summary") or {}).get("cells") or []
    frozen = []
    for cell in cells:
        extra = cell.get("extra") or {}
        if extra.get("protocol") != BASELINE_PROTOCOL:
            continue
        copied = dict(cell)
        copied["ranking_eligible"] = False
        extra = dict(extra)
        extra["frozen_source"] = "EXP-GM-OA-01"
        extra["rerun"] = False
        copied["extra"] = extra
        frozen.append(copied)
    if len(frozen) != 18:
        raise ValueError(f"expected 18 frozen need_change_gate cells, got {len(frozen)}")
    return frozen


def oa01_baseline_metrics(cells: list[dict[str, Any]]) -> dict[str, Any]:
    valid = [c for c in cells if c.get("measurement_valid")]
    control = [c for c in valid if (c.get("extra") or {}).get("variant") == "control"]
    intervention = [c for c in valid if (c.get("extra") or {}).get("variant") == "intervention"]
    scored = [c for c in valid if c.get("full_pass") is not None]

    def mean(items: list[dict], field: str) -> float | None:
        if not items:
            return None
        return round(sum(int(bool((c.get("extra") or {}).get(field))) for c in items) / len(items), 4)

    return {
        "source": "EXP-GM-OA-01 need_change_gate, frozen, not rerun",
        "n": len(cells),
        "Coverage": round(len(valid) / len(cells), 4) if cells else 0.0,
        "ActionSelectionAccuracy": mean(valid, "need_change_correct"),
        "ControlStabilityRate": mean(control, "target_correct"),
        "AdaptationRate": mean(intervention, "target_correct"),
        "ContractFailureRate": 0.0,
        "TargetCorrect": mean(valid, "target_correct"),
        "OracleConditionedFullPass": round(sum(int(c["full_pass"]) for c in scored) / len(scored), 4) if scored else None,
        "note": "ContractFailureRate=0 是因为 OA-01 统一 JSON 接受了 keep 的占位字段；失败记在 TargetCorrect / FullPass，不是提交拒绝。",
    }
