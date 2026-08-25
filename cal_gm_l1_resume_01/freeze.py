from __future__ import annotations

import hashlib
import subprocess
from datetime import datetime, timezone
from pathlib import Path

import yaml

from v0_first_batch.paths import BRIDGE_ROOT, GAWORLD_ROOT

ROOT = Path(__file__).resolve().parent
CONTINUITY = GAWORLD_ROOT / "gaworld" / "work" / "continuity.py"


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
        "experiment_id": "CAL-GM-L1-RESUME-01",
        "parent": "EXP-GM-L1-01b",
        "phase": "rule",
        "frozen_at": datetime.now(timezone.utc).isoformat(),
        "task_card_hash": _sha_file(ROOT / "task_card.yaml"),
        "oracle_hash": _sha_files(sorted((ROOT / "oracle").glob("*.json")) + sorted((ROOT / "tasks").glob("*.yaml"))),
        "protocol_hash": _sha_file(ROOT / "protocol.md"),
        "scorer_hash": _sha_file(ROOT / "scorer.py"),
        "gaworld_next_step": _sha_file(CONTINUITY) if CONTINUITY.is_file() else "missing",
        "runner_hash": _sha_files([ROOT / "loop.py", ROOT / "prompts.py", ROOT / "contract.py", ROOT / "loader.py"]),
        "base_commit": commit,
        "model": "GLM-4-Flash",
        "temperature": 0,
        "do_not_edit_after_freeze": ["task_card.yaml", "tasks/", "oracle/", "protocol.md", "scorer.py", "prompts.py", "contract.py", "loader.py"],
        "does_not_overwrite": ["EXP-GM-L1-01", "EXP-GM-L1-01b"],
    }


def write_manifest(out_dir: Path) -> dict:
    payload = build_manifest()
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "FREEZE.yaml").write_text(yaml.safe_dump(payload, allow_unicode=True, sort_keys=False), encoding="utf-8")
    return payload
