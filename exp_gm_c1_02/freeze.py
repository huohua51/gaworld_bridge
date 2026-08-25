from __future__ import annotations

import hashlib
import subprocess
from datetime import datetime, timezone
from pathlib import Path

import yaml

from exp_gm_c1_02.budget import MODEL, TEMPERATURE
from exp_gm_c1_02.fairness import preflight
from v0_first_batch.paths import BRIDGE_ROOT, GAWORLD_ROOT

ROOT = Path(__file__).resolve().parent
COORD = GAWORLD_ROOT / "gaworld" / "work" / "coordination.py"


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
        "experiment_id": "EXP-GM-C1-02",
        "parent": "CAL-GM-C1-REPAIR-01",
        "phase": "rule",
        "frozen_at": datetime.now(timezone.utc).isoformat(),
        "task_card_hash": _sha_file(ROOT / "task_card.yaml"),
        "task_hash": _sha_files(sorted((ROOT / "oracle").glob("*.json")) + sorted((ROOT / "tasks").glob("*.yaml"))),
        "protocol_hash": _sha_file(ROOT / "protocol.md"),
        "scorer_hash": _sha_file(ROOT / "scorer.py"),
        "gaworld_coordination_hash": _sha_file(COORD) if COORD.is_file() else "missing",
        "runner_hash": _sha_files(
            [ROOT / "loop.py", ROOT / "prompts.py", ROOT / "contract.py", ROOT / "channel.py", ROOT / "loader.py"]
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
            "channel.py",
            "loader.py",
            "tasks",
            "oracle",
        ],
        "not_c1_01_items": True,
        "not_c1_comp_01_items": True,
        "not_c1_repair_01_items": True,
        "heldout": "not_created",
        "direct_is_formal_result": False,
        "primary_track": "multi",
    }


def write_manifest(out_dir: Path) -> dict:
    payload = build_manifest()
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "FREEZE.yaml").write_text(yaml.safe_dump(payload, allow_unicode=True, sort_keys=False), encoding="utf-8")
    return payload
