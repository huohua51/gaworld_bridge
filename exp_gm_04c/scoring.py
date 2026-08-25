"""R0—R3 gates and locatable first_error for EXP-GM-04c."""

from __future__ import annotations

from typing import Any


def first_error(
    *,
    track: str,
    variant: str,
    events: list[str],
    draft_exists: bool,
    final_exists: bool,
    review_emitted: bool,
    review_contract_ok: bool,
    review_delivered: bool,
    review_read: bool,
    review_adopted: bool,
    review_advice_correct: bool | None,
    private_ok: bool,
    unauthorized_write: bool,
    stale_final: bool,
    target_correct: bool,
    absorbed: bool,
) -> str:
    if unauthorized_write:
        return "unauthorized_artifact_write"
    if track != "focused" and not draft_exists:
        return "draft_not_created"
    if track != "focused" and "review_requested" not in events:
        return "review_not_requested"
    if track != "focused" and not private_ok:
        return "review_private_context_missing"
    if track != "focused" and not review_emitted:
        return "review_not_emitted"
    if track != "focused" and not review_contract_ok:
        return "review_contract_invalid"
    if track == "full_review" and not review_delivered:
        return "review_not_delivered"
    if track != "focused" and not review_read:
        return "review_not_read"
    if track == "full_review" and variant == "intervention":
        if review_advice_correct and not review_adopted:
            return "review_not_adopted"
        if review_advice_correct and stale_final:
            return "stale_draft_reused"
        if review_advice_correct is False:
            return "review_not_adopted"
    if not final_exists or not target_correct:
        return "final_artifact_incorrect"
    if track != "focused" and not absorbed:
        return "result_not_absorbed"
    return "none"


def r0_ok(track: str, variant: str, loop: dict[str, Any]) -> tuple[bool, str]:
    if loop.get("leak_on_first_brief"):
        return False, f"v2 leaked into executor brief: {loop['leak_on_first_brief']}"
    if track == "drop_review" and not loop.get("inbox_empty"):
        return False, "drop-review inbox was not empty"
    if track == "full_review" and loop.get("inbox_empty") and variant == "intervention":
        return False, "full-review inbox empty"
    if track != "focused" and not loop.get("private_ok"):
        return False, "reviewer private context missing"
    if track == "focused" and loop.get("reviewer_calls"):
        return False, "focused track called reviewer"
    if track != "focused" and loop.get("reviewer_calls") != 1:
        return False, f"reviewer calls={loop.get('reviewer_calls')}"
    if track == "drop_review" and loop.get("leak_on_drop_retry"):
        return False, f"v2 leaked into drop retry: {loop['leak_on_drop_retry']}"
    if track != "focused" and "review_requested" not in (loop.get("events") or []):
        return False, "review was not requested"
    return True, "ok"


def process_success(track: str, variant: str, loop: dict[str, Any], *, target_correct: bool, other_also: bool) -> bool:
    if not target_correct or other_also:
        return False
    if track == "focused":
        return True
    if track == "drop_review":
        return variant == "control" and loop.get("inbox_empty")
    if variant == "control":
        return bool(loop.get("review_action")) and (loop.get("review_action") or {}).get("decision") == "approve"
    return bool(
        loop.get("review_advice_correct")
        and (loop.get("adopt") or {}).get("ok")
        and (loop.get("final_inspect") or {}).get("spec_version") == "v2"
    )
