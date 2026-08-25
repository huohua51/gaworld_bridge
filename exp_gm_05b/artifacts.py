"""L1 two-rule sources. L2 GM-05 tasks are frozen and not imported."""

from __future__ import annotations

_AID = '''SPEC_VERSION = "{version}"
MIN_AGE = 18
INCOME_CAP = {value}


def eligible(age, income):
    return int(age) >= MIN_AGE and int(income) <= INCOME_CAP
'''

_HOURS = '''SPEC_VERSION = "{version}"
MAX_HOURS = {value}


def can_work(certified, hours):
    return bool(certified) and int(hours) <= MAX_HOURS
'''

_ROUTE = '''SPEC_VERSION = "{version}"
HIGH_PRIORITY_THRESHOLD = {value}


def route(severity, center_closed):
    if bool(center_closed):
        return None
    if int(severity) >= HIGH_PRIORITY_THRESHOLD:
        return "emergency"
    return "standard"
'''

TEMPLATES = {
    "gm05b_aid_elig_001": _AID,
    "gm05b_hours_cert_001": _HOURS,
    "gm05b_route_closed_001": _ROUTE,
}


def render_source(task: dict, version: str) -> str:
    change = dict(task["change_v1"] if version == "v1" else task["change_v2"])
    return TEMPLATES[task["id"]].format(version=version, value=change[task["path"]])
