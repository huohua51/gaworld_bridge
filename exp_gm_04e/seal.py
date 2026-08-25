#!/usr/bin/env python3
"""Seal EXP-GM-04e evidence. Do not retune 04e prompts or touch held-out tasks."""

from __future__ import annotations

import hashlib
import json
import shutil
from datetime import datetime, timezone
from pathlib import Path

from v0_first_batch.paths import BRIDGE_ROOT

SEAL = BRIDGE_ROOT / "output" / "exp_gm_04e_seal_20260824"
PROMPTS = SEAL / "prompts"
HELD = SEAL / "heldout_snapshot"


def _sha256(path: Path) -> str:
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    return f"sha256:{digest}"


def _copy_and_hash(src: Path, dest: Path) -> dict[str, str]:
    dest.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src, dest)
    return {"src": str(src), "seal": str(dest), "sha256": _sha256(dest)}


def _hash_tree(root: Path, pattern: str) -> list[dict[str, str]]:
    rows = []
    for path in sorted(root.glob(pattern)):
        if path.is_file():
            rows.append({"path": str(path), "sha256": _sha256(path)})
    return rows


def main() -> int:
    SEAL.mkdir(parents=True, exist_ok=True)
    records: dict = {
        "experiment_id": "EXP-GM-04e",
        "status": "stop_before_full",
        "sealed_at": datetime.now(timezone.utc).isoformat(),
        "do_not": [
            "retune 04e development prompts",
            "run 04e-Full",
            "run original held-out tasks",
            "build auto-apply-patch environment tools",
        ],
        "prompts": [],
        "reviewer_cells": [],
        "executor_cells": [],
        "reports": [],
        "heldout": [],
    }
    for rel in (
        "exp_gm_04e/roles.py",
        "exp_gm_04e/executor.py",
        "exp_gm_04e/loop.py",
        "exp_gm_04e/loop_e.py",
        "exp_gm_04e/tasks.py",
        "exp_gm_04e/task_card.yaml",
        "exp_gm_04c/roles.py",
    ):
        src = BRIDGE_ROOT / rel
        records["prompts"].append(_copy_and_hash(src, PROMPTS / rel.replace("/", "__")))
    r_root = BRIDGE_ROOT / "output" / "exp_gm_04e_r_20260824"
    e_root = BRIDGE_ROOT / "output" / "exp_gm_04e_e_20260824"
    records["reviewer_cells"] = _hash_tree(r_root, "runs/*/cell_result.json")
    records["reviewer_drafts"] = _hash_tree(r_root, "runs/*/draft_main.py")
    records["executor_cells"] = _hash_tree(e_root, "runs/*/cell_result.json")
    records["executor_before"] = _hash_tree(e_root, "runs/*/draft_main.py")
    records["executor_after"] = _hash_tree(e_root, "runs/*/final_main.py")
    for report in (r_root / "REPORT.md", r_root / "cell_table.json", e_root / "REPORT.md", e_root / "cell_table.json"):
        records["reports"].append({"path": str(report), "sha256": _sha256(report)})
    held_files = [
        BRIDGE_ROOT / "exp_gm_04d" / "tasks.py",
        BRIDGE_ROOT / "exp_gm_04d" / "oracle" / "test_ship_v1.py",
        BRIDGE_ROOT / "exp_gm_04d" / "oracle" / "test_ship_v2.py",
        BRIDGE_ROOT / "exp_gm_04d" / "oracle" / "test_age_v1.py",
        BRIDGE_ROOT / "exp_gm_04d" / "oracle" / "test_age_v2.py",
        BRIDGE_ROOT / "exp_gm_04d" / "oracle" / "test_stock_v1.py",
        BRIDGE_ROOT / "exp_gm_04d" / "oracle" / "test_stock_v2.py",
    ]
    for src in held_files:
        records["heldout"].append(_copy_and_hash(src, HELD / src.name))
    (SEAL / "MANIFEST.json").write_text(json.dumps(records, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    note = [
        "# EXP-GM-04e Seal",
        "",
        f"- sealed_at：{records['sealed_at']}",
        "- status：stop_before_full",
        "- Reviewer 组件校准通过；完整审核协议未宣称已改进",
        "- typed-patch 协议失败；不能写成 Executor 不会改文件",
        "- Full 未跑；原留出题 sealed_not_run",
        "- 不得再调 04e 开发集提示词，不得自动应用 patch",
        "",
        f"- Reviewer cell_result：{len(records['reviewer_cells'])}",
        f"- Executor cell_result：{len(records['executor_cells'])}",
        f"- 留出快照：{len(records['heldout'])}",
        "",
    ]
    (SEAL / "README.md").write_text("\n".join(note), encoding="utf-8")
    print((SEAL / "README.md").read_text(encoding="utf-8"))
    print("manifest", SEAL / "MANIFEST.json")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
