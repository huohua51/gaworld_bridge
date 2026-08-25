#!/usr/bin/env python3
"""EXP-GM-T3-01 runner. Seed0 freezes hashes, then runs 18 cells and branches."""

from __future__ import annotations

import argparse
import json
import os
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path

from exp_gm_t3_01.budget import MODEL, PROVIDER, TEMPERATURE
from exp_gm_t3_01.contracts.review_action import parse_json_object
from exp_gm_t3_01.fairness import preflight, sha256_text, v2_leaks_in_prompt
from exp_gm_t3_01.freeze import write_manifest
from exp_gm_t3_01.loader import TRACKS, VARIANTS, load_tasks
from exp_gm_t3_01.loop import generate_shared_draft, run_track_from_draft
from exp_gm_t3_01.roles import (
    builder_revise_prompt,
    reviewer_prompt,
    rule_builder_draft,
    rule_builder_revise,
    rule_reviewer,
    self_check_prompt,
)
from exp_gm_t3_01.rule_tests.calibrate import main as rule_main
from exp_gm_t3_01.scorer import score_cell
from v0_first_batch.paths import BRIDGE_ROOT, GAWORLD_ROOT, ensure_import_paths
from v0_first_batch.schema import summarize_workflow

WORKFLOW_ID = "exp_gm_t3_01_full_workflow"


def _pin_glm() -> None:
    ensure_import_paths()
    from config import CONFIG

    providers = CONFIG.setdefault("llm", {}).setdefault("providers", {})
    glm = providers.setdefault(PROVIDER, {})
    if isinstance(glm, dict):
        glm["max_tokens"] = max(int(glm.get("max_tokens") or 0), 1024)
        glm["temperature"] = TEMPERATURE
    routing = CONFIG.setdefault("llm", {}).setdefault("routing", {})
    routing["default"] = PROVIDER
    tasks = dict(routing.get("tasks") or {})
    tasks["interview"] = PROVIDER
    routing["tasks"] = tasks
    os.environ["GAWORLD_LLM_PROVIDER"] = PROVIDER
    CONFIG.setdefault("eval_mode", {})["enabled"] = True
    from gaworld.eval_mode import apply_eval_mode_runtime

    apply_eval_mode_runtime(CONFIG)


def _llm(prompt: str) -> str:
    _pin_glm()
    from config import CONFIG
    from llm_providers import LLMRouter

    return LLMRouter(CONFIG).call(prompt, task="interview") or ""


def _rule_generate(task):
    return lambda _brief: rule_builder_draft(task)


def _rule_revise(task):
    return lambda _brief, source, review: rule_builder_revise(task, review=review, current=source)


def _rule_reviewer(task):
    return lambda draft, private: rule_reviewer(draft, task, private)


def _llm_generate(_task):
    return lambda prompt: _llm(prompt)


def _llm_revise(log: list[dict]):
    def _fn(brief, source, review):
        prompt = builder_revise_prompt(brief, source, review)
        raw_text = _llm(prompt)
        log.append({
            "stage": "builder_final",
            "prompt": prompt,
            "had_review": review is not None,
            "prompt_sha": sha256_text(prompt),
            "raw_text": raw_text,
        })
        return raw_text

    return _fn


def _llm_reviewer(track: str, log: list[dict]):
    def _fn(draft, private):
        prompt = self_check_prompt(draft, private) if track == "single" else reviewer_prompt(draft, private)
        raw_text = _llm(prompt)
        parsed = parse_json_object(raw_text) or {}
        log.append({
            "stage": "review",
            "prompt": prompt,
            "track": track,
            "prompt_sha": sha256_text(prompt),
            "raw_text": raw_text,
            "parsed": parsed,
        })
        return parsed

    return _fn


def _attach_prompts(loop: dict, task: dict, log: list[dict]) -> dict:
    review_p = next((e["prompt"] for e in log if e.get("stage") == "review"), "")
    final_p = next((e["prompt"] for e in log if e.get("stage") == "builder_final"), "")
    loop["review_prompt"] = review_p
    loop["final_prompt"] = final_p
    loop["call_log"] = log
    loop["first_prompt_leaks"] = v2_leaks_in_prompt(task, str(loop.get("first_prompt") or ""))
    loop["final_prompt_leaks"] = v2_leaks_in_prompt(task, final_p) if loop.get("track") == "drop" else []
    out_dir = Path(loop.get("final_path") or loop.get("draft_path") or ".")
    parent = out_dir.parent if out_dir.suffix else out_dir
    (parent / "first_prompt.txt").write_text(str(loop.get("first_prompt") or ""), encoding="utf-8")
    (parent / "review_prompt.txt").write_text(review_p, encoding="utf-8")
    (parent / "final_prompt.txt").write_text(final_p, encoding="utf-8")
    review_raw = next((e.get("raw_text") for e in log if e.get("stage") == "review"), "")
    (parent / "review_raw.txt").write_text(str(review_raw or ""), encoding="utf-8")
    return loop


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


def _draft_hash_ok(cells: list[dict]) -> bool:
    hashes: dict[tuple, set[str]] = defaultdict(set)
    inputs: dict[tuple, set[str]] = defaultdict(set)
    for cell in cells:
        extra = cell.get("extra") or {}
        key = (extra.get("task_id"), extra.get("variant"), extra.get("repeat_id"))
        hashes[key].add(str(extra.get("shared_draft_sha256") or ""))
        inputs[key].add(str(extra.get("first_input_sha") or extra.get("draft_prompt_sha") or ""))
    return (
        bool(hashes)
        and all(len(values) == 1 and "" not in values for values in hashes.values())
        and all(len(values) == 1 and "" not in values for values in inputs.values())
    )


def _budget_ok(cells: list[dict]) -> bool:
    for cell in cells:
        extra = cell.get("extra") or {}
        if extra.get("budget_calls") != 3:
            return False
        if list(extra.get("budget_kinds") or []) != ["builder_draft", "review", "builder_final"]:
            return False
    return bool(cells)


def _isolation_ok(cells: list[dict]) -> bool:
    drops = [c for c in cells if (c.get("extra") or {}).get("track") == "drop"]
    if not drops:
        return False
    for cell in drops:
        extra = cell.get("extra") or {}
        if not extra.get("reviewer_ran"):
            return False
        if extra.get("executor_saw_review"):
            return False
        if extra.get("drop_inbox_empty") is False:
            return False
    return True


def _seed0_gate(cells: list[dict], coverage: float) -> str:
    if coverage < 1.0 or len(cells) < 18:
        return "A_r0"
    if not _draft_hash_ok(cells) or not _budget_ok(cells) or not _isolation_ok(cells):
        return "A_r0"
    single = _full_rate(cells, "single")
    multi = _full_rate(cells, "multi")
    if single == 0.0 and multi == 0.0:
        return "C_floor"
    if single == 1.0 and multi == 1.0:
        return "C_ceiling_fill"
    return "fill_repeats"


def _metrics(cells: list[dict]) -> dict:
    return {
        "TargetCorrect": {track: _mean(_valid(cells, track), "target_correct") for track in TRACKS},
        "OracleConditionedFullPass": {track: _full_rate(cells, track) for track in TRACKS},
        "FalsePositiveRevisionRate": _mean(_valid(cells, variant="control"), "false_positive_revision"),
        "TrueRevisionRate": _mean(_valid(cells, variant="intervention"), "true_revision"),
        "VerifiedPatchAdoptionRate": _mean(_valid(cells, variant="intervention"), "verified_patch_adoption"),
        "single_minus_multi": None
        if _full_rate(cells, "single") is None or _full_rate(cells, "multi") is None
        else round(_full_rate(cells, "single") - _full_rate(cells, "multi"), 4),
        "multi_minus_drop": None
        if _full_rate(cells, "multi") is None or _full_rate(cells, "drop") is None
        else round(_full_rate(cells, "multi") - _full_rate(cells, "drop"), 4),
        "first_error": dict(Counter((c.get("process_profile") or {}).get("first_error") for c in cells)),
    }


def _pack(cells: list[dict], out: Path, *, phase: str, gate: str | None, freeze: dict | None) -> dict:
    summary = summarize_workflow(WORKFLOW_ID, cells)
    summary["ranking_eligible"] = False
    metrics = _metrics(cells)
    payload = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "experiment_id": "EXP-GM-T3-01",
        "phase": phase,
        "gate": gate,
        "ranking_eligible": False,
        "freeze": freeze,
        "summary": summary,
        "fairness": {
            "coverage": summary["coverage"],
            "draft_hash_ok": _draft_hash_ok(cells),
            "budget_ok": _budget_ok(cells),
            "isolation_ok": _isolation_ok(cells),
            "single_full": _full_rate(cells, "single"),
            "multi_full": _full_rate(cells, "multi"),
            "drop_full": _full_rate(cells, "drop"),
        },
        "metrics": metrics,
        "model": MODEL,
        "temperature": TEMPERATURE,
        "note": "seed0 先看测量门，不宣布多Agent价值。",
    }
    (out / "cell_table.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    if phase == "seed0":
        (out / "cell_table_seed0.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    fair = payload["fairness"]
    lines = [
        "# EXP-GM-T3-01",
        "",
        f"- 时间：{payload['generated_at']}",
        f"- phase：{phase}；gate：{gate}",
        "- ranking_eligible：false",
        f"- 冻结：{(freeze or {}).get('base_commit')}",
        "",
        "## 测量门",
        "",
        "seed0 先看这四项，不比较谁更强。",
        "",
        f"- Coverage：{fair['coverage']}",
        f"- 初稿哈希一致：{fair['draft_hash_ok']}",
        f"- 预算均为 3 次：{fair['budget_ok']}",
        f"- Drop 隔离且 Reviewer 实际运行：{fair['isolation_ok']}",
        f"- FullPass Single / Multi / Drop：{fair['single_full']} / {fair['multi_full']} / {fair['drop_full']}",
        "",
        "## 主报",
        "",
        f"- TargetCorrect：{metrics['TargetCorrect']}",
        f"- OracleConditionedFullPass：{metrics['OracleConditionedFullPass']}",
        f"- FalsePositiveRevisionRate：{metrics['FalsePositiveRevisionRate']}",
        f"- TrueRevisionRate：{metrics['TrueRevisionRate']}",
        f"- VerifiedPatchAdoptionRate：{metrics['VerifiedPatchAdoptionRate']}",
        f"- Single−Multi：{metrics['single_minus_multi']}",
        f"- Multi−Drop：{metrics['multi_minus_drop']}",
        f"- first_error：{metrics['first_error']}",
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
    if gate == "A_r0":
        lines.extend(["", "**分支：** Coverage 或公平性未过，停止。multi_agent_net_benefit=N/A。不改提示重跑。"])
    elif gate == "C_floor":
        lines.extend(["", "**分支：** Single 与 Multi 共同地板。不能解释成多 Agent 无价值。multi_agent_net_benefit=N/A。"])
    elif gate == "C_ceiling_fill":
        lines.extend(["", "**分支：** Single 与 Multi 都满分。可补重复，但任务可能过于简单；即使 Multi=Single 也不能说多 Agent 无价值。"])
    elif gate == "fill_repeats" or gate == "completed_repeats":
        lines.extend(["", "**分支：** Coverage 通过且脱离共同地板。不在 seed0 宣布谁更强。"])
    (out / "REPORT.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    if phase == "seed0":
        (out / "REPORT_seed0.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    return payload


def run_repeat(out: Path, repeat_id: int, *, mode: str) -> list[dict]:
    cells: list[dict] = []
    for task in load_tasks():
        for variant in VARIANTS:
            shared_dir = out / "shared_drafts" / f"{task['id']}_{variant}_r{repeat_id}"
            generate_fn = _rule_generate(task) if mode == "rule" else _llm_generate(task)
            shared = generate_shared_draft(
                task=task, variant=variant, repeat_id=repeat_id, out_dir=shared_dir, generate_fn=generate_fn,
            )
            for track in TRACKS:
                instance_id = f"{task['id']}_{variant}_{track}_r{repeat_id}"
                print(f"run {instance_id} mode={mode}", flush=True)
                log: list[dict] = [{"stage": "builder_draft", "prompt": shared.get("draft_prompt"), "prompt_sha": sha256_text(str(shared.get("draft_prompt") or ""))}]
                if mode == "rule":
                    revise_fn = _rule_revise(task)
                    reviewer_fn = _rule_reviewer(task)
                else:
                    revise_fn = _llm_revise(log)
                    reviewer_fn = _llm_reviewer(track, log)
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
                if mode == "llm":
                    loop = _attach_prompts(loop, task, log)
                cell = score_cell(
                    task=task, variant=variant, track=track, repeat_id=repeat_id,
                    loop=loop, workflow_id=WORKFLOW_ID, instance_id=instance_id,
                )
                cell["ranking_eligible"] = False
                extra = dict(cell.get("extra") or {})
                extra["mode"] = mode
                extra["model_version"] = "rule" if mode == "rule" else MODEL
                extra["draft_prompt_sha"] = shared.get("draft_prompt_sha256") or sha256_text(str(shared.get("draft_prompt") or ""))
                extra["first_input_sha"] = extra["draft_prompt_sha"]
                extra["draft_has_v2_tokens"] = bool(shared.get("draft_has_v2_tokens"))
                cell["extra"] = extra
                (out / "runs" / instance_id / "cell_result.json").write_text(
                    json.dumps(cell, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
                )
                (out / "runs" / instance_id / "call_log.json").write_text(
                    json.dumps(log, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
                )
                cells.append(cell)
                print(
                    f"  valid={cell.get('measurement_valid')} full_pass={cell.get('full_pass')} "
                    f"first_error={(cell.get('process_profile') or {}).get('first_error')}",
                    flush=True,
                )
    return cells


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--phase", choices=("rule", "seed0"), default="rule")
    args = parser.parse_args()
    ensure_import_paths()
    os.chdir(GAWORLD_ROOT)
    print("phase=rule", flush=True)
    if rule_main() != 0:
        return 1
    if args.phase == "rule":
        print("Rule 已过门。seed0 用 --phase seed0。", flush=True)
        return 0

    out = BRIDGE_ROOT / "output" / "exp_gm_t3_01_r0fix_20260825"
    out.mkdir(parents=True, exist_ok=True)
    check = preflight()
    print("fairness_preflight", json.dumps(check, ensure_ascii=False), flush=True)
    if not check["ok"]:
        print("fairness preflight failed; not freezing, not calling the model.", flush=True)
        return 1
    freeze = write_manifest(out)
    print("frozen", json.dumps(freeze, ensure_ascii=False), flush=True)

    print("phase=seed0_r0fix", flush=True)
    cells = run_repeat(out, 0, mode="llm")
    coverage = summarize_workflow(WORKFLOW_ID, cells)["coverage"]
    measurement = {
        "coverage": coverage,
        "draft_hash_ok": _draft_hash_ok(cells),
        "budget_ok": _budget_ok(cells),
        "isolation_ok": _isolation_ok(cells),
    }
    r0_pass = coverage == 1.0 and measurement["budget_ok"] and measurement["isolation_ok"]
    gate = "r0_pass" if r0_pass else "A_r0"
    payload = _pack(cells, out, phase="seed0", gate=gate, freeze=freeze)
    print((out / "REPORT.md").read_text(encoding="utf-8"))
    print("r0_measurement", json.dumps(measurement, ensure_ascii=False), flush=True)
    if not r0_pass:
        print("gate=A_r0，测量门未过。不补 Seed，不处理 false_positive_revision。", flush=True)
        return 1
    print("R0 测量门通过。本轮只跑 repeat 0，不补 54 格，不处理 false_positive_revision。", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
