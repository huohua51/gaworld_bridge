from __future__ import annotations

import hashlib
import subprocess
from datetime import datetime, timezone
from pathlib import Path

import yaml

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
        "experiment_id": "HO-GM-I1-01",
        "parent": "EXP-GM-I1",
        "phase": "rule",
        "frozen_at": datetime.now(timezone.utc).isoformat(),
        "task_card_hash": _sha_file(ROOT / "task_card.yaml"),
        "task_hash": _sha_file(ROOT / "probes.py"),
        "scorer_hash": _sha_file(ROOT / "scoring.py"),
        "runner_hash": _sha_files(
            [ROOT / "run_exp_i1.py", ROOT / "loop.py", ROOT / "roles.py", ROOT / "probes.py"]
        ),
        "base_commit": commit,
        "model": "GLM-4-Flash",
        "temperature": 0,
        "do_not_edit_after_freeze": [
            "task_card.yaml",
            "probes.py",
            "scoring.py",
            "roles.py",
            "loop.py",
        ],
        "heldout": "this_experiment",
        "holdout_run_once": True,
        "does_not_overwrite": ["EXP-GM-I1", "EXP-GM-REL1", "EXP-GM-N1"],
        "probes": ["pier_berth_001", "pump_station_001", "library_hours_001"],
    }


def write_manifest(out_dir: Path) -> dict:
    payload = build_manifest()
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "FREEZE.yaml").write_text(yaml.safe_dump(payload, allow_unicode=True, sort_keys=False), encoding="utf-8")
    return payload
