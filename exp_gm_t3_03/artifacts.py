"""Canonical v1/v2 sources for Rule agents. LLM must write equivalent files."""

from __future__ import annotations

_SHIP = '''SPEC_VERSION = "{version}"
FREE_SHIP_KG = {value}


def free_shipping(kg):
    return int(kg) >= FREE_SHIP_KG
'''

_REDEEM = '''SPEC_VERSION = "{version}"
REDEEM_MIN = {value}


def can_redeem(points):
    return int(points) >= REDEEM_MIN
'''

_ALERT = '''SPEC_VERSION = "{version}"
ALERT_C = {value}


def should_alert(temp):
    return int(temp) >= ALERT_C
'''

TEMPLATES = {
    "t3_free_ship_kg_001": _SHIP,
    "t3_redeem_points_001": _REDEEM,
    "t3_alert_celsius_001": _ALERT,
}


def render_source(task: dict, version: str) -> str:
    change = dict(task["change_v1"] if version == "v1" else task["change_v2"])
    return TEMPLATES[task["id"]].format(version=version, value=change[task["target"]])
