"""Versioned identity wrapper around the frozen REL1-v3 scorer."""

from __future__ import annotations

from typing import Any

from exp_rel1_03.scorer import score_cell as _score_v3

WORKFLOW_ID = "exp_rel1_04_postmerge_fresh_surface"
SCORER_VERSION = "rel1-postmerge-fresh-surface-v4.0"


def score_cell(
    task: dict[str, Any], variant: str, loop: dict[str, Any]
) -> dict[str, Any]:
    result = _score_v3(task, variant, loop)
    result["workflow_id"] = WORKFLOW_ID
    result["instance_id"] = f"rel1_v4_{task['id']}_{variant}_full_s0"
    result.setdefault("extra", {})["experiment_id"] = "EXP-GM-REL1-04"
    result["extra"]["protocol_reused_from"] = "EXP-GM-REL1-03"
    return result
