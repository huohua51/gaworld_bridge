"""Canonical v1/v2 sources for Rule agents. LLM must write equivalent files."""

from __future__ import annotations

_PARKING = '''SPEC_VERSION = "{version}"
PARKING_FREE_MINUTES = {value}


def fee_required(minutes):
    return int(minutes) >= PARKING_FREE_MINUTES
'''

_DEPOSIT = '''SPEC_VERSION = "{version}"
DEPOSIT_PERCENT = {value}


def deposit(price):
    return int(price) * DEPOSIT_PERCENT // 100
'''

_QUEUE = '''SPEC_VERSION = "{version}"
QUEUE_CAP = {value}


def can_join(length):
    return int(length) < QUEUE_CAP
'''

TEMPLATES = {
    "t3_parking_threshold_001": _PARKING,
    "t3_deposit_ratio_001": _DEPOSIT,
    "t3_queue_cap_001": _QUEUE,
}


def render_source(task: dict, version: str) -> str:
    change = dict(task["change_v1"] if version == "v1" else task["change_v2"])
    return TEMPLATES[task["id"]].format(version=version, value=change[task["target"]])
