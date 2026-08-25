#!/usr/bin/env python3
"""Freeze GM-05 version after Rule calibration. Do not edit after live runs start."""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

from v0_first_batch.paths import BRIDGE_ROOT

ROOT = BRIDGE_ROOT / "exp_gm_05"
OUT = BRIDGE_ROOT / "output" / "exp_gm_05_freeze_20260824"

FILES = [
    "task_card.yaml",
    "tasks.py",
    "roles.py",
    "artifacts.py",
    "budget.py",
    "scoring.py",
    "aggregate.py",
    "engine.py",
    "single_loop.py",
    "multi_loop.py",
    "drop_loop.py",
    "rule_controls.py",
    "run.py",
    "oracle/test_aid_v1.py",
    "oracle/test_aid_v2.py",
    "oracle/test_roster_v1.py",
    "oracle/test_roster_v2.py",
    "oracle/test_routing_v1.py",
    "oracle/test_routing_v2.py",
]


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    rows = []
    for rel in FILES:
        path = ROOT / rel
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        rows.append({"path": rel, "sha256": f"sha256:{digest}"})
    payload = {
        "experiment_id": "EXP-GM-05",
        "frozen_at": datetime.now(timezone.utc).isoformat(),
        "note": "Do not modify these files after GLM cells start.",
        "files": rows,
    }
    (OUT / "FREEZE.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
