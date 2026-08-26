"""Task Card schema checks for the versioned benchmark kernel."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

TASK_FAMILIES = {f"T{i}" for i in range(1, 7)}
MECHANISMS = {f"M{i}" for i in range(1, 10)}
TARGET_AXES = {
    "functional",
    "human_validity",
    "both",
    "功能能力",
    "人类效度",
    "两者分别评分",
}
REQUIRED_FIELDS = {
    "task_id",
    "task_family",
    "target_axis",
    "mechanism",
    "control",
    "variant",
    "oracle",
    "required_events",
    "primary_metric",
    "diagnostic_metrics",
    "human_reference",
}


@dataclass(frozen=True)
class TaskCardValidation:
    valid: bool
    errors: tuple[str, ...]
    warnings: tuple[str, ...]


def _mechanism_ids(value: Any) -> set[str]:
    if isinstance(value, str):
        return {part for part in value.replace(",", " ").split() if part in MECHANISMS}
    if isinstance(value, (list, tuple, set)):
        return {str(part) for part in value if str(part) in MECHANISMS}
    return set()


def validate_task_card(card: Mapping[str, Any]) -> TaskCardValidation:
    """Validate a v1 Task Card against the fields registered in the plan."""

    missing = sorted(field for field in REQUIRED_FIELDS if field not in card)
    errors = [f"missing:{field}" for field in missing]
    warnings: list[str] = []

    family = str(card.get("task_family") or "")
    if family and family not in TASK_FAMILIES:
        errors.append(f"invalid_task_family:{family}")

    axis = str(card.get("target_axis") or "")
    if axis and axis not in TARGET_AXES:
        errors.append(f"invalid_target_axis:{axis}")

    if "mechanism" in card and not _mechanism_ids(card.get("mechanism")):
        errors.append("mechanism_requires_M1_to_M9")

    for field in ("required_events", "diagnostic_metrics"):
        value = card.get(field)
        if field in card and not isinstance(value, list):
            errors.append(f"{field}_must_be_list")

    if card.get("human_reference") in {None, "", "N/A"} and axis in {
        "human_validity",
        "人类效度",
        "both",
        "两者分别评分",
    }:
        warnings.append("human_reference_not_registered")

    return TaskCardValidation(not errors, tuple(errors), tuple(warnings))
