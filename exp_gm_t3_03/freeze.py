from __future__ import annotations

import hashlib
import subprocess
from datetime import datetime, timezone
from pathlib import Path

import yaml

from exp_gm_t3_01.budget import MODEL, TEMPERATURE
from exp_gm_t3_03.fairness import preflight
from v0_first_batch.paths import BRIDGE_ROOT

ROOT = Path(__file__).resolve().parent


def _sha_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _sha_files(paths: list[Path]) -> str:
    h = hashlib.sha256()
    for path in sorted(paths, key=lambda p: str(p)):
        h.update(path.read_bytes())
    return h.hexdigest()


def build_manifest() -> dict:
    try:
        commit = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=str(BRIDGE_ROOT), text=True).strip()
    except (subprocess.CalledProcessError, FileNotFoundError):
        commit = "unknown"
    return {
        "experiment_id": "EXP-GM-T3-03",
        "parent": "EXP-GM-T3-02",
        "phase": "seed0",
        "frozen_at": datetime.now(timezone.utc).isoformat(),
        "task_card_hash": _sha_file(ROOT / "task_card.yaml"),
        "task_hash": _sha_files(
            sorted((ROOT / "oracle").glob("*.py"))
            + sorted((ROOT / "tasks").glob("*.yaml"))
        ),
        "protocol_hash": _sha_file(ROOT / "protocol.md"),
        "scorer_hash": _sha_file(ROOT / "scorer.py"),
        "runner_hash": _sha_files(
            [ROOT / "run_matrix.py", ROOT / "loop.py", ROOT / "prompts.py", ROOT / "loader.py", ROOT / "artifacts.py"]
        ),
        "t3_02_contract": _sha_file(BRIDGE_ROOT / "exp_gm_t3_02" / "contract.py"),
        "t3_02_integrity": _sha_file(BRIDGE_ROOT / "exp_gm_t3_02" / "integrity.py"),
        "change_01_contract": _sha_file(BRIDGE_ROOT / "cal_gm_change_01" / "contract.py"),
        "apply_01_prompt": _sha_file(BRIDGE_ROOT / "cal_gm_apply_01" / "prompts.py"),
        "base_commit": commit,
        "model": MODEL,
        "temperature": TEMPERATURE,
        "fairness_preflight": {k: v for k, v in preflight().items() if k not in {"v2_leaks_helper", "sha256_text"}},
        "do_not_edit_after_freeze": [
            "task_card.yaml",
            "protocol.md",
            "scorer.py",
            "prompts.py",
            "loader.py",
            "artifacts.py",
            "tasks",
            "oracle",
        ],
        "retained_from_t3_02": ["CHANGE_01_decision_contract", "APPLY_01_required_changes", "payload_integrity_trace"],
        "not_t3_01_or_t3_02_items": True,
    }


def write_manifest(out_dir: Path) -> dict:
    payload = build_manifest()
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "FREEZE.yaml").write_text(yaml.safe_dump(payload, allow_unicode=True, sort_keys=False), encoding="utf-8")
    return payload
