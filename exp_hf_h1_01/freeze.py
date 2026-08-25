from __future__ import annotations

import hashlib
import subprocess
from datetime import datetime, timezone
from pathlib import Path

import yaml

from v0_first_batch.paths import BRIDGE_ROOT

ROOT = Path(__file__).resolve().parent


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write_manifest(out_dir: Path) -> dict:
    try:
        commit = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=str(BRIDGE_ROOT), text=True).strip()
    except (subprocess.CalledProcessError, FileNotFoundError):
        commit = "unknown"
    payload = {
        "experiment_id": "EXP-HF-H1-01",
        "phase": "infrastructure",
        "frozen_at": datetime.now(timezone.utc).isoformat(),
        "base_commit": commit,
        "sampling_hash": _sha(ROOT / "SAMPLING.yaml"),
        "rubric_hash": _sha(ROOT / "rubric.yaml"),
        "protocol_hash": _sha(ROOT / "protocol.md"),
        "task_card_hash": _sha(ROOT / "task_card.yaml"),
        "do_not_edit_after_pilot_freeze": [
            "SAMPLING.yaml",
            "rubric.yaml",
            "protocol.md",
            "human_protocols",
        ],
        "note": "基础设施冻结。Rubric 在认知访谈前仍可改；访谈后正式冻结。刺激抽样规则即刻冻结。",
        "ranking_eligible": False,
        "h1_formal_score": None,
    }
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "FREEZE.yaml").write_text(yaml.safe_dump(payload, allow_unicode=True, sort_keys=False), encoding="utf-8")
    return payload
