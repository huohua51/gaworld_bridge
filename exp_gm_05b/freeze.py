#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

from v0_first_batch.paths import BRIDGE_ROOT

ROOT = BRIDGE_ROOT / "exp_gm_05b"
OUT = BRIDGE_ROOT / "output" / "exp_gm_05b_freeze_20260824"
FILES = [
    "tasks.py",
    "artifacts.py",
    "roles.py",
    "scoring.py",
    "inspect.py",
    "direct_loop.py",
    "review_loop.py",
    "oracle/test_aid_v1.py",
    "oracle/test_aid_v2.py",
    "oracle/test_hours_v1.py",
    "oracle/test_hours_v2.py",
    "oracle/test_route_v1.py",
    "oracle/test_route_v2.py",
]


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    rows = [{"path": rel, "sha256": "sha256:" + hashlib.sha256((ROOT / rel).read_bytes()).hexdigest()} for rel in FILES]
    payload = {"experiment_id": "EXP-GM-05b", "frozen_at": datetime.now(timezone.utc).isoformat(), "files": rows}
    (OUT / "FREEZE.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print((OUT / "FREEZE.json").read_text(encoding="utf-8"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
