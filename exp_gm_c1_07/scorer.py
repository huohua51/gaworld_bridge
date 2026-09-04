"""C1-07 identity wrapper around the unchanged C1-v5 scorer."""

from __future__ import annotations

from typing import Any

from exp_gm_c1_05.scorer import score_cell as _score_v5

WORKFLOW_ID = "exp_gm_c1_07_postmerge_fresh_surface"
SCORER_VERSION = "c1-postmerge-fresh-surface-v7.0"


def score_cell(
    task: dict[str, Any], variant: str, loop: dict[str, Any]
) -> dict[str, Any]:
    result = _score_v5(task, variant, loop)
    result["workflow_id"] = WORKFLOW_ID
    result["instance_id"] = f"c1_v7_{task['id']}_{variant}_full_s0"
    result.setdefault("extra", {})["experiment_id"] = "EXP-GM-C1-07"
    result["extra"]["protocol_reused_from"] = "EXP-GM-C1-05"
    result["extra"]["operational_predecessor"] = "EXP-GM-C1-06"
    return result
