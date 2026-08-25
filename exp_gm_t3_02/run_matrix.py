#!/usr/bin/env python3
"""EXP-GM-T3-02 integration regression. Repeat 0 only. Does not overwrite T3-01."""

from __future__ import annotations

import argparse
import json
import os
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path

from exp_gm_t3_01.budget import MODEL, PROVIDER, TEMPERATURE
from exp_gm_t3_01.fairness import sha256_text
from exp_gm_t3_01.loader import TRACKS, VARIANTS, load_tasks
from exp_gm_t3_02.contract import parse_json_object
from exp_gm_t3_02.freeze import write_manifest
from exp_gm_t3_02.loop import generate_shared_draft, run_track_from_draft
from exp_gm_t3_02.prompts import reviewer_prompt, rule_builder_draft, rule_executor, rule_review, strip_source
from exp_gm_t3_02.rule_tests import main as rule_main
from exp_gm_t3_02.scorer import score_cell
from v0_first_batch.paths import BRIDGE_ROOT, GAWORLD_ROOT, ensure_import_paths
from v0_first_batch.schema import summarize_workflow

WORKFLOW_ID = "exp_gm_t3_02_integration"
T3_01_BASELINE = BRIDGE_ROOT / "output" / "exp_gm_t3_01_r0fix_20260825" / "cell_table.json"


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
        if extra.get("track") in {"single", "multi"} and not extra.get("payload_integrity"):
            return False
        if extra.get("track") == "drop" and not extra.get("payload_integrity"):
            return False
    return bool(cells)


def _t3_01_full() -> dict[str, float | None]:
    if not T3_01_BASELINE.is_file():
        return {"single": None, "multi": None, "drop": None}
    payload = json.loads(T3_01_BASELINE.read_text(encoding="utf-8"))
    fair = payload.get("fairness") or {}
    return {
        "single": fair.get("single_full"),
        "multi": fair.get("multi_full"),
        "drop": fair.get("drop_full"),
    }


def _gain(new: float | None, old: float | None) -> float | None:
    if new is None or old is None:
        return None
    return round(new - old, 4)


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


def _claim(gate: str, metrics: dict) -> str:
    if gate == "A_r0":
        return "Coverage 或公平性未过，回到 R0，不解释能力。不补重复。"
    errors = metrics.get("first_error") or {}
    if errors.get("review_decision_incorrect"):
        return "Reviewer 判断错：CHANGE 单独会做，完整上下文导致判断退化。"
    if errors.get("review_payload_mutated"):
        return "Payload hash 不一致：消息编排或序列化问题。"
    if errors.get("executor_did_not_read_payload"):
        return "Executor 没读 payload：交接/上下文接入问题。"
    if errors.get("partial_change_applied"):
        return "收到正确 payload 仍 partial：完整流程上下文造成执行退化。"
    if gate == "C_floor":
        return "三轨仍全 0。继续按新首错定位，不补重复。不能解释成多 Agent 无价值。"
    multi = metrics["FullPass"]["multi"]
    single = metrics["FullPass"]["single"]
    drop = metrics["FullPass"]["drop"]
    if multi is not None and single is not None and multi > single and drop is not None and drop < multi:
        return "Multi 高于 Single，Drop 低：独立审核产生可识别价值。不补 54 格。"
    if single and multi:
        return "Single/Multi 都提升：组件契约集成有效。不补 54 格，不建留出。"
    return "已脱离测量失败。不补 54 格，不建留出，不开 C1。"


def _metrics(cells: list[dict]) -> dict:
    t301 = _t3_01_full()
    full = {track: _full_rate(cells, track) for track in TRACKS}
    outcome = None if full["multi"] is None or full["single"] is None else round(full["multi"] - full["single"], 4)
    review_delivery = None if full["multi"] is None or full["drop"] is None else round(full["multi"] - full["drop"], 4)
    floor = full["single"] == 0.0 and full["multi"] == 0.0
    return {
        "Coverage": {track: _coverage_track(cells, track) for track in TRACKS},
        "ReviewDecisionAccuracy": {track: _mean(_valid(cells, track), "review_decision_correct") for track in TRACKS},
        "PayloadIntegrity": {track: _mean(_valid(cells, track), "payload_integrity") for track in TRACKS},
        "CompleteChangeAdoptionRate": {track: _mean(_valid(cells, track), "complete") for track in TRACKS},
        "TargetCorrect": {track: _mean(_valid(cells, track), "target_correct") for track in TRACKS},
        "FullPass": full,
        "StrictPair": {track: _strict_pair(cells, track) for track in TRACKS},
        "T3_01_FullPass": t301,
        "T3_01_to_T3_02_FullPass_Gain": {track: _gain(full[track], t301.get(track)) for track in TRACKS},
        "OutcomeMultiAgentNetBenefit": {"value": None if floor else outcome, "reason": "common_workflow_floor" if floor else "multi_minus_single"},
        "WorkflowMultiAgentNetBenefit": {"value": None if floor else review_delivery, "reason": "common_workflow_floor" if floor else "multi_minus_drop"},
        "ReviewDeliveryValue": {"value": None if floor else review_delivery, "reason": "common_workflow_floor" if floor else "multi_minus_drop"},
        "first_error": dict(Counter((c.get("process_profile") or {}).get("first_error") for c in cells)),
    }


def _pack(cells: list[dict], out: Path, *, phase: str, gate: str | None, freeze: dict | None) -> dict:
    summary = summarize_workflow(WORKFLOW_ID, cells)
    summary["ranking_eligible"] = False
    metrics = _metrics(cells)
    payload = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "experiment_id": "EXP-GM-T3-02",
        "parent": "EXP-GM-T3-01",
        "phase": phase,
        "gate": gate,
        "ranking_eligible": False,
        "claim": _claim(gate or "", metrics),
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
        "note": "组件集成回归。不能证明泛化。不覆盖 T3-01。",
    }
    (out / "cell_table.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    fair = payload["fairness"]
    m = metrics
    lines = [
        "# EXP-GM-T3-02",
        "",
        f"- 时间：{payload['generated_at']}",
        f"- phase：{phase}；gate：{gate}",
        "- ranking_eligible：false",
        "- parent：EXP-GM-T3-01；construct：component_to_workflow_integration",
        f"- 冻结：{(freeze or {}).get('base_commit')}",
        "",
        "## 测量门",
        "",
        f"- Coverage：{fair['coverage']}",
        f"- 初稿哈希一致：{fair['draft_hash_ok']}",
        f"- 预算均为 3 次：{fair['budget_ok']}",
        f"- Drop 隔离：{fair['isolation_ok']}",
        f"- Payload 完整性：{fair['payload_integrity_ok']}",
        "",
        "## 主报",
        "",
        "| 指标 | Single | Multi | Drop |",
        "|---|---:|---:|---:|",
        f"| Coverage | {m['Coverage']['single']} | {m['Coverage']['multi']} | {m['Coverage']['drop']} |",
        f"| ReviewDecisionAccuracy | {m['ReviewDecisionAccuracy']['single']} | {m['ReviewDecisionAccuracy']['multi']} | {m['ReviewDecisionAccuracy']['drop']} |",
        f"| PayloadIntegrity | {m['PayloadIntegrity']['single']} | {m['PayloadIntegrity']['multi']} | {m['PayloadIntegrity']['drop']} |",
        f"| CompleteChangeAdoptionRate | {m['CompleteChangeAdoptionRate']['single']} | {m['CompleteChangeAdoptionRate']['multi']} | {m['CompleteChangeAdoptionRate']['drop']} |",
        f"| TargetCorrect | {m['TargetCorrect']['single']} | {m['TargetCorrect']['multi']} | {m['TargetCorrect']['drop']} |",
        f"| FullPass | {m['FullPass']['single']} | {m['FullPass']['multi']} | {m['FullPass']['drop']} |",
        f"| StrictPair | {m['StrictPair']['single']} | {m['StrictPair']['multi']} | {m['StrictPair']['drop']} |",
        "",
        f"- T3-01 FullPass：{m['T3_01_FullPass']}",
        f"- T3-01 → T3-02 FullPass Gain：{m['T3_01_to_T3_02_FullPass_Gain']}",
        f"- OutcomeMultiAgentNetBenefit：{m['OutcomeMultiAgentNetBenefit']}",
        f"- WorkflowMultiAgentNetBenefit：{m['WorkflowMultiAgentNetBenefit']}",
        f"- ReviewDeliveryValue：{m['ReviewDeliveryValue']}",
        f"- first_error：{m['first_error']}",
        "",
        f"**结论：** {_claim(gate or '', metrics)}",
        "",
        "| instance | valid | FullPass | track | first_error |",
        "|---|---|---|---|---|",
    ]
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


def run_repeat(out: Path, repeat_id: int, *, mode: str) -> list[dict]:
    cells: list[dict] = []
    for task in load_tasks():
        for variant in VARIANTS:
            shared_dir = out / "shared_drafts" / f"{task['id']}_{variant}_r{repeat_id}"
            generate_fn = (lambda _p, t=task: rule_builder_draft(t)) if mode == "rule" else (lambda prompt: strip_source(_llm(prompt)))
            shared = generate_shared_draft(task=task, variant=variant, repeat_id=repeat_id, out_dir=shared_dir, generate_fn=generate_fn)
            for track in TRACKS:
                instance_id = f"{task['id']}_{variant}_{track}_r{repeat_id}"
                print(f"run {instance_id} mode={mode}", flush=True)
                log: list[dict] = []

                def reviewer_fn(draft: str, t=task, v=variant, tr=track, lg=log):
                    prompt = reviewer_prompt(t, v, draft, self_check=tr == "single")
                    if mode == "rule":
                        parsed = rule_review(t, v, draft)
                        raw = json.dumps(parsed, ensure_ascii=False)
                    else:
                        raw = _llm(prompt)
                        parsed = parse_json_object(raw) or {}
                    lg.append({"stage": "review", "prompt": prompt, "raw_text": raw, "parsed": parsed})
                    return parsed

                def revise_fn(prompt: str, review, t=task, lg=log):
                    from exp_gm_t3_02.rule_tests import _draft_from_prompt

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


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--phase", choices=("rule", "seed0"), default="seed0")
    args = parser.parse_args()
    ensure_import_paths()
    os.chdir(GAWORLD_ROOT)
    print("phase=rule", flush=True)
    if rule_main() != 0:
        return 1
    if args.phase == "rule":
        print("Rule 已过门。seed0 用 --phase seed0。", flush=True)
        return 0
    from exp_gm_t3_02.fairness import preflight

    out = BRIDGE_ROOT / "output" / "exp_gm_t3_02_20260825"
    out.mkdir(parents=True, exist_ok=True)
    check = preflight()
    print("fairness_preflight", json.dumps({k: v for k, v in check.items() if k not in {"v2_leaks_helper", "sha256_text"}}, ensure_ascii=False), flush=True)
    if not check["ok"]:
        print("fairness preflight failed; not freezing, not calling the model.", flush=True)
        return 1
    freeze = write_manifest(out)
    print("frozen", json.dumps({k: v for k, v in freeze.items() if k != "fairness_preflight"}, ensure_ascii=False), flush=True)
    print("phase=seed0", flush=True)
    cells = run_repeat(out, 0, mode="llm")
    coverage = summarize_workflow(WORKFLOW_ID, cells)["coverage"]
    gate = _seed0_gate(cells, coverage)
    payload = _pack(cells, out, phase="seed0", gate=gate, freeze=freeze)
    print((out / "REPORT.md").read_text(encoding="utf-8"))
    if gate == "A_r0":
        print("gate=A_r0，停止。不补重复。", flush=True)
        return 1
    if gate == "C_floor":
        print("gate=C_floor，三轨仍全 0。不补重复。", flush=True)
        return 0
    print("repeat 0 完成。按计划不补 54 格，不建留出，不开 C1。", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
