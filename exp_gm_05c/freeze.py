#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

from v0_first_batch.paths import BRIDGE_ROOT

ROOT = BRIDGE_ROOT / "exp_gm_05c"
OUT = BRIDGE_ROOT / "output" / "exp_gm_05c_r1_freeze_20260824"
FILES = [
    "tasks.py",
    "roles.py",
    "scoring.py",
    "fork_loop.py",
    "aggregate.py",
    "budget.py",
    "inspect.py",
    "contract.py",
]


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    rows = [{"path": rel, "sha256": "sha256:" + hashlib.sha256((ROOT / rel).read_bytes()).hexdigest()} for rel in FILES]
    l1 = BRIDGE_ROOT / "output" / "exp_gm_05b_freeze_20260824" / "FREEZE.json"
    payload = {
        "experiment_id": "EXP-GM-05c-r1",
        "parent": "EXP-GM-05c-r0",
        "change_scope": "review_action_output_contract_only",
        "frozen_at": datetime.now(timezone.utc).isoformat(),
        "l1_tasks": "frozen_from_exp_gm_05b",
        "l1_freeze": str(l1) if l1.exists() else None,
        "files": rows,
    }
    (OUT / "FREEZE.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print((OUT / "FREEZE.json").read_text(encoding="utf-8"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
