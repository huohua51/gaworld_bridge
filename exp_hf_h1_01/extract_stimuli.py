#!/usr/bin/env python3
"""Mechanically extract 18 Full-track Agent stimuli. No cherry-picking."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import yaml

from exp_hf_h1_01.anonymize import from_i1, from_l1, from_t3, rater_view, stimulus_id
from v0_first_batch.paths import BRIDGE_ROOT

ROOT = Path(__file__).resolve().parent
OUT = BRIDGE_ROOT / "output" / "exp_hf_h1_01_20260825"
SAMPLING = yaml.safe_load((ROOT / "SAMPLING.yaml").read_text(encoding="utf-8"))
BLIND_NAMESPACE = "EXP-HF-H1-01-development-pilot-v1"

RUN = {
    "T3": lambda task, variant: BRIDGE_ROOT / "output" / "holdout_t3_20260825" / "runs" / f"{task}_{variant}_multi_r0",
    "I1": lambda task, variant: BRIDGE_ROOT / "output" / "holdout_i1_20260825" / "runs" / f"{task}_{variant}_full_s0",
    "L1": lambda task, variant: BRIDGE_ROOT / "output" / "holdout_l1_20260825" / "runs" / f"{task}_{variant}_multi_r0",
}
BUILD = {"T3": from_t3, "I1": from_i1, "L1": from_l1}


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def blind_id(internal_id: str) -> str:
    """Return a source-neutral display ID for the rater interface."""

    digest = hashlib.sha256(
        f"{BLIND_NAMESPACE}:{internal_id}".encode()
    ).hexdigest()[:12]
    return f"trace-{digest}"


def _read_slot(path: Path, fallback: dict) -> dict:
    if not path.is_file():
        path.write_text(
            json.dumps(fallback, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        return fallback
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {**fallback, "status": "invalid_slot_file"}
    return payload if isinstance(payload, dict) else {**fallback, "status": "invalid_slot_file"}


def _write_blind_display(display_dir: Path, trace: dict, internal_id: str) -> str:
    display_id = blind_id(internal_id)
    view = rater_view(trace)
    view["stimulus_id"] = display_id
    (display_dir / f"{display_id}.json").write_text(
        json.dumps(view, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return display_id


def planned_cells() -> list[tuple[str, str, str]]:
    cells = []
    for construct in SAMPLING["matrix"]["constructs"]:
        for task in SAMPLING["matrix"]["tasks"][construct]:
            for variant in SAMPLING["matrix"]["variants"]:
                cells.append((construct, task, variant))
    return cells


def extract(out_dir: Path | None = None) -> dict:
    target_out = Path(out_dir) if out_dir is not None else OUT
    cells = planned_cells()
    assert len(cells) == 18, len(cells)
    registry = []
    agent_dir = target_out / "stimuli" / "agent"
    display_dir = target_out / "stimuli" / "display"
    human_dir = target_out / "stimuli" / "human"
    agent_dir.mkdir(parents=True, exist_ok=True)
    display_dir.mkdir(parents=True, exist_ok=True)
    human_dir.mkdir(parents=True, exist_ok=True)
    for construct, task, variant in cells:
        run_dir = RUN[construct](task, variant)
        cell_path = run_dir / "cell_result.json"
        if not cell_path.is_file():
            raise FileNotFoundError(run_dir)
        cell = json.loads(cell_path.read_text(encoding="utf-8"))
        extra = cell.get("extra") or {}
        track = extra.get("track")
        expected = {"T3": "multi", "I1": "full", "L1": "multi"}[construct]
        if track != expected:
            raise ValueError(f"{run_dir} track={track} expected={expected}")
        if extra.get("variant") != variant:
            raise ValueError(f"{run_dir} variant mismatch")
        sid = stimulus_id(construct, task, variant)
        trace = BUILD[construct](run_dir, task_id=task, variant=variant)
        trace["source_run"] = str(run_dir.relative_to(BRIDGE_ROOT))
        trace["source_cell_sha256"] = _sha(cell_path)
        (agent_dir / f"{sid}.json").write_text(json.dumps(trace, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        (display_dir / f"{sid}.json").write_text(
            json.dumps(rater_view(trace), ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        agent_blind_id = _write_blind_display(display_dir, trace, sid)
        human_slot = {
            "stimulus_id": f"{sid}-human",
            "pairs_with": sid,
            "construct": construct,
            "task_id": task,
            "variant": variant,
            "status": "not_collected",
            "source_kind": "human",
            "h1_role": "development_stimulus",
        }
        slot_path = human_dir / f"{sid}-human.json"
        slot = _read_slot(slot_path, human_slot)
        human_status = str(slot.get("status") or "not_collected")
        human_blind_id = blind_id(f"{sid}-human")
        if human_status == "collected":
            _write_blind_display(display_dir, slot, f"{sid}-human")
        registry.append(
            {
                "stimulus_id": sid,
                "construct": construct,
                "task_id": task,
                "variant": variant,
                "variant_code": trace["variant_code"],
                "track": expected,
                "source_kind": "agent",
                "source_run": trace["source_run"],
                "source_cell_sha256": trace["source_cell_sha256"],
                "measurement_valid": cell.get("measurement_valid"),
                "full_pass_hidden_from_rater": cell.get("full_pass"),
                "functional_role": "sealed_holdout_result",
                "H1_role": "development_stimulus",
                "not_future_h1_holdout": True,
                "human_slot": f"{sid}-human",
                "human_status": human_status,
                "agent_blind_id": agent_blind_id,
                "human_blind_id": human_blind_id,
            }
        )
    n_human_collected = sum(
        item["human_status"] == "collected" for item in registry
    )
    payload = {
        "experiment_id": "EXP-HF-H1-01",
        "n_agent": len(registry),
        "n_human_collected": n_human_collected,
        "n_human_slots": 18,
        "selection_rule": "mechanical_task_variant_repeat",
        "manual_best_case_selection": False,
        "repeat_index": 0,
        "c1_included": False,
        "ranking_eligible": False,
        "h1_formal_score": None,
        "cells": registry,
    }
    target_out.mkdir(parents=True, exist_ok=True)
    (target_out / "STIMULUS_REGISTRY.yaml").write_text(
        yaml.safe_dump(payload, allow_unicode=True, sort_keys=False),
        encoding="utf-8",
    )
    display_ids = [item["agent_blind_id"] for item in registry]
    display_ids.extend(
        item["human_blind_id"]
        for item in registry
        if item["human_status"] == "collected"
    )
    (display_dir / "index.json").write_text(
        json.dumps(
            {
                "stimuli": sorted(display_ids),
                "n_agent": len(registry),
                "n_human_collected": n_human_collected,
                "n_human_slots": len(registry),
            },
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    return payload


def refresh_human_registry(out_dir: Path | None = None) -> dict:
    """Refresh collected counts and blind views without rebuilding Agent traces."""

    target_out = Path(out_dir) if out_dir is not None else OUT
    registry_path = target_out / "STIMULUS_REGISTRY.yaml"
    registry = yaml.safe_load(registry_path.read_text(encoding="utf-8")) or {}
    cells = registry.get("cells") or []
    display_dir = target_out / "stimuli" / "display"
    human_dir = target_out / "stimuli" / "human"
    display_dir.mkdir(parents=True, exist_ok=True)
    display_ids = []
    collected = 0
    for cell in cells:
        sid = str(cell["stimulus_id"])
        agent_display_id = str(cell.get("agent_blind_id") or blind_id(sid))
        human_internal_id = str(cell.get("human_slot") or f"{sid}-human")
        human_display_id = str(
            cell.get("human_blind_id") or blind_id(human_internal_id)
        )
        cell["agent_blind_id"] = agent_display_id
        cell["human_blind_id"] = human_display_id
        display_ids.append(agent_display_id)
        slot_path = human_dir / f"{human_internal_id}.json"
        try:
            slot = json.loads(slot_path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            slot = {"status": "invalid_slot_file"}
        status = str(slot.get("status") or "not_collected")
        cell["human_status"] = status
        if status == "collected":
            _write_blind_display(display_dir, slot, human_internal_id)
            display_ids.append(human_display_id)
            collected += 1
    registry["n_human_collected"] = collected
    registry["n_human_slots"] = len(cells)
    registry_path.write_text(
        yaml.safe_dump(registry, allow_unicode=True, sort_keys=False),
        encoding="utf-8",
    )
    (display_dir / "index.json").write_text(
        json.dumps(
            {
                "stimuli": sorted(display_ids),
                "n_agent": int(registry.get("n_agent") or len(cells)),
                "n_human_collected": collected,
                "n_human_slots": len(cells),
            },
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    return registry


def main() -> int:
    payload = extract()
    print(f"extracted {payload['n_agent']} agent stimuli -> {OUT}", flush=True)
    return 0 if payload["n_agent"] == 18 else 1


if __name__ == "__main__":
    raise SystemExit(main())
