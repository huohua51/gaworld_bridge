from __future__ import annotations

import hashlib
import subprocess
from datetime import datetime, timezone
from pathlib import Path

import yaml

from exp_gm_l1_01.budget import MODEL, TEMPERATURE
from exp_gm_l1_01.fairness import preflight
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
        "experiment_id": "EXP-GM-L1-01",
        "parent": "C1_STAGE",
        "phase": "rule",
        "frozen_at": datetime.now(timezone.utc).isoformat(),
        "task_card_hash": _sha_file(ROOT / "task_card.yaml"),
        "task_hash": _sha_files(sorted((ROOT / "oracle").glob("*.json")) + sorted((ROOT / "tasks").glob("*.yaml"))),
        "protocol_hash": _sha_file(ROOT / "protocol.md"),
        "scorer_hash": _sha_file(ROOT / "scorer.py"),
        "gaworld_continuity_hash": _sha_file(CONTINUITY) if CONTINUITY.is_file() else "missing",
        "runner_hash": _sha_files(
            [ROOT / "loop.py", ROOT / "prompts.py", ROOT / "contract.py", ROOT / "loader.py"]
        ),
        "base_commit": commit,
        "model": MODEL,
        "temperature": TEMPERATURE,
        "fairness_preflight": preflight(),
        "do_not_edit_after_freeze": [
            "task_card.yaml",
            "protocol.md",
            "scorer.py",
            "prompts.py",
            "contract.py",
            "loader.py",
            "loop.py",
            "tasks",
            "oracle",
        ],
        "heldout": "not_created",
        "direct_is_formal_result": False,
        "primary_track": "multi",
        "does_not_overwrite": ["EXP-GM-C1-01", "EXP-GM-C1-02", "EXP-GM-C1-03"],
        "c1_status": "development_partial_pass",
        "no_c1_04": True,
    }


def write_manifest(out_dir: Path) -> dict:
    payload = build_manifest()
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "FREEZE.yaml").write_text(yaml.safe_dump(payload, allow_unicode=True, sort_keys=False), encoding="utf-8")
    return payload
