#!/usr/bin/env python3
"""HO-GM-I1-01: TASK-I1 Verified Information Relay. Seed 0 first."""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path

from holdout_i1.loop import run_cell_loop
from holdout_i1.probes import PROBES, variant_spec
from holdout_i1.roles import (
    dispatcher_prompt,
    observer_prompt,
    parse_json_object,
    rule_dispatcher,
    rule_observer,
    rule_verifier,
    verifier_prompt,
)
from holdout_i1.scoring import first_error, process_success, r0_ok
from v0_first_batch.paths import BRIDGE_ROOT, GAWORLD_ROOT, ensure_import_paths
from v0_first_batch.schema import CriterionResult, GateResult, compose, summarize_workflow

WORKFLOW_ID = "holdout_i1_verified_information_relay"
TRACKS = ("focused", "full", "drop_verified", "no_verification")
VARIANTS = ("control", "intervention")


def _pin_glm() -> None:
    ensure_import_paths()
    from config import CONFIG

    providers = CONFIG.setdefault("llm", {}).setdefault("providers", {})
    glm = providers.setdefault("paratera_glm", {})
    if isinstance(glm, dict):
        glm["max_tokens"] = max(int(glm.get("max_tokens") or 0), 2048)
        glm["temperature"] = 0
    routing = CONFIG.setdefault("llm", {}).setdefault("routing", {})
    routing["default"] = "paratera_glm"
    tasks = dict(routing.get("tasks") or {})
    tasks["schedule"] = "paratera_glm"
    routing["tasks"] = tasks
    os.environ["GAWORLD_LLM_PROVIDER"] = "paratera_glm"


def _llm(prompt: str) -> str:
    _pin_glm()
    from config import CONFIG
    from llm_providers import LLMRouter

    return LLMRouter(CONFIG).call(prompt, task="interview") or ""


def _rule_fns(probe: dict, variant: str):
    def observer(_signals):
        return rule_observer(probe, variant)

    def verifier(raw, private, version):
        return rule_verifier(raw, private, version)

    def dispatcher(verified, raw):
        return rule_dispatcher(probe, verified=verified, raw=raw)

    return observer, verifier, dispatcher


def _llm_fns(probe: dict, variant: str):
    spec = variant_spec(probe, variant)

    def observer(_signals):
        raw = _llm(observer_prompt(probe, spec["signals"]))
        try:
            payload = parse_json_object(raw)
        except (ValueError, json.JSONDecodeError):
            return []
        if isinstance(payload, list):
            return [item for item in payload if isinstance(item, dict)]
        if isinstance(payload, dict) and "source_id" in payload:
            return [payload]
        if isinstance(payload, dict):
            return list(payload.get("signals") or payload.get("reports") or [])
        return []

    def verifier(raw, private, version):
        text = _llm(verifier_prompt(raw, private, version))
        try:
            return parse_json_object(text)
        except (ValueError, json.JSONDecodeError):
            return {}

    def dispatcher(verified, raw):
        extra = "核验消息未送达，可再决策一次，但没有核实状态。" if verified is None and raw is None else ""
        text = _llm(dispatcher_prompt(probe, verified=verified, raw=raw, extra=extra))
        try:
            return parse_json_object(text)
        except (ValueError, json.JSONDecodeError):
            return {}

    return observer, verifier, dispatcher


def _score_cell(probe: dict, variant: str, track: str, seed: int, out_root: Path, *, mode: str) -> dict:
    ensure_import_paths()
    from config import CONFIG
    from gaworld.eval_mode import apply_eval_mode_runtime

    cfg = CONFIG
    cfg.setdefault("eval_mode", {})
    cfg["eval_mode"]["enabled"] = True
    apply_eval_mode_runtime(cfg)

    instance_id = f"{probe['id']}_{variant}_{track}_s{seed}"
    run_dir = out_root / "runs" / instance_id
    run_dir.mkdir(parents=True, exist_ok=True)
    observer_fn, verifier_fn, dispatcher_fn = _rule_fns(probe, variant) if mode == "rule" else _llm_fns(probe, variant)
    loop = run_cell_loop(
        probe=probe,
        variant=variant,
        track=track,
        task_id=instance_id,
        out_dir=run_dir,
        observer_fn=observer_fn,
        verifier_fn=verifier_fn,
        dispatcher_fn=dispatcher_fn,
    )
    action = loop.get("action") or {}
    oracle = loop["oracle_value"]
    other = probe["value_b"] if variant == "control" else probe["value_a"]
    target_correct = action.get("value") == oracle
    other_also = action.get("value") == other
    r0, r0_detail = r0_ok(track, loop)
    events = list(loop.get("events") or [])
    err = first_error(
        track=track,
        events=events,
        observation_ok="observation_created" in events or track == "focused",
        raw_sent="raw_signal_sent" in events or track == "focused",
        raw_delivered="raw_signal_delivered" in events or track not in {"full", "drop_verified"},
        verification_requested="verification_requested" in events or track not in {"full", "drop_verified"},
        wrong_source="wrong_source_verified" in events,
        verified_emitted="verified_message_emitted" in events or track == "focused",
        verified_delivered="verified_delivered" in events or track != "full",
        verified_read="verified_message_read" in events or track not in {"focused", "full"},
        verified_adopted="verified_state_adopted" in events or track not in {"focused", "full"},
        unauthorized_read=bool(loop.get("dispatcher_read_trust")),
        target_correct=target_correct,
        stale=action.get("adopted_state_version") not in {None, "", loop.get("expected_version")} and target_correct,
        contract_error=str(loop.get("contract_error") or "ok"),
    )
    conditioned = process_success(track, loop, target_correct=target_correct, other_also=other_also)
    cell = compose(
        workflow_id=WORKFLOW_ID,
        instance_id=instance_id,
        measurement_gates=[
            GateResult("execution_valid", r0, layer="R0", detail=r0_detail),
            GateResult("eval_mode_on", True, layer="R0"),
            GateResult("fields_extractable", True, layer="R0"),
        ],
        artifact_gates=[
            GateResult("action_present", bool(action.get("value")) or track in {"drop_verified", "no_verification"}, layer="R1"),
            GateResult("roles_legal", not loop.get("verifier_submitted") and not loop.get("dispatcher_read_trust"), layer="R1"),
        ],
        criteria=[
            CriterionResult(
                criterion_id="target_correct",
                layer="R2",
                scorer="action_oracle",
                evaluable=True,
                score=1.0 if target_correct else 0.0,
                passed=target_correct,
                critical=False,
                detail=f"got={action.get('value')} oracle={oracle}",
            ),
            CriterionResult(
                criterion_id="oracle_conditioned_success",
                layer="R3",
                scorer="verified_bind",
                evaluable=True,
                score=1.0 if conditioned else 0.0,
                passed=conditioned,
                critical=True,
                detail=f"evidence={action.get('evidence_message_id')} version={action.get('adopted_state_version')}",
            ),
        ],
        process_profile={
            "first_error": err,
            "events": events,
            "adopted_state_version": action.get("adopted_state_version"),
            "evidence_message_id": action.get("evidence_message_id"),
            "verified_message_id": (loop.get("verified") or {}).get("message_id"),
            "observer_calls": loop.get("observer_calls"),
            "verifier_calls": loop.get("verifier_calls"),
            "dispatcher_calls": loop.get("dispatcher_calls"),
        },
        extra={
            "probe_id": probe["id"],
            "track": track,
            "variant": variant,
            "seed": seed,
            "mode": mode,
            "model_version": "rule" if mode == "rule" else "GLM-4-Flash",
            "temperature": 0,
            "target_correct": target_correct,
            "oracle_conditioned_success": conditioned,
            "other_also": other_also,
            "action": action,
            "ranking_note": "pilot, not a leaderboard",
        },
    )
    cell["ranking_eligible"] = False
    (run_dir / "cell_result.json").write_text(json.dumps(cell, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return cell


def _rate(cells: list[dict], track: str, variant: str | None = None) -> float | None:
    subset = [
        c for c in cells
        if c.get("extra", {}).get("track") == track
        and (variant is None or c.get("extra", {}).get("variant") == variant)
        and c.get("full_pass") is not None
    ]
    if not subset:
        return None
    return round(sum(int(c["full_pass"]) for c in subset) / len(subset), 4)


def _strict_pair(cells: list[dict]) -> float | None:
    groups: dict[tuple, dict] = {}
    for cell in cells:
        extra = cell.get("extra") or {}
        key = (extra.get("probe_id"), extra.get("track"), extra.get("seed"))
        groups.setdefault(key, {})[extra.get("variant")] = cell
    pairs = [g for g in groups.values() if "control" in g and "intervention" in g]
    if not pairs:
        return None
    ok = 0
    for pair in pairs:
        c, i = pair["control"], pair["intervention"]
        if c.get("measurement_valid") and i.get("measurement_valid") and c.get("full_pass") == 1 and i.get("full_pass") == 1:
            ok += 1
    return round(ok / len(pairs), 4)


def _lock_rate(cells: list[dict]) -> float | None:
    groups: dict[tuple, dict] = {}
    for cell in cells:
        extra = cell.get("extra") or {}
        key = (extra.get("probe_id"), extra.get("track"), extra.get("seed"))
        groups.setdefault(key, {})[extra.get("variant")] = extra.get("action") or {}
    pairs = [g for g in groups.values() if "control" in g and "intervention" in g]
    if not pairs:
        return None
    locked = 0
    for pair in pairs:
        a = (pair["control"] or {}).get("value")
        b = (pair["intervention"] or {}).get("value")
        if a and b and a == b:
            locked += 1
    return round(locked / len(pairs), 4)


def _unauth_rate(cells: list[dict]) -> float:
    if not cells:
        return 0.0
    hits = 0
    for cell in cells:
        events = (cell.get("process_profile") or {})
        extra = cell.get("extra") or {}
        if extra.get("action") and "unauthorized" in str(events.get("first_error")):
            hits += 1
        if (cell.get("process_profile") or {}).get("first_error") == "unauthorized_private_read":
            hits += 1
    return round(hits / len(cells), 4)


def _decision(rates: dict) -> str:
    f, full, drop, nv = rates.get("focused"), rates.get("full"), rates.get("drop_verified"), rates.get("no_verification")
    if any(v is None for v in (f, full, drop, nv)):
        return "出现不可评分。先看 R0，停止通信能力解释。"
    gap_note = ""
    if f is not None and full is not None and f < 1.0:
        gap_note = " CommunicationPropagationGap 暂不可解释：direct_verified_state 仍有契约错误，不能当上限。"
    if f >= 0.8 and full >= 0.8 and drop <= 0.4:
        return "direct_verified_state/Full 高、Drop 低：通信与核验闭环有效。" + gap_note
    if f >= 0.8 and full < 0.5:
        return "direct_verified_state 高、Full 低：看 Rule Full。Rule 高则是模型交互失败；Rule 也低则修平台。" + gap_note
    if full >= 0.8 and drop >= 0.8:
        return "Full 和 Drop 都高：优先查信息泄漏，或任务可以绕过通信。"
    if full >= 0.8 and nv >= 0.8:
        return "Full 和 No-verification 都高：Verifier 角色可能并不必要，或信号没有真正冲突。"
    return "结果混合。按 first_error 拆开 Observer / Verifier / 送达 / Dispatcher。" + gap_note


def _pack(cells: list[dict], out: Path, *, phase: str) -> dict:
    summary = summarize_workflow(WORKFLOW_ID, cells)
    summary["ranking_eligible"] = False
    scored = [c for c in cells if c.get("full_pass") is not None]
    target_rate = (
        round(sum(int(bool((c.get("extra") or {}).get("target_correct"))) for c in scored) / len(scored), 4)
        if scored else None
    )
    rates = {
        "focused": _rate(cells, "focused"),
        "full": _rate(cells, "full"),
        "drop_verified": _rate(cells, "drop_verified"),
        "no_verification": _rate(cells, "no_verification"),
        "full_control": _rate(cells, "full", "control"),
        "full_intervention": _rate(cells, "full", "intervention"),
        "drop_control": _rate(cells, "drop_verified", "control"),
        "drop_intervention": _rate(cells, "drop_verified", "intervention"),
    }
    payload = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "experiment_id": "HO-GM-I1-01",
        "task_id": "TASK-I1",
        "status": "pilot",
        "ranking_eligible": False,
        "phase": phase,
        "summary": summary,
        "target_correct_rate": target_rate,
        "rates": rates,
        "communication_value": None if rates["full"] is None or rates["drop_verified"] is None else round(rates["full"] - rates["drop_verified"], 4),
        "verification_value": None if rates["full"] is None or rates["no_verification"] is None else round(rates["full"] - rates["no_verification"], 4),
        "communication_propagation_gap": None if rates["focused"] is None or rates["full"] is None else round(rates["focused"] - rates["full"], 4),
        "strict_pair": _strict_pair(cells),
        "strict_pair_full": _strict_pair([c for c in cells if (c.get("extra") or {}).get("track") == "full"]),
        "strict_pair_focused": _strict_pair([c for c in cells if (c.get("extra") or {}).get("track") == "focused"]),
        "strategy_lock_rate": _lock_rate(cells),
        "unauthorized_read_rate": _unauth_rate(cells),
        "decision": "",
    }
    payload["decision"] = _decision(rates)
    payload["communication_propagation_interpretable"] = bool(
        rates["focused"] is not None and rates["focused"] >= 0.999
    )
    payload["holdout_run_once"] = True
    payload["parent"] = "EXP-GM-I1"
    import yaml

    (out / "GATE.yaml").write_text(
        yaml.safe_dump(
            {
                "experiment_id": "HO-GM-I1-01",
                "parent": "EXP-GM-I1",
                "phase": phase,
                "ranking_eligible": False,
                "holdout_run_once": True,
                "coverage": summary.get("coverage"),
                "measurement_valid": summary.get("measurement_valid"),
                "rates": rates,
                "communication_value": payload["communication_value"],
                "verification_value": payload["verification_value"],
                "strict_pair_full": payload["strict_pair_full"],
                "unauthorized_read_rate": payload["unauthorized_read_rate"],
                "decision": payload["decision"],
            },
            allow_unicode=True,
            sort_keys=False,
        ),
        encoding="utf-8",
    )
    (out / "cell_table.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    report = [
        "# HO-GM-I1-01 密封留出",
        "",
        f"- 时间：{payload['generated_at']}",
        "- 状态：sealed holdout，不可排名，只跑 seed0 一次",
        "- 父实验：EXP-GM-I1（开发集分数不改）",
        "- 只评 Dispatcher 结构化动作；猜对但无合法核验证据不算干净成功",
        "- focused 轨对外登记为 direct_verified_state，不是能力上限",
        "",
        "## 覆盖与主结果",
        "",
        f"- requested：{summary['requested']}",
        f"- measurement_valid：{summary['measurement_valid']}",
        f"- coverage：{summary['coverage']}",
        f"- oracle_conditioned FullPass：{summary['full_pass_rate']}",
        f"- target_correct：{target_rate}",
        f"- StrictPair（全轨）：{payload['strict_pair']}；direct_verified_state {payload['strict_pair_focused']}；Full {payload['strict_pair_full']}",
        f"- 策略锁死率：{payload['strategy_lock_rate']}",
        f"- 未经授权读取率：{payload['unauthorized_read_rate']}",
        "",
        "### 分轨与价值",
        "",
        f"- direct_verified_state（内部轨名 focused）：{rates['focused']}",
        f"- Full：{rates['full']}（control {rates['full_control']} / intervention {rates['full_intervention']}）",
        f"- Drop-verified：{rates['drop_verified']}（control {rates['drop_control']} / intervention {rates['drop_intervention']}）",
        f"- No-verification：{rates['no_verification']}",
        f"- CommunicationValue (Full − Drop)：{payload['communication_value']}",
        f"- VerificationValue (Full − NoVerify)：{payload['verification_value']}",
        f"- CommunicationPropagationGap (direct_verified_state − Full)：{payload['communication_propagation_gap']}",
        "",
        "## 决策",
        "",
        payload["decision"],
        "",
        "| instance | valid | FullPass | target_correct | conditioned | first_error |",
        "|---|---|---|---|---|---|",
    ]
    for cell in summary["cells"]:
        extra = cell.get("extra") or {}
        report.append(
            f"| {cell.get('instance_id')} | {cell.get('measurement_valid')} | {cell.get('full_pass')} | "
            f"{extra.get('target_correct')} | {extra.get('oracle_conditioned_success')} | "
            f"{(cell.get('process_profile') or {}).get('first_error')} |"
        )
    text = "\n".join(report) + "\n"
    (out / "REPORT.md").write_text(text, encoding="utf-8")
    return payload


def run_matrix(out: Path, seeds: list[int], *, mode: str) -> list[dict]:
    cells: list[dict] = []
    for probe in PROBES:
        for variant in VARIANTS:
            for track in TRACKS:
                for seed in seeds:
                    print(f"run {probe['id']} variant={variant} track={track} seed={seed} mode={mode}", flush=True)
                    cell = _score_cell(probe, variant, track, seed, out, mode=mode)
                    cells.append(cell)
                    extra = cell.get("extra") or {}
                    print(
                        f"  valid={cell.get('measurement_valid')} full_pass={cell.get('full_pass')} "
                        f"target_correct={extra.get('target_correct')} "
                        f"first_error={(cell.get('process_profile') or {}).get('first_error')}",
                        flush=True,
                    )
    return cells


def load_cells_except_track(out: Path, track: str) -> list[dict]:
    cells: list[dict] = []
    for path in sorted((out / "runs").glob("*/cell_result.json")):
        cell = json.loads(path.read_text(encoding="utf-8"))
        if (cell.get("extra") or {}).get("track") != track:
            cells.append(cell)
    return cells


def run_focused_matrix(out: Path, seeds: list[int], *, mode: str) -> list[dict]:
    cells: list[dict] = []
    for probe in PROBES:
        for variant in VARIANTS:
            for seed in seeds:
                print(f"run {probe['id']} variant={variant} track=focused seed={seed} mode={mode}", flush=True)
                cell = _score_cell(probe, variant, "focused", seed, out, mode=mode)
                cells.append(cell)
                extra = cell.get("extra") or {}
                print(
                    f"  valid={cell.get('measurement_valid')} full_pass={cell.get('full_pass')} "
                    f"target_correct={extra.get('target_correct')} "
                    f"first_error={(cell.get('process_profile') or {}).get('first_error')}",
                    flush=True,
                )
    return cells


def main() -> int:
    import argparse

    import yaml

    from holdout_i1.freeze import write_manifest

    parser = argparse.ArgumentParser()
    parser.add_argument("--phase", choices=("rule", "seed0"), default="seed0")
    args = parser.parse_args()
    ensure_import_paths()
    os.chdir(GAWORLD_ROOT)
    os.environ.setdefault("GAWORLD_LLM_PROVIDER", "paratera_glm")
    out = BRIDGE_ROOT / "output" / "holdout_i1_20260825"
    out.mkdir(parents=True, exist_ok=True)
    freeze_path = out / "FREEZE.yaml"
    if freeze_path.is_file():
        freeze = yaml.safe_load(freeze_path.read_text(encoding="utf-8")) or {}
        print("reuse freeze", freeze.get("base_commit"), flush=True)
    else:
        freeze = write_manifest(out)
        print("frozen", json.dumps({k: v for k, v in freeze.items() if k != "frozen_at"}, ensure_ascii=False), flush=True)
    if args.phase == "rule":
        print("Rule 已过门并冻结。下一步 --phase seed0 跑 24 格一次。不补 repeat。", flush=True)
        return 0
    _pin_glm()
    print("phase=seed0", flush=True)
    cells = run_matrix(out, [0], mode="llm")
    payload = _pack(cells, out, phase="seed0")
    payload["freeze"] = freeze.get("base_commit")
    payload["holdout_run_once"] = True
    payload["ranking_eligible"] = False
    (out / "cell_table.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print((out / "REPORT.md").read_text(encoding="utf-8"))
    if payload["summary"]["coverage"] < 1.0 or payload["summary"]["measurement_valid"] < 24:
        print("seed0 未过测量门。不补重复。不得回头调协议。", flush=True)
        return 1
    print("seed0 留出完成。不补 repeat 1/2。不得回头调协议。", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
