from __future__ import annotations

import hashlib
import subprocess
from datetime import datetime, timezone
from pathlib import Path

import yaml

from exp_gm_n1.budget import MODEL, TEMPERATURE
from exp_gm_n1.fairness import preflight
from v0_first_batch.paths import BRIDGE_ROOT

ROOT = Path(__file__).resolve().parent


def _sha_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _sha_files(paths: list[Path]) -> str:
    h = hashlib.sha256()
    for path in sorted(paths, key=lambda p: str(p)):
        h.update(path.read_bytes())
    return h.hexdigest()


def _base_commit() -> str:
    try:
        return subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=str(BRIDGE_ROOT), text=True).strip()
    except (subprocess.CalledProcessError, FileNotFoundError):
        return "unknown"


def build_manifest() -> dict:
    return {
        "experiment_id": "EXP-GM-N1",
        "phase": "seed0",
        "frozen_at": datetime.now(timezone.utc).isoformat(),
        "task_card_hash": _sha_file(ROOT / "task_card.yaml"),
        "oracle_hash": _sha_files(sorted((ROOT / "oracle").glob("*.json")) + sorted((ROOT / "tasks").glob("*.yaml"))),
        "protocol_hash": _sha_file(ROOT / "protocol.md"),
        "scorer_hash": _sha_file(ROOT / "scorer.py"),
        "runner_hash": _sha_files(
            [ROOT / "run_matrix.py", ROOT / "loop.py", ROOT / "prompts.py", ROOT / "contract.py", ROOT / "fairness.py"]
        ),
        "base_commit": _base_commit(),
        "model": MODEL,
        "temperature": TEMPERATURE,
        "fairness_preflight": preflight(),
        "do_not_edit_after_freeze": [
            "task_card.yaml",
            "tasks/",
            "oracle/",
            "protocol.md",
            "scorer.py",
            "run_matrix.py",
            "loop.py",
            "prompts.py",
            "contract.py",
        ],
    }


def write_manifest(out_dir: Path) -> dict:
    payload = build_manifest()
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "FREEZE.yaml").write_text(yaml.safe_dump(payload, allow_unicode=True, sort_keys=False), encoding="utf-8")
    return payload
