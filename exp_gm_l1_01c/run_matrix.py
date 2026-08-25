#!/usr/bin/env python3
"""EXP-GM-L1-01c. Full Multi interruption recovery. Direct is solvability only."""

from __future__ import annotations

import argparse
import json
import os
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

import yaml

from exp_gm_l1_01c.budget import KINDS, MODEL, PROVIDER, TEMPERATURE
from exp_gm_l1_01c.loader import TRACKS, VARIANTS, load_tasks
from exp_gm_l1_01c.loop import run_cell, run_direct
from exp_gm_l1_01c.prompts import rule_checkpoint, rule_direct, rule_handoff, rule_resume, rule_step
from exp_gm_l1_01c.rule_tests import main as rule_main
from exp_gm_l1_01c.scorer import score_cell
from exp_gm_l1_01c.loader import solve_outputs
from v0_first_batch.paths import BRIDGE_ROOT, GAWORLD_ROOT, ensure_import_paths
from v0_first_batch.schema import summarize_workflow

WORKFLOW_ID = "exp_gm_l1_01c_handoff"
EXPERIMENT_ID = "EXP-GM-L1-01c"
OUT = BRIDGE_ROOT / "output" / "exp_gm_l1_01c_20260825"


def _pin_glm() -> None:
    ensure_import_paths()
    from config import CONFIG
    from gaworld.eval_mode import apply_eval_mode_runtime

    providers = CONFIG.setdefault("llm", {}).setdefault("providers", {})
    glm = providers.setdefault(PROVIDER, {})
    if isinstance(glm, dict):
        glm["max_tokens"] = max(int(glm.get("max_tokens") or 0), 2048)
        glm["temperature"] = TEMPERATURE
    routing = CONFIG.setdefault("llm", {}).setdefault("routing", {})
    routing["default"] = PROVIDER
    tasks = dict(routing.get("tasks") or {})
    tasks["interview"] = PROVIDER
    routing["tasks"] = tasks
    os.environ["GAWORLD_LLM_PROVIDER"] = PROVIDER
    CONFIG.setdefault("eval_mode", {})["enabled"] = True
    apply_eval_mode_runtime(CONFIG)


def _llm(prompt: str) -> str:
    _pin_glm()
    from config import CONFIG
    from llm_providers import LLMRouter

    return LLMRouter(CONFIG).call(prompt, task="interview") or ""


def _load_freeze() -> dict:
    path = OUT / "FREEZE.yaml"
    if path.is_file():
        return yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    from exp_gm_l1_01c.freeze import write_manifest

    return write_manifest(OUT)


def _valid(cells: list[dict], track: str | None = None, variant: str | None = None) -> list[dict]:
    out = []
    for cell in cells:
        extra = cell.get("extra") or {}
        if track is not None and extra.get("track") != track:
            continue
        if variant is not None and extra.get("variant") != variant:
            continue
        if cell.get("measurement_valid"):
            out.append(cell)
    return out


def _mean(cells: list[dict], field: str) -> float | None:
    if not cells:
        return None
    vals = []
    for cell in cells:
        extra = cell.get("extra") or {}
        value = extra.get(field)
        if value is None:
            continue
        vals.append(float(value) if not isinstance(value, bool) else float(value))
    if not vals:
        return None
    return round(sum(vals) / len(vals), 4)


def _rate(cells: list[dict], field: str) -> float | None:
    if not cells:
        return None
    return round(sum(int(bool((c.get("extra") or {}).get(field))) for c in cells) / len(cells), 4)


def _full_rate(cells: list[dict], track: str) -> float | None:
    subset = [c for c in _valid(cells, track) if c.get("full_pass") is not None]
    if not subset:
        return None
    return round(sum(int(c["full_pass"]) for c in subset) / len(subset), 4)


def _coverage_track(cells: list[dict], track: str) -> float:
    subset = [c for c in cells if (c.get("extra") or {}).get("track") == track]
    if not subset:
        return 0.0
    return round(sum(int(bool(c.get("measurement_valid"))) for c in subset) / len(subset), 4)


def _strict_pair(cells: list[dict], track: str) -> float | None:
    groups: dict[tuple, dict[str, dict]] = {}
    for cell in _valid(cells, track):
        extra = cell.get("extra") or {}
        key = (extra.get("task_id"), extra.get("repeat_id"), extra.get("track"))
        groups.setdefault(key, {})[str(extra.get("variant"))] = cell
    pairs = [g for g in groups.values() if "control" in g and "intervention" in g]
    if not pairs:
        return None
    n = sum(1 for g in pairs if g["control"].get("full_pass") == 1 and g["intervention"].get("full_pass") == 1)
    return round(n / len(pairs), 4)


def _isolation_ok(cells: list[dict]) -> bool:
    ckpts = [c for c in cells if (c.get("extra") or {}).get("track") == "drop_checkpoint"]
    hands = [c for c in cells if (c.get("extra") or {}).get("track") == "drop_handoff"]
    if not ckpts or not hands:
        return False
    for cell in ckpts:
        extra = cell.get("extra") or {}
        if extra.get("variant") == "intervention" and extra.get("checkpoint_delivered"):
            return False
        if extra.get("variant") == "intervention" and not extra.get("b_ran"):
            return False
        if not extra.get("drop_checkpoint_isolated", True):
            return False
    for cell in hands:
        extra = cell.get("extra") or {}
        if extra.get("variant") == "intervention" and extra.get("handoff_completed"):
            return False
        if not extra.get("drop_handoff_isolated", True):
            return False
    return True


def _budget_ok(cells: list[dict]) -> bool:
    return bool(cells) and all((c.get("extra") or {}).get("budget_calls") == len(KINDS) for c in cells)


def _pattern(cells: list[dict], track: str) -> str:
    control = _full_rate(_valid(cells, track, "control"), track)
    intervention = _full_rate(_valid(cells, track, "intervention"), track)
    if control == 1.0 and intervention == 1.0:
        return "both_pass"
    if control == 1.0 and intervention == 0.0:
        return "drop_works"
    if control == 0.0 and intervention == 0.0:
        return "both_fail"
    return "mixed"


def _counts(cells: list[dict], track: str, variant: str) -> tuple[int, int]:
    subset = [
        c
        for c in cells
        if (c.get("extra") or {}).get("track") == track and (c.get("extra") or {}).get("variant") == variant
    ]
    return sum(int(c.get("full_pass") == 1) for c in subset), len(subset)


def _frac(cells: list[dict], track: str, variant: str) -> str:
    passed, n = _counts(cells, track, variant)
    return f"{passed}/{n}"


def _strict_frac(cells: list[dict], track: str) -> str:
    groups: dict[tuple, dict[str, dict]] = {}
    for cell in _valid(cells, track):
        extra = cell.get("extra") or {}
        key = (extra.get("task_id"), extra.get("repeat_id"), extra.get("track"))
        groups.setdefault(key, {})[str(extra.get("variant"))] = cell
    pairs = [g for g in groups.values() if "control" in g and "intervention" in g]
    if not pairs:
        return "0/0"
    n = sum(1 for g in pairs if g["control"].get("full_pass") == 1 and g["intervention"].get("full_pass") == 1)
    return f"{n}/{len(pairs)}"


def _cells_by_repeat(cells: list[dict]) -> dict[int, list[dict]]:
    grouped: dict[int, list[dict]] = {}
    for cell in cells:
        rid = int((cell.get("extra") or {}).get("repeat_id") or 0)
        grouped.setdefault(rid, []).append(cell)
    return grouped


def _ci(split: dict, track: str) -> str:
    d = (split or {}).get(track) or {}
    return f"{d.get('control')}/{d.get('intervention')}"


def _track_counts(cells: list[dict]) -> dict:
    return {
        "full_multi": {
            "control": _frac(cells, "multi", "control"),
            "interruption": _frac(cells, "multi", "intervention"),
            "strict_pair": _strict_frac(cells, "multi"),
        },
        "drop_checkpoint": {
            "control": _frac(cells, "drop_checkpoint", "control"),
            "interruption": _frac(cells, "drop_checkpoint", "intervention"),
        },
        "drop_handoff": {
            "control": _frac(cells, "drop_handoff", "control"),
            "interruption": _frac(cells, "drop_handoff", "intervention"),
        },
    }


def _drop_first_error_ok(cells: list[dict], track: str, expected: str) -> bool:
    subset = [
        c
        for c in cells
        if (c.get("extra") or {}).get("track") == track and (c.get("extra") or {}).get("variant") == "intervention"
    ]
    return bool(subset) and all((c.get("process_profile") or {}).get("first_error") == expected for c in subset)


def _env_repair(cells: list[dict]) -> int:
    return sum(1 for c in cells if not (c.get("extra") or {}).get("env_denied", True))


def _seed0_gate(cells: list[dict], coverage: float) -> str:
    if coverage < 1.0 or len(cells) < 18:
        return "A_r0"
    if not _budget_ok(cells) or not _isolation_ok(cells) or _env_repair(cells) != 0:
        return "A_r0"
    mc, mn = _counts(cells, "multi", "control")
    mi, min_ = _counts(cells, "multi", "intervention")
    dc, dn = _counts(cells, "drop_checkpoint", "control")
    di, din = _counts(cells, "drop_checkpoint", "intervention")
    hc, hn = _counts(cells, "drop_handoff", "control")
    hi, hin = _counts(cells, "drop_handoff", "intervention")
    if mn != 3 or min_ != 3 or dn != 3 or din != 3 or hn != 3 or hin != 3:
        return "A_r0"
    drop_ok = _drop_first_error_ok(cells, "drop_checkpoint", "checkpoint_not_delivered") and _drop_first_error_ok(
        cells, "drop_handoff", "handoff_not_delivered"
    )
    if mc == 3 and mi == 3 and dc == 3 and di == 0 and hc == 3 and hi == 0 and drop_ok:
        return "regression_pass"
    if mc < 3 or mi < 3:
        return "off_floor"
    if dc == 3 and di == 0 and hc == 3 and hi == 0:
        return "construct_open"
    if (dc == 3 and di == 0) != (hc == 3 and hi == 0):
        return "single_drop"
    if mc == 0 and mi == 0:
        return "C_floor"
    return "off_floor"


def _fiftyfour_gate(all_cells: list[dict]) -> str:
    grouped = _cells_by_repeat(all_cells)
    if sorted(grouped) != [0, 1, 2]:
        return "repeats_off_pattern"
    for slice_cells in grouped.values():
        if len(slice_cells) != 18:
            return "repeats_off_pattern"
        cov = summarize_workflow(WORKFLOW_ID, slice_cells)["coverage"]
        if _seed0_gate(slice_cells, cov) != "regression_pass":
            return "repeats_off_pattern"
    if summarize_workflow(WORKFLOW_ID, all_cells)["coverage"] != 1.0:
        return "repeats_off_pattern"
    return "development_regression_pass"


def _interpret(gate: str, *, direct_ok: bool, full: dict[str, float | None], phase: str = "") -> str:
    if not direct_ok:
        return "Direct 不可做。停止。Direct 不是正式系统结果。不解释 Multi，不能说中断恢复失败。"
    if phase == "direct":
        return "Direct 6/6 过门，非正式结果。本轮不开 Multi。不能解释为中断恢复已通过。"
    if gate == "A_r0":
        return "Coverage 或公平性未过，回到 R0。不解释能力。"
    if gate == "C_floor":
        return "Full Multi 与 Drop 共同地板。不能估计 Checkpoint 或 Handoff 的价值。不能说 L1 已经通过。"
    if gate == "C_ceiling":
        return "三轨都高：Drop 无效或任务不依赖检查点/接替交付。不补 54 格。"
    if gate == "regression_pass":
        return "seed0 满足回归门。允许补 repeat 1/2。54 格未完成前不能登记开发集闭环，不能写泛化通过或进入正式排名。"
    if gate == "development_regression_pass":
        return "54 格保持同一模式。开发集回归通过。不能写泛化通过或进入正式排名。"
    if gate == "repeats_off_pattern":
        return "seed0 过门后 repeat 未保持同一模式。停在 54 格诊断，按首错定位。不能登记开发集闭环。"
    if gate == "single_drop":
        return "只识别出一种 Drop 机制的因果价值。分别报告，不能笼统说中断恢复通过。"
    multi = full.get("multi")
    if multi == 1.0:
        return "R0 有效且 Full Multi 通过。仍是开发集 seed0，不能扩写成一般性长期连续性已通过。"
    return "R0 有效且 Full Multi 不在地板。按首错定位检查点、接替与恢复位置。不能提前说 L1 已经通过。"


def _split(cells: list[dict], field: str) -> dict[str, dict[str, float | None]]:
    return {
        track: {
            "control": _rate(_valid(cells, track, "control"), field),
            "intervention": _rate(_valid(cells, track, "intervention"), field),
        }
        for track in TRACKS
    }


def _metrics(cells: list[dict]) -> dict:
    full = {track: _full_rate(cells, track) for track in TRACKS}
    inter_multi = _valid(cells, "multi", "intervention")
    payload = {
        "Coverage": {track: _coverage_track(cells, track) for track in TRACKS},
        "checkpoint_created": _split(cells, "checkpoint_created"),
        "checkpoint_delivered_to_successor": _split(cells, "checkpoint_delivered_to_successor"),
        "checkpoint_content_correct": _split(cells, "checkpoint_content_correct"),
        "handoff_delivered": _split(cells, "handoff_delivered"),
        "handoff_adopted": _split(cells, "handoff_adopted"),
        "resume_step_correct": _split(cells, "resume_step_correct"),
        "completed_step_not_repeated": _split(cells, "completed_step_not_repeated"),
        "remaining_step_not_skipped": _split(cells, "remaining_step_not_skipped"),
        "target_correct": _split(cells, "target_correct"),
        "FullPass": full,
        "StrictPair": {track: _strict_pair(cells, track) for track in TRACKS},
        "RecoveryLatency": _mean(inter_multi, "recovery_latency"),
        "environment_auto_repair": _env_repair(cells),
        "first_error": dict(Counter((c.get("process_profile") or {}).get("first_error") for c in cells)),
    }
    return payload


def _claim(gate: str, interpretation: str, *, direct_ok: bool, phase: str = "") -> str:
    if not direct_ok:
        return "Direct 不可做。停止。不跑 Multi。"
    if phase == "direct":
        return "Direct 可做性门通过。非正式结果。本轮不开 Multi。中断恢复结果仍为 N/A。"
    if gate == "A_r0":
        return "Coverage 或公平性未过，回到 R0。不解释能力。"
    if gate == "C_floor":
        return "共同地板。不能估计 Checkpoint 或 Handoff 的价值。不能说 L1 已通过。"
    if gate == "C_ceiling":
        return "三轨都高：Drop 无效或任务不依赖交付。不补 54 格。"
    if gate == "regression_pass":
        return "seed0 回归门通过。允许补 repeat 1/2。不能写泛化或排名。"
    if gate == "development_regression_pass":
        return "54 格开发集回归通过。不能写泛化或排名。"
    if gate == "repeats_off_pattern":
        return "repeat 未保持 seed0 模式。不登记闭环。不能写泛化或排名。"
    if gate == "single_drop":
        return "只识别出一种机制。分别报告，不能笼统说中断恢复通过。不补 54 格。"
    return interpretation


def _pack(
    cells: list[dict],
    out: Path,
    *,
    phase: str,
    gate: str,
    freeze: dict,
    direct_ok: bool,
    direct_fullpass: float | None,
) -> None:
    coverage = summarize_workflow(WORKFLOW_ID, cells)["coverage"] if cells else None
    metrics = _metrics(cells) if cells else {}
    interpretation = _interpret(gate, direct_ok=direct_ok, full=(metrics.get("FullPass") or {}), phase=phase)
    counts = _track_counts(cells) if cells else {}
    closed = gate == "development_regression_pass"
    payload = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "experiment_id": EXPERIMENT_ID,
        "parent": "EXP-GM-L1-01b",
        "phase": phase,
        "gate": gate,
        "status": "direct_pass_multi_not_run" if phase == "direct" and direct_ok else gate,
        "measurement_result": "pass" if cells and coverage == 1.0 else "fail",
        "ranking_eligible": False,
        "holdout_allowed": False,
        "direct_ok": direct_ok,
        "direct_coverage": coverage if phase == "direct" else None,
        "direct_fullpass": direct_fullpass,
        "direct_strict_pair": _strict_pair(cells, "direct") if phase == "direct" and cells else None,
        "direct_is_formal_result": False,
        "primary_track": "multi",
        "coverage": coverage,
        "environment_auto_repair": (metrics.get("environment_auto_repair") if cells else None),
        "multi_agent_matrix_run": False if phase in {"rule", "direct"} else True,
        "full_multi": counts.get("full_multi"),
        "drop_checkpoint": counts.get("drop_checkpoint"),
        "drop_handoff": counts.get("drop_handoff"),
        "checkpoint_causal_dependency": (
            "replicated"
            if closed
            else ("observed_seed0" if gate in {"regression_pass", "repeats_off_pattern"} else None)
        ),
        "handoff_causal_dependency": (
            "replicated"
            if closed
            else ("observed_seed0" if gate in {"regression_pass", "repeats_off_pattern"} else None)
        ),
        "interruption_recovery_development_result": (
            "pass" if closed else ("pending_repeats" if gate == "regression_pass" else None)
        ),
        "resume_workflow_regression": "pass" if closed else "pending",
        "original_failure_status": (
            "resolved_on_development_regression" if closed else "mitigated_not_resolved"
        ),
        "interruption_recovery_result": "N/A" if phase in {"rule", "direct"} else ("development_pass" if closed else "pending"),
        "repeat_1_2_allowed": gate in {"regression_pass", "development_regression_pass", "repeats_off_pattern"},
        "repeat_1_2_run": phase == "repeats",
        "n_cells": len(cells),
        "c1_status": "development_partial_pass",
        "function_progress": "~85%",
        "function_progress_means": "evaluation_construction_and_mechanism_coverage",
        "does_not_overwrite": ["EXP-GM-L1-01", "EXP-GM-L1-01b", "CAL-GM-L1-RESUME-01", "EXP-GM-C1-01", "EXP-GM-C1-02", "EXP-GM-C1-03"],
        "claim": _claim(gate, interpretation, direct_ok=direct_ok, phase=phase),
        "interpretation": interpretation,
        "metrics": metrics,
        "model": MODEL,
        "temperature": TEMPERATURE,
        "freeze": freeze.get("base_commit"),
        "do_not": [
            "run_c1_04",
            "tune_c1_prompts",
            "create_c1_holdout",
            "overwrite_l1_01b_strict_pair",
            "claim_generalization",
            "enter_ranking",
        ],
    }
    (out / "GATE.yaml").write_text(yaml.safe_dump(payload, allow_unicode=True, sort_keys=False), encoding="utf-8")
    m = metrics
    full = m.get("FullPass") or {}
    lines = [
        f"# {EXPERIMENT_ID}",
        "",
        f"- 时间：{payload['generated_at']}",
        f"- phase：{phase}；gate：{gate}",
        "- 正式对象：Full Multi。Direct 非正式结果。不覆盖 C1。",
        "- ranking_eligible：false",
        f"- Direct 可做：{direct_ok}（FullPass={direct_fullpass}，仅校准）",
        f"- 冻结：{freeze.get('base_commit')}",
        f"- Coverage：{coverage}",
        "",
        "| 指标 control/intervention | Multi | DropCheckpoint | DropHandoff |",
        "|---|---|---|---|",
        f"| Coverage | {(m.get('Coverage') or {}).get('multi')} | {(m.get('Coverage') or {}).get('drop_checkpoint')} | {(m.get('Coverage') or {}).get('drop_handoff')} |",
        f"| checkpoint_created | {_ci(m.get('checkpoint_created') or {}, 'multi')} | {_ci(m.get('checkpoint_created') or {}, 'drop_checkpoint')} | {_ci(m.get('checkpoint_created') or {}, 'drop_handoff')} |",
        f"| checkpoint_delivered_to_successor | {_ci(m.get('checkpoint_delivered_to_successor') or {}, 'multi')} | {_ci(m.get('checkpoint_delivered_to_successor') or {}, 'drop_checkpoint')} | {_ci(m.get('checkpoint_delivered_to_successor') or {}, 'drop_handoff')} |",
        f"| checkpoint_content_correct | {_ci(m.get('checkpoint_content_correct') or {}, 'multi')} | {_ci(m.get('checkpoint_content_correct') or {}, 'drop_checkpoint')} | {_ci(m.get('checkpoint_content_correct') or {}, 'drop_handoff')} |",
        f"| handoff_delivered | {_ci(m.get('handoff_delivered') or {}, 'multi')} | {_ci(m.get('handoff_delivered') or {}, 'drop_checkpoint')} | {_ci(m.get('handoff_delivered') or {}, 'drop_handoff')} |",
        f"| handoff_adopted | {_ci(m.get('handoff_adopted') or {}, 'multi')} | {_ci(m.get('handoff_adopted') or {}, 'drop_checkpoint')} | {_ci(m.get('handoff_adopted') or {}, 'drop_handoff')} |",
        f"| resume_step_correct | {_ci(m.get('resume_step_correct') or {}, 'multi')} | {_ci(m.get('resume_step_correct') or {}, 'drop_checkpoint')} | {_ci(m.get('resume_step_correct') or {}, 'drop_handoff')} |",
        f"| completed_step_not_repeated | {_ci(m.get('completed_step_not_repeated') or {}, 'multi')} | {_ci(m.get('completed_step_not_repeated') or {}, 'drop_checkpoint')} | {_ci(m.get('completed_step_not_repeated') or {}, 'drop_handoff')} |",
        f"| remaining_step_not_skipped | {_ci(m.get('remaining_step_not_skipped') or {}, 'multi')} | {_ci(m.get('remaining_step_not_skipped') or {}, 'drop_checkpoint')} | {_ci(m.get('remaining_step_not_skipped') or {}, 'drop_handoff')} |",
        f"| target_correct | {_ci(m.get('target_correct') or {}, 'multi')} | {_ci(m.get('target_correct') or {}, 'drop_checkpoint')} | {_ci(m.get('target_correct') or {}, 'drop_handoff')} |",
        f"| FullPass | {full.get('multi')} | {full.get('drop_checkpoint')} | {full.get('drop_handoff')} |",
        f"| StrictPair | {(m.get('StrictPair') or {}).get('multi')} | {(m.get('StrictPair') or {}).get('drop_checkpoint')} | {(m.get('StrictPair') or {}).get('drop_handoff')} |",
        "",
        f"- Full Multi：control {(counts.get('full_multi') or {}).get('control')}；interruption {(counts.get('full_multi') or {}).get('interruption')}；strict_pair {(counts.get('full_multi') or {}).get('strict_pair')}",
        f"- Drop Checkpoint：control {(counts.get('drop_checkpoint') or {}).get('control')}；interruption {(counts.get('drop_checkpoint') or {}).get('interruption')}",
        f"- Drop Handoff：control {(counts.get('drop_handoff') or {}).get('control')}；interruption {(counts.get('drop_handoff') or {}).get('interruption')}",
        f"- RecoveryLatency（intervention multi）：{m.get('RecoveryLatency')}",
        f"- first_error：{m.get('first_error')}",
        f"- 解释：{interpretation}",
        "",
        f"**结论：** {_claim(gate, interpretation, direct_ok=direct_ok, phase=phase)} 功能进度约 85% 是评测建设与机制覆盖，不是 GAWorld 能力得分。不做 C1-04。",
        "",
    ]
    if gate == "development_regression_pass":
        lines += [
            "```yaml",
            "interruption_recovery_development_result: pass",
            "checkpoint_causal_dependency: replicated",
            "handoff_causal_dependency: replicated",
            "resume_workflow_regression: pass",
            "original_failure_status: resolved_on_development_regression",
            "ranking_eligible: false",
            "l1_01b_strict_pair_unchanged: 2_of_3",
            "```",
            "",
        ]
    if cells:
        lines += ["| instance | valid | FullPass | track | first_error |", "|---|---|---|---|---|"]
        for cell in cells:
            extra = cell.get("extra") or {}
            err = (cell.get("process_profile") or {}).get("first_error")
            lines.append(
                f"| {cell.get('instance_id')} | {cell.get('measurement_valid')} | {cell.get('full_pass')} | {extra.get('track')} | {err} |"
            )
        lines.append("")
    (out / "REPORT.md").write_text("\n".join(lines), encoding="utf-8")
    (out / "cell_table.json").write_text(json.dumps({"cells": cells, "gate": payload}, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    if phase == "seed0":
        (out / "seed0_cells.json").write_text(
            json.dumps({"cells": cells, "gate": payload}, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        (out / "GATE.seed0.yaml").write_text(yaml.safe_dump(payload, allow_unicode=True, sort_keys=False), encoding="utf-8")
        (out / "REPORT.seed0.md").write_text((out / "REPORT.md").read_text(encoding="utf-8"), encoding="utf-8")


def _score_and_store(*, task, variant, track, repeat_id, loop, out_dir) -> dict:
    instance_id = f"{task['id']}_{variant}_{track}_r{repeat_id}"
    cell = score_cell(
        task=task,
        variant=variant,
        track=track,
        repeat_id=repeat_id,
        loop=loop,
        workflow_id=WORKFLOW_ID,
        instance_id=instance_id,
    )
    run_dir = out_dir / "runs" / instance_id
    run_dir.mkdir(parents=True, exist_ok=True)
    (run_dir / "cell_result.json").write_text(json.dumps(cell, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    extra = cell.get("extra") or {}
    print(
        f"done {instance_id} valid={cell.get('measurement_valid')} full_pass={cell.get('full_pass')} first_error={extra.get('first_error')}",
        flush=True,
    )
    return cell


def _fns(task: dict, variant: str, mode: str):
    successor = "worker_b" if variant == "intervention" else "worker_a"

    def step1(_p):
        if mode != "rule":
            return _llm(_p)
        return json.dumps(rule_step(task, "worker_a", task["step_ids"][0]), ensure_ascii=False)

    def checkpoint(_p):
        if mode != "rule":
            return _llm(_p)
        first = task["step_ids"][0]
        return json.dumps(rule_checkpoint(task, "worker_a", [first], {first: solve_outputs(task)[first]}), ensure_ascii=False)

    def handoff(_p):
        if mode != "rule":
            return _llm(_p)
        return json.dumps(rule_handoff(task, variant, {"completed_steps": [task["step_ids"][0]]}), ensure_ascii=False)

    def resume(_p):
        if mode != "rule":
            return _llm(_p)
        ck = {"checkpoint_version": "ckpt-001", "completed_steps": [task["step_ids"][0]]}
        ho = {"successor": successor, "checkpoint_version": "ckpt-001", "resume_step": task["step_ids"][1]}
        return json.dumps(rule_resume(task, successor, ck, ho), ensure_ascii=False)

    def step2(_p):
        if mode != "rule":
            return _llm(_p)
        prior = {task["step_ids"][0]: solve_outputs(task)[task["step_ids"][0]]}
        return json.dumps(rule_step(task, successor, task["step_ids"][1], prior), ensure_ascii=False)

    def step3(_p):
        if mode != "rule":
            return _llm(_p)
        outputs = solve_outputs(task)
        prior = {task["step_ids"][0]: outputs[task["step_ids"][0]], task["step_ids"][1]: outputs[task["step_ids"][1]]}
        return json.dumps(rule_step(task, successor, task["step_ids"][2], prior), ensure_ascii=False)

    return step1, checkpoint, handoff, resume, step2, step3


def run_direct_cells(out: Path, *, mode: str) -> list[dict]:
    cells = []
    for task in load_tasks():
        for variant in VARIANTS:
            instance_id = f"{task['id']}_{variant}_direct_r0"
            print(f"run {instance_id} mode={mode}", flush=True)
            generate = (lambda _p, t=task, v=variant: json.dumps(rule_direct(t, v), ensure_ascii=False)) if mode == "rule" else _llm
            loop = run_direct(task=task, variant=variant, out_dir=out / "runs" / instance_id, generate_fn=generate)
            cells.append(_score_and_store(task=task, variant=variant, track="direct", repeat_id=0, loop=loop, out_dir=out))
    return cells


def run_repeat(out: Path, repeat_id: int, *, mode: str) -> list[dict]:
    cells = []
    for task in load_tasks():
        for variant in VARIANTS:
            for track in TRACKS:
                instance_id = f"{task['id']}_{variant}_{track}_r{repeat_id}"
                print(f"run {instance_id} mode={mode}", flush=True)
                step1, checkpoint, handoff, resume, step2, step3 = _fns(task, variant, mode)
                loop = run_cell(
                    task=task,
                    variant=variant,
                    track=track,
                    out_dir=out / "runs" / instance_id,
                    step1_fn=step1,
                    checkpoint_fn=checkpoint,
                    handoff_fn=handoff,
                    resume_fn=resume,
                    step2_fn=step2,
                    step3_fn=step3,
                )
                cells.append(_score_and_store(task=task, variant=variant, track=track, repeat_id=repeat_id, loop=loop, out_dir=out))
    return cells


def _run_repeats(freeze: dict) -> int:
    seed_path = OUT / "seed0_cells.json"
    table_path = OUT / "cell_table.json"
    src = seed_path if seed_path.is_file() else table_path
    if not src.is_file():
        print("缺少 seed0 结果。先跑 --phase seed0。", flush=True)
        return 1
    seed0 = json.loads(src.read_text(encoding="utf-8")).get("cells") or []
    coverage = summarize_workflow(WORKFLOW_ID, seed0)["coverage"]
    seed_gate = _seed0_gate(seed0, coverage)
    if seed_gate != "regression_pass" or len(seed0) != 18:
        print(f"seed0 未过门 gate={seed_gate} n={len(seed0)}。不补 repeat 1/2。", flush=True)
        return 1
    if not seed_path.is_file():
        (OUT / "seed0_cells.json").write_text(
            json.dumps({"cells": seed0}, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
    cached = json.loads((OUT / "direct_cells.json").read_text(encoding="utf-8")) if (OUT / "direct_cells.json").is_file() else {}
    direct_full = cached.get("fullpass")
    print("phase=repeats seed0=regression_pass", flush=True)
    r1 = run_repeat(OUT, 1, mode="llm")
    r2 = run_repeat(OUT, 2, mode="llm")
    all_cells = seed0 + r1 + r2
    gate = _fiftyfour_gate(all_cells)
    _pack(all_cells, OUT, phase="repeats", gate=gate, freeze=freeze, direct_ok=True, direct_fullpass=direct_full)
    print((OUT / "REPORT.md").read_text(encoding="utf-8"))
    print(f"gate={gate} n_cells={len(all_cells)}", flush=True)
    if gate != "development_regression_pass":
        print("54 格未保持同一模式。按首错定位。不登记闭环。", flush=True)
        return 1
    print("54 格保持同一模式。开发集回归通过。不能写泛化或排名。", flush=True)
    return 0


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--phase", choices=("rule", "direct", "seed0", "repeats"), default="seed0")
    args = parser.parse_args()
    ensure_import_paths()
    os.chdir(GAWORLD_ROOT)
    print("phase=rule", flush=True)
    if rule_main() != 0:
        return 1
    from exp_gm_l1_01c.fairness import preflight

    check = preflight()
    print("fairness_preflight", json.dumps({"ok": check["ok"], "n_leaks": len(check["leaks"])}, ensure_ascii=False), flush=True)
    if not check["ok"]:
        print("fairness preflight failed", check["leaks"], flush=True)
        return 1
    OUT.mkdir(parents=True, exist_ok=True)
    freeze = _load_freeze()
    if args.phase == "rule":
        _pack([], OUT, phase="rule", gate="rule_pass", freeze=freeze, direct_ok=False, direct_fullpass=None)
        print("Rule 已过门并冻结。下一步 Direct 6 格。", flush=True)
        return 0
    if args.phase == "repeats":
        return _run_repeats(freeze)
    cached = OUT / "direct_cells.json"
    reuse_direct = False
    if args.phase == "seed0" and cached.is_file():
        cached_payload = json.loads(cached.read_text(encoding="utf-8"))
        reuse_direct = bool(cached_payload.get("ok")) and len(cached_payload.get("cells") or []) == 6
    if reuse_direct:
        print("reuse Direct 6/6, skip re-run", flush=True)
        direct_cells = list(cached_payload["cells"])
        direct_full = cached_payload.get("fullpass")
        direct_cov = cached_payload.get("coverage")
        direct_pair = cached_payload.get("strict_pair")
        direct_ok = True
    else:
        print("phase=direct", flush=True)
        direct_cells = run_direct_cells(OUT, mode="llm")
        direct_full = _full_rate(direct_cells, "direct")
        direct_cov = summarize_workflow(WORKFLOW_ID, direct_cells)["coverage"]
        direct_pair = _strict_pair(direct_cells, "direct")
        direct_ok = direct_cov == 1.0 and len(direct_cells) == 6 and direct_full == 1.0 and direct_pair == 1.0
        (OUT / "direct_cells.json").write_text(
            json.dumps(
                {
                    "ok": direct_ok,
                    "fullpass": direct_full,
                    "coverage": direct_cov,
                    "strict_pair": direct_pair,
                    "cells": direct_cells,
                },
                ensure_ascii=False,
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )
    print(f"direct_ok={direct_ok} direct_fullpass={direct_full} coverage={direct_cov} strict_pair={direct_pair} (not formal)", flush=True)
    if not direct_ok:
        _pack(direct_cells, OUT, phase="direct", gate="direct_fail", freeze=freeze, direct_ok=False, direct_fullpass=direct_full)
        print("Direct 未过。停止。不跑 Multi。不能说中断恢复失败，只能说新题 Direct 不可做。", flush=True)
        return 1
    if args.phase == "direct":
        _pack(direct_cells, OUT, phase="direct", gate="direct_pass", freeze=freeze, direct_ok=True, direct_fullpass=direct_full)
        print("Direct 已过。seed0 用 --phase seed0。", flush=True)
        return 0
    print("phase=seed0", flush=True)
    cells = run_repeat(OUT, 0, mode="llm")
    coverage = summarize_workflow(WORKFLOW_ID, cells)["coverage"]
    gate = _seed0_gate(cells, coverage)
    _pack(cells, OUT, phase="seed0", gate=gate, freeze=freeze, direct_ok=True, direct_fullpass=direct_full)
    print((OUT / "REPORT.md").read_text(encoding="utf-8"))
    if gate == "A_r0":
        print("gate=A_r0，停止。不补 repeat 1/2。", flush=True)
        return 1
    if gate == "C_floor":
        print("gate=C_floor。seed0 测量有效但处于共同地板。不补 54 格。", flush=True)
        return 0
    if gate == "regression_pass":
        print("gate=regression_pass。seed0 完成。允许 --phase repeats。", flush=True)
        return 0
    print(f"gate={gate}。seed0 完成。不补 repeat 1/2。", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
