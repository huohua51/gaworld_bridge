"""04d metrics: FalsePositiveRevisionRate and PatchAdoptionRate."""

from __future__ import annotations

from typing import Any

from exp_gm_04c.scoring import first_error as first_error_04c
from exp_gm_04c.scoring import process_success as process_success_04c
from exp_gm_04c.scoring import r0_ok


def first_error(**kwargs) -> str:
    err = first_error_04c(**kwargs)
    return err


def process_success(track: str, variant: str, loop: dict[str, Any], *, target_correct: bool, other_also: bool) -> bool:
    if loop.get("freeze_ok") is False and track == "full_review":
        return False
    return process_success_04c(track, variant, loop, target_correct=target_correct, other_also=other_also)


def false_positive_revision(cell: dict) -> bool | None:
    extra = cell.get("extra") or {}
    if extra.get("track") != "full_review" or extra.get("variant") != "control":
        return None
    return bool(extra.get("false_positive_revision"))


def patch_adoption_eligible(cell: dict) -> bool:
    extra = cell.get("extra") or {}
    return (
        extra.get("track") == "full_review"
        and extra.get("variant") == "intervention"
        and extra.get("review_advice_correct") is True
        and extra.get("review_delivered") is not False
    )
