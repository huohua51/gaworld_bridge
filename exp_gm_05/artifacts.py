"""Deterministic v1/v2 sources. Only the registered constant differs."""

from __future__ import annotations

_AID = '''SPEC_VERSION = "{version}"
INCOME_CAP = {value}
MIN_AGE = 18
TOTAL_BUDGET = 10000
PROOF_REQUIRED = True

_PRIORITY = {{"critical": 0, "high": 1, "standard": 2}}


def eligible(applicant):
    age = int(applicant.get("age") or 0)
    income = int(applicant.get("income") or 0)
    proof = bool(applicant.get("proof"))
    if age < MIN_AGE:
        return False
    if income > INCOME_CAP:
        return False
    if PROOF_REQUIRED and not proof:
        return False
    return True


def allocate(applicants):
    ranked = []
    for index, person in enumerate(applicants or []):
        if not eligible(person):
            continue
        ranked.append((_PRIORITY.get(str(person.get("priority") or "standard"), 9), index, person))
    ranked.sort()
    remaining = TOTAL_BUDGET
    out = []
    for _, _, person in ranked:
        request = int(person.get("request") or 0)
        grant = min(max(request, 0), remaining)
        remaining -= grant
        out.append({{"id": person.get("id"), "granted": grant}})
    return out
'''

_ROSTER = '''SPEC_VERSION = "{version}"
NIGHT_SHIFT_MINIMUM = {value}
MAX_HOURS = 12
CERTIFIED_ROLES = ("medic",)


def valid_roster(assignments, workers, shifts):
    worker_map = {{item["id"]: item for item in workers}}
    shift_map = {{item["id"]: item for item in shifts}}
    by_shift = {{}}
    by_worker = {{}}
    for item in assignments or []:
        sid = item["shift_id"]
        wid = item["worker_id"]
        if sid not in shift_map or wid not in worker_map:
            return False
        by_shift.setdefault(sid, []).append(wid)
        by_worker.setdefault(wid, []).append(sid)
    for shift in shifts:
        people = by_shift.get(shift["id"]) or []
        if not people:
            return False
        role = shift.get("role")
        if role in CERTIFIED_ROLES:
            for wid in people:
                certs = worker_map[wid].get("certified") or []
                if role not in certs:
                    return False
        if shift.get("kind") == "night" and len(people) < NIGHT_SHIFT_MINIMUM:
            return False
    for wid, sids in by_worker.items():
        hours = sum(int(shift_map[sid].get("hours") or 0) for sid in sids)
        if hours > MAX_HOURS:
            return False
        slots = [shift_map[sid].get("slot") for sid in sids]
        if len(slots) != len(set(slots)):
            return False
    return True


def assign(workers, shifts):
    leftover = list(workers)
    out = []
    for shift in shifts:
        need = NIGHT_SHIFT_MINIMUM if shift.get("kind") == "night" else 1
        role = shift.get("role")

        def _score(person):
            certs = person.get("certified") or []
            if role in CERTIFIED_ROLES:
                return 0 if role in certs else 99
            return 0 if not any(item in CERTIFIED_ROLES for item in certs) else 1

        chosen = []
        for person in sorted(leftover, key=_score):
            if len(chosen) >= need:
                break
            certs = person.get("certified") or []
            if role in CERTIFIED_ROLES and role not in certs:
                continue
            chosen.append(person)
        if len(chosen) < need:
            return []
        chosen_ids = {{item["id"] for item in chosen}}
        leftover = [item for item in leftover if item["id"] not in chosen_ids]
        for person in chosen:
            out.append({{"worker_id": person["id"], "shift_id": shift["id"]}})
    return out
'''

_ROUTING = '''SPEC_VERSION = "{version}"
HIGH_PRIORITY_THRESHOLD = {value}
DEADLINE_HOURS = 2
STANDARD_HOURS = 8


def is_high_priority(incident):
    return int(incident.get("severity") or 0) >= HIGH_PRIORITY_THRESHOLD


def route(incident, centers):
    high = is_high_priority(incident)
    region = incident.get("region")
    deadline = DEADLINE_HOURS if high else STANDARD_HOURS
    for center in centers or []:
        if center.get("closed"):
            continue
        if center.get("region") != region:
            continue
        used = int(center.get("used") or 0)
        capacity = int(center.get("capacity") or 0)
        if used >= capacity:
            continue
        return {{"center_id": center.get("id"), "high_priority": high, "deadline_hours": deadline}}
    return {{"center_id": None, "high_priority": high, "deadline_hours": deadline}}
'''


TEMPLATES = {
    "gm05_aid_allocation_001": _AID,
    "gm05_shift_roster_001": _ROSTER,
    "gm05_incident_routing_001": _ROUTING,
}


def render_source(task: dict, version: str) -> str:
    change = dict(task["change_v1"] if version == "v1" else task["change_v2"])
    value = change[task["path"]]
    return TEMPLATES[task["id"]].format(version=version, value=value)
