#!/usr/bin/env python3
"""EXP-GM-T3-03 discrimination. Direct doability, then seed0. Repeats only if off floor and ceiling."""

from __future__ import annotations

import argparse
import json
import os
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path

from exp_gm_t3_01.budget import MODEL, PROVIDER, TEMPERATURE
from exp_gm_t3_02.contract import parse_json_object
from exp_gm_t3_03.freeze import write_manifest
from exp_gm_t3_03.loader import TRACKS, VARIANTS, load_tasks
from exp_gm_t3_03.loop import generate_shared_draft, run_track_from_draft
from exp_gm_t3_03.prompts import reviewer_prompt, rule_builder_draft, rule_executor, rule_review, strip_source
from exp_gm_t3_03.rule_tests import main as rule_main
from exp_gm_t3_03.scorer import score_cell
from v0_first_batch.paths import BRIDGE_ROOT, GAWORLD_ROOT, ensure_import_paths
from v0_first_batch.schema import summarize_workflow

WORKFLOW_ID = "exp_gm_t3_03_discrimination"
PRIVATE_VISIBLE = {"direct": True, "single": False, "multi": True, "drop": True}


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


def _draft_hash_ok(cells: list[dict]) -> bool:
    hashes: dict[tuple, set[str]] = defaultdict(set)
    for cell in cells:
        extra = cell.get("extra") or {}
        key = (extra.get("task_id"), extra.get("variant"), extra.get("repeat_id"))
        hashes[key].add(str(extra.get("shared_draft_sha256") or ""))
    return bool(hashes) and all(len(values) == 1 and "" not in values for values in hashes.values())


def _budget_ok(cells: list[dict]) -> bool:
    return bool(cells) and all((c.get("extra") or {}).get("budget_calls") == 3 for c in cells) and all(
        list((c.get("extra") or {}).get("budget_kinds") or []) == ["builder_draft", "review", "builder_final"] for c in cells
    )


def _isolation_ok(cells: list[dict]) -> bool:
    drops = [c for c in cells if (c.get("extra") or {}).get("track") == "drop"]
    if not drops:
        return False
    for cell in drops:
        extra = cell.get("extra") or {}
        if not extra.get("reviewer_ran") or extra.get("executor_saw_review") or extra.get("drop_inbox_empty") is False:
            return False
    return True


def _payload_ok(cells: list[dict]) -> bool:
    for cell in cells:
        extra = cell.get("extra") or {}
        if extra.get("track") in {"single", "multi", "direct"} and not extra.get("payload_integrity"):
            return False
        if extra.get("track") == "drop" and not extra.get("payload_integrity"):
            return False
    return bool(cells)


def _split_drop(cells: list[dict], field: str) -> dict[str, float | None]:
    return {
        "control": _mean(_valid(cells, "drop", "control"), field),
        "intervention": _mean(_valid(cells, "drop", "intervention"), field),
        "pooled_average": _mean(_valid(cells, "drop"), field),
    }


def _first_errors(cells: list[dict], track: str | None = None, variant: str | None = None) -> dict:
    subset = cells
    if track is not None or variant is not None:
        subset = []
        for cell in cells:
            extra = cell.get("extra") or {}
            if track is not None and extra.get("track") != track:
                continue
            if variant is not None and extra.get("variant") != variant:
                continue
            subset.append(cell)
    return dict(Counter((c.get("process_profile") or {}).get("first_error") for c in subset))


def _seed0_gate(cells: list[dict], coverage: float) -> str:
    if coverage < 1.0 or len(cells) < 18:
        return "A_r0"
    if not _draft_hash_ok(cells) or not _budget_ok(cells) or not _isolation_ok(cells) or not _payload_ok(cells):
        return "A_r0"
    single = _full_rate(cells, "single")
    multi = _full_rate(cells, "multi")
    if single == 0.0 and multi == 0.0:
        return "C_floor"
    if single == 1.0 and multi == 1.0:
        return "C_ceiling"
    return "off_floor"


def _value_pattern(cells: list[dict]) -> dict[str, Any]:
    single = _full_rate(cells, "single")
    multi = _full_rate(cells, "multi")
    drop = _full_rate(cells, "drop")
    single_int = _first_errors(cells, "single", "intervention")
    drop_int = _first_errors(cells, "drop", "intervention")
    locates = bool(single_int.get("review_decision_incorrect")) and set(single_int) <= {"review_decision_incorrect"}
    drop_locates = bool(drop_int.get("review_payload_not_delivered")) and set(drop_int) <= {
        "review_payload_not_delivered"
    }
    better = (
        multi is not None
        and single is not None
        and drop is not None
        and multi > single
        and multi > drop
    )
    return {
        "multi_gt_single": bool(multi is not None and single is not None and multi > single),
        "multi_gt_drop": bool(multi is not None and drop is not None and multi > drop),
        "pattern": better,
        "single_intervention_first_error": single_int,
        "drop_intervention_first_error": drop_int,
        "first_error_locates_to_reviewer_private_info": locates and better,
        "advantage_vanishes_on_drop": drop_locates and better,
        "estimable": better and locates and drop_locates,
    }


def _claim(gate: str, metrics: dict, *, direct_ok: bool, phase: str) -> str:
    if not direct_ok:
        return "新题 Direct 不可做。停止。不解释 Multi vs Single。"
    if gate == "A_r0":
        return "Coverage 或公平性未过，回到 R0，不解释能力。不补重复。"
    pattern = metrics.get("value_pattern") or {}
    if gate == "C_floor":
        return "Single 与 Multi 共地板。不能解释成多 Agent 无价值。不补重复。"
    if gate == "C_ceiling":
        return "Single 与 Multi 共天花板。无私有信息区分度。不补重复。不能报告多智能体审核价值。"
    if pattern.get("estimable"):
        if phase == "seed0":
            return "R0 有效且不共地板、不共天花板；方向符合 Multi>Single 且 Multi>Drop，首错指向 Reviewer 私有信息。补 repeat 1/2 后再报告。"
        return "出现 Multi>Single 且 Multi>Drop，且首错定位到 Reviewer 提供的信息；丢弃后优势消失。仍不能作为排名分，也不能宣称泛化。"
    if pattern.get("pattern"):
        return "FullPass 方向是 Multi>Single 且 Multi>Drop，但首错不能定位到 Reviewer 私有信息。不能报告多智能体审核价值。"
    return "未同时出现 Multi>Single 且 Multi>Drop。T3-02 只证明集成已修好，本实验尚不能证明多 Agent 更好。"


def _metrics(cells: list[dict]) -> dict:
    full = {track: _full_rate(cells, track) for track in TRACKS}
    outcome = None if full["multi"] is None or full["single"] is None else round(full["multi"] - full["single"], 4)
    review_delivery = None if full["multi"] is None or full["drop"] is None else round(full["multi"] - full["drop"], 4)
    floor = full["single"] == 0.0 and full["multi"] == 0.0
    ceiling = full["single"] == 1.0 and full["multi"] == 1.0
    pattern = _value_pattern(cells)
    return {
        "Coverage": {track: _coverage_track(cells, track) for track in TRACKS},
        "ReviewDecisionAccuracy": {track: _mean(_valid(cells, track), "review_decision_correct") for track in TRACKS},
        "PayloadIntegrityWhenTransmitted": {
            "single": _mean(_valid(cells, "single"), "payload_integrity"),
            "multi": _mean(_valid(cells, "multi"), "payload_integrity"),
            "note": "有传输时完整性。Drop 干预没有交付，不能读成成功传输。",
        },
        "DropPayloadIsolation": _mean(_valid(cells, "drop"), "payload_integrity"),
        "CompleteChangeAdoptionRate": {
            "single": _mean(_valid(cells, "single"), "complete"),
            "multi": _mean(_valid(cells, "multi"), "complete"),
            "drop": _split_drop(cells, "complete"),
        },
        "TargetCorrect": {
            "single": _mean(_valid(cells, "single"), "target_correct"),
            "multi": _mean(_valid(cells, "multi"), "target_correct"),
            "drop": _split_drop(cells, "target_correct"),
        },
        "FullPass": full,
        "StrictPair": {track: _strict_pair(cells, track) for track in TRACKS},
        "OutcomeMultiAgentNetBenefit": {
            "value": None if floor or ceiling else outcome,
            "reason": "common_workflow_floor" if floor else ("multi_equals_single_ceiling" if ceiling else "multi_minus_single"),
        },
        "ReviewDeliveryValue": {
            "value": None if floor else review_delivery,
            "reason": "common_workflow_floor" if floor else "multi_minus_drop",
            "drop_complete_not_partial_adoption": True,
        },
        "first_error": dict(Counter((c.get("process_profile") or {}).get("first_error") for c in cells)),
        "first_error_single_intervention": _first_errors(cells, "single", "intervention"),
        "first_error_drop_intervention": _first_errors(cells, "drop", "intervention"),
        "value_pattern": pattern,
    }


def _report_lines(payload: dict) -> list[str]:
    fair = payload["fairness"]
    m = payload["metrics"]
    drop_complete = m["CompleteChangeAdoptionRate"]["drop"]
    drop_target = m["TargetCorrect"]["drop"]
    freeze = payload.get("freeze") or {}
    return [
        "# EXP-GM-T3-03",
        "",
        f"- 时间：{payload['generated_at']}",
        f"- phase：{payload['phase']}；gate：{payload.get('gate')}",
        "- ranking_eligible：false",
        "- generalization_claim：false",
        f"- multi_agent_value_estimable：{payload.get('multi_agent_value_estimable')}",
        "- parent：EXP-GM-T3-02；construct：independent_reviewer_private_information",
        f"- Direct 可做：{payload.get('direct_ok')}",
        f"- 冻结：{freeze.get('base_commit')}",
        "",
        "## 测量门",
        "",
        f"- Coverage：{fair['coverage']}",
        f"- 初稿哈希一致：{fair['draft_hash_ok']}",
        f"- 预算均为 3 次：{fair['budget_ok']}",
        f"- Drop 隔离：{fair['isolation_ok']}",
        f"- 有传输时 payload 完整性：{fair['payload_integrity_ok']}",
        "",
        "## 主报",
        "",
        "| 指标 | Single | Multi | Drop |",
        "|---|---:|---:|---:|",
        f"| Coverage | {m['Coverage']['single']} | {m['Coverage']['multi']} | {m['Coverage']['drop']} |",
        f"| ReviewDecisionAccuracy | {m['ReviewDecisionAccuracy']['single']} | {m['ReviewDecisionAccuracy']['multi']} | {m['ReviewDecisionAccuracy']['drop']} |",
        f"| PayloadIntegrity（有传输时） | {m['PayloadIntegrityWhenTransmitted']['single']} | {m['PayloadIntegrityWhenTransmitted']['multi']} | 不适用（干预未交付） |",
        f"| CompleteChangeAdoptionRate | {m['CompleteChangeAdoptionRate']['single']} | {m['CompleteChangeAdoptionRate']['multi']} | control {drop_complete['control']} / intervention {drop_complete['intervention']} |",
        f"| TargetCorrect | {m['TargetCorrect']['single']} | {m['TargetCorrect']['multi']} | control {drop_target['control']} / intervention {drop_target['intervention']} |",
        f"| FullPass | {m['FullPass']['single']} | {m['FullPass']['multi']} | {m['FullPass']['drop']} |",
        f"| StrictPair | {m['StrictPair']['single']} | {m['StrictPair']['multi']} | {m['StrictPair']['drop']} |",
        "",
        "Drop 的 pooled 平均若出现 0.5，是 control 与 intervention 两种变体的平均，不表示部分采用。",
        "",
        f"- Direct FullPass：{payload.get('direct_fullpass')}",
        f"- OutcomeMultiAgentNetBenefit：{m['OutcomeMultiAgentNetBenefit']}",
        f"- ReviewDeliveryValue：{m['ReviewDeliveryValue']}",
        f"- first_error：{m['first_error']}",
        f"- Single intervention first_error：{m['first_error_single_intervention']}",
        f"- Drop intervention first_error：{m['first_error_drop_intervention']}",
        f"- value_pattern：{m['value_pattern']}",
        "",
        f"**结论：** {payload['claim']}",
        "",
        "| instance | valid | FullPass | track | first_error |",
        "|---|---|---|---|---|",
    ]


def _pack(cells: list[dict], out: Path, *, phase: str, gate: str | None, freeze: dict | None, direct_ok: bool, direct_fullpass: float | None) -> dict:
    summary = summarize_workflow(WORKFLOW_ID, cells)
    summary["ranking_eligible"] = False
    metrics = _metrics(cells)
    pattern = metrics["value_pattern"]
    estimable = bool(direct_ok and gate not in {"A_r0", "C_floor", "C_ceiling"} and pattern.get("estimable") and phase != "seed0")
    payload = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "experiment_id": "EXP-GM-T3-03",
        "parent": "EXP-GM-T3-02",
        "phase": phase,
        "gate": gate,
        "ranking_eligible": False,
        "generalization_claim": False,
        "multi_agent_value_estimable": estimable,
        "direct_ok": direct_ok,
        "direct_fullpass": direct_fullpass,
        "claim": _claim(gate or "", metrics, direct_ok=direct_ok, phase=phase),
        "freeze": freeze,
        "summary": summary,
        "fairness": {
            "coverage": summary["coverage"],
            "draft_hash_ok": _draft_hash_ok(cells),
            "budget_ok": _budget_ok(cells),
            "isolation_ok": _isolation_ok(cells),
            "payload_integrity_ok": _payload_ok(cells),
            "single_full": _full_rate(cells, "single"),
            "multi_full": _full_rate(cells, "multi"),
            "drop_full": _full_rate(cells, "drop"),
        },
        "metrics": metrics,
        "model": MODEL,
        "temperature": TEMPERATURE,
        "note": "区分度实验。不能使用 T3-01/T3-02 开发题。不覆盖历史分数。",
    }
    (out / "cell_table.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    lines = _report_lines(payload)
    for cell in summary["cells"]:
        extra = cell.get("extra") or {}
        lines.append(
            f"| {cell.get('instance_id')} | {cell.get('measurement_valid')} | {cell.get('full_pass')} | "
            f"{extra.get('track')} | {(cell.get('process_profile') or {}).get('first_error')} |"
        )
    (out / "REPORT.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    if phase == "seed0":
        (out / "REPORT_seed0.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
        (out / "cell_table_seed0.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return payload


def _run_cells(out: Path, repeat_id: int, *, mode: str, tracks: tuple[str, ...], shared_root: str) -> list[dict]:
    cells: list[dict] = []
    for task in load_tasks():
        for variant in VARIANTS:
            shared_dir = out / shared_root / f"{task['id']}_{variant}_r{repeat_id}"
            generate_fn = (lambda _p, t=task: rule_builder_draft(t)) if mode == "rule" else (lambda prompt: strip_source(_llm(prompt)))
            shared = generate_shared_draft(task=task, variant=variant, repeat_id=repeat_id, out_dir=shared_dir, generate_fn=generate_fn)
            for track in tracks:
                instance_id = f"{task['id']}_{variant}_{track}_r{repeat_id}"
                print(f"run {instance_id} mode={mode}", flush=True)
                log: list[dict] = []
                private_visible = PRIVATE_VISIBLE[track]

                def reviewer_fn(draft: str, t=task, v=variant, tr=track, vis=private_visible, lg=log):
                    prompt = reviewer_prompt(t, v, draft, private_visible=vis, self_check=tr in {"single", "direct"})
                    if mode == "rule":
                        parsed = rule_review(t, v, draft, private_visible=vis)
                        raw = json.dumps(parsed, ensure_ascii=False)
                    else:
                        raw = _llm(prompt)
                        parsed = parse_json_object(raw) or {}
                    lg.append({"stage": "review", "prompt": prompt, "raw_text": raw, "parsed": parsed})
                    return parsed

                def revise_fn(prompt: str, review, t=task, lg=log):
                    from exp_gm_t3_03.rule_tests import _draft_from_prompt

                    if mode == "rule":
                        text = rule_executor(t, _draft_from_prompt(prompt, t), review)
                    else:
                        text = _llm(prompt)
                    lg.append({"stage": "builder_final", "prompt": prompt, "had_review": review is not None, "raw_text": text})
                    return text

                loop = run_track_from_draft(
                    task=task,
                    variant=variant,
                    track=track,
                    task_id=instance_id,
                    out_dir=out / "runs" / instance_id,
                    shared=shared,
                    revise_fn=revise_fn,
                    reviewer_fn=reviewer_fn,
                    drop=track == "drop",
                )
                review_p = next((e["prompt"] for e in log if e.get("stage") == "review"), "")
                final_p = next((e["prompt"] for e in log if e.get("stage") == "builder_final"), loop.get("final_prompt") or "")
                loop["review_prompt"] = review_p
                loop["final_prompt"] = final_p
                parent = Path(loop["final_path"]).parent
                (parent / "first_prompt.txt").write_text(str(loop.get("first_prompt") or ""), encoding="utf-8")
                (parent / "review_prompt.txt").write_text(review_p, encoding="utf-8")
                (parent / "final_prompt.txt").write_text(final_p, encoding="utf-8")
                review_raw = next((e.get("raw_text") for e in log if e.get("stage") == "review"), "")
                (parent / "review_raw.txt").write_text(str(review_raw or ""), encoding="utf-8")
                cell = score_cell(
                    task=task, variant=variant, track=track, repeat_id=repeat_id,
                    loop=loop, workflow_id=WORKFLOW_ID, instance_id=instance_id,
                    private_visible=private_visible,
                )
                extra = dict(cell.get("extra") or {})
                extra["mode"] = mode
                extra["model_version"] = "rule" if mode == "rule" else MODEL
                extra["draft_prompt_sha"] = shared.get("draft_prompt_sha256")
                cell["extra"] = extra
                cell["ranking_eligible"] = False
                (parent / "cell_result.json").write_text(json.dumps(cell, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
                cells.append(cell)
                print(
                    f"  valid={cell.get('measurement_valid')} full_pass={cell.get('full_pass')} "
                    f"first_error={(cell.get('process_profile') or {}).get('first_error')}",
                    flush=True,
                )
    return cells


def _write_gate(out: Path, payload: dict) -> None:
    import yaml

    drop_complete = payload["metrics"]["CompleteChangeAdoptionRate"]["drop"]
    body = {
        "experiment_id": "EXP-GM-T3-03",
        "parent": "EXP-GM-T3-02",
        "status": payload.get("phase"),
        "role": "multi_vs_single_discrimination",
        "ranking_eligible": False,
        "generalization_claim": False,
        "multi_agent_value_estimable": payload.get("multi_agent_value_estimable"),
        "gate": payload.get("gate"),
        "direct_ok": payload.get("direct_ok"),
        "direct_fullpass": payload.get("direct_fullpass"),
        "coverage": payload["fairness"]["coverage"],
        "single_fullpass": payload["fairness"]["single_full"],
        "multi_fullpass": payload["fairness"]["multi_full"],
        "drop_fullpass": payload["fairness"]["drop_full"],
        "drop_complete_change_adoption": drop_complete,
        "value_pattern": payload["metrics"]["value_pattern"],
        "claim": payload.get("claim"),
    }
    (out / "GATE.yaml").write_text(yaml.safe_dump(body, allow_unicode=True, sort_keys=False), encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--phase", choices=("rule", "direct", "seed0"), default="seed0")
    args = parser.parse_args()
    ensure_import_paths()
    os.chdir(GAWORLD_ROOT)
    print("phase=rule", flush=True)
    if rule_main() != 0:
        return 1
    if args.phase == "rule":
        print("Rule 已过门。下一步 Direct，再用 --phase seed0。", flush=True)
        return 0
    from exp_gm_t3_03.fairness import preflight

    out = BRIDGE_ROOT / "output" / "exp_gm_t3_03_20260825"
    out.mkdir(parents=True, exist_ok=True)
    check = preflight()
    print("fairness_preflight", json.dumps({k: v for k, v in check.items() if k not in {"v2_leaks_helper", "sha256_text"}}, ensure_ascii=False), flush=True)
    if not check["ok"]:
        print("fairness preflight failed; not freezing, not calling the model.", flush=True)
        return 1
    freeze = write_manifest(out)
    print("frozen", json.dumps({k: v for k, v in freeze.items() if k != "fairness_preflight"}, ensure_ascii=False), flush=True)
    print("phase=direct", flush=True)
    direct_cells = _run_cells(out, 0, mode="llm", tracks=("direct",), shared_root="direct_drafts")
    direct_summary = summarize_workflow(WORKFLOW_ID, direct_cells)
    direct_full = _full_rate(direct_cells, "direct")
    direct_ok = (
        direct_summary["coverage"] == 1.0
        and len(direct_cells) == 6
        and _budget_ok(direct_cells)
        and _payload_ok(direct_cells)
        and direct_full == 1.0
    )
    (out / "direct_cells.json").write_text(json.dumps({"ok": direct_ok, "fullpass": direct_full, "cells": direct_cells}, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"direct_ok={direct_ok} direct_fullpass={direct_full}", flush=True)
    if not direct_ok:
        _pack(direct_cells, out, phase="direct", gate="direct_fail", freeze=freeze, direct_ok=False, direct_fullpass=direct_full)
        print("Direct 未过。停止。不跑 Single/Multi/Drop，不解释多智能体价值。", flush=True)
        return 1
    if args.phase == "direct":
        print("Direct 已过。seed0 用 --phase seed0。", flush=True)
        return 0
    print("phase=seed0", flush=True)
    cells = _run_cells(out, 0, mode="llm", tracks=TRACKS, shared_root="shared_drafts")
    coverage = summarize_workflow(WORKFLOW_ID, cells)["coverage"]
    gate = _seed0_gate(cells, coverage)
    payload = _pack(cells, out, phase="seed0", gate=gate, freeze=freeze, direct_ok=True, direct_fullpass=direct_full)
    _write_gate(out, payload)
    print((out / "REPORT.md").read_text(encoding="utf-8"))
    if gate == "A_r0":
        print("gate=A_r0，停止。不补重复。", flush=True)
        return 1
    if gate in {"C_floor", "C_ceiling"}:
        print(f"gate={gate}，不补 repeat 1/2。不能报告多智能体审核价值。", flush=True)
        return 0
    print("gate=off_floor。补 repeat 1/2。", flush=True)
    for repeat_id in (1, 2):
        cells.extend(_run_cells(out, repeat_id, mode="llm", tracks=TRACKS, shared_root="shared_drafts"))
    coverage = summarize_workflow(WORKFLOW_ID, cells)["coverage"]
    gate = _seed0_gate(cells, coverage) if len(cells) >= 18 else "A_r0"
    if coverage == 1.0 and _draft_hash_ok(cells) and _budget_ok(cells) and _isolation_ok(cells) and _payload_ok(cells):
        single = _full_rate(cells, "single")
        multi = _full_rate(cells, "multi")
        if single == 0.0 and multi == 0.0:
            gate = "C_floor"
        elif single == 1.0 and multi == 1.0:
            gate = "C_ceiling"
        else:
            gate = "off_floor"
    payload = _pack(cells, out, phase="r0r1r2", gate=gate, freeze=freeze, direct_ok=True, direct_fullpass=direct_full)
    _write_gate(out, payload)
    print((out / "REPORT.md").read_text(encoding="utf-8"))
    print("repeat 0/1/2 完成。不建留出，不开 C1，不覆盖 T3-01/T3-02。", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
