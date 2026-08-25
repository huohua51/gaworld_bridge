"""Canonical v1/v2 sources for Rule agents. LLM must write equivalent files."""

from __future__ import annotations

_QUEUE = '''SPEC_VERSION = "{version}"
QUEUE_MAX = {value}


def queue_full(n):
    return int(n) >= QUEUE_MAX
'''

_BATT = '''SPEC_VERSION = "{version}"
MIN_BATTERY = {value}


def battery_ok(pct):
    return int(pct) >= MIN_BATTERY
'''

_NOISE = '''SPEC_VERSION = "{version}"
NOISE_DB = {value}


def too_loud(db):
    return int(db) >= NOISE_DB
'''

TEMPLATES = {
    "t3_ho_queue_max_001": _QUEUE,
    "t3_ho_battery_pct_001": _BATT,
    "t3_ho_noise_db_001": _NOISE,
}


def render_source(task: dict, version: str) -> str:
    change = dict(task["change_v1"] if version == "v1" else task["change_v2"])
    return TEMPLATES[task["id"]].format(version=version, value=change[task["target"]])
