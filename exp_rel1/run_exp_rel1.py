#!/usr/bin/env python3
"""EXP-GM-REL1: TASK-REL1 history-based trust formation and update. Seed 0 first."""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path

from exp_rel1.loop import run_cell_loop
from exp_rel1.probes import PROBES, variant_spec
from exp_rel1.roles import (
    dispatcher_prompt,
    observer_prompt,
    parse_json_object,
    rule_dispatcher,
    rule_observer,
    rule_trust_updater,
    trust_updater_prompt,
)
from exp_rel1.scoring import first_error, process_success, r0_ok
from v0_first_batch.paths import BRIDGE_ROOT, GAWORLD_ROOT, ensure_import_paths
from v0_first_batch.schema import CriterionResult, GateResult, compose, summarize_workflow

WORKFLOW_ID = "exp_rel1_trust_formation_update"
TRACKS = ("focused", "full", "drop_trust", "no_history")
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

    def updater(history, currents, version, phase):
        return rule_trust_updater(history, currents, version, phase)

    def dispatcher(trust, currents, round_name):
        return rule_dispatcher(probe, trust=trust, round_name=round_name)

    return observer, updater, dispatcher


def _as_dict(payload: dict | list) -> dict:
    if isinstance(payload, dict):
        return payload
    return {}


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
        if isinstance(payload, dict) and "person_id" in payload:
            return [payload]
        if isinstance(payload, dict):
            return list(payload.get("signals") or payload.get("reports") or [])
        return []

    def updater(history, currents, version, phase):
        text = _llm(trust_updater_prompt(history, currents, version, phase))
        try:
            return _as_dict(parse_json_object(text))
        except (ValueError, json.JSONDecodeError):
            return {}

    def dispatcher(trust, currents, round_name):
        extra = "信任状态未送达，可再决策一次，但没有历史账本。" if trust is None and currents is None else ""
        text = _llm(dispatcher_prompt(probe, trust=trust, currents=currents, round_name=round_name, extra=extra))
        try:
            return _as_dict(parse_json_object(text))
        except (ValueError, json.JSONDecodeError):
            return {}

    return observer, updater, dispatcher


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
    observer_fn, updater_fn, dispatcher_fn = _rule_fns(probe, variant) if mode == "rule" else _llm_fns(probe, variant)
    loop = run_cell_loop(
        probe=probe,
        variant=variant,
        track=track,
        task_id=instance_id,
        out_dir=run_dir,
        observer_fn=observer_fn,
        updater_fn=updater_fn,
        dispatcher_fn=dispatcher_fn,
    )
    formation_action = loop.get("formation_action") or {}
    update_action = loop.get("update_action") or {}
    other = variant_spec(probe, "intervention" if variant == "control" else "control")
    formation_correct = formation_action.get("value") == loop["oracle_formation"]
    update_correct = update_action.get("value") == loop["oracle_update"]
    target_correct = formation_correct and update_correct
    other_also = (
        formation_action.get("value") == other["formation_value"]
        and update_action.get("value") == other["update_value"]
    )
    r0, r0_detail = r0_ok(track, loop)
    events = list(loop.get("events") or [])
    err = first_error(
        track=track,
        events=events,
        observation_ok="observation_created" in events or track == "focused",
        current_sent="current_signal_sent" in events or track == "focused",
        current_delivered="current_signal_delivered" in events or track not in {"full", "drop_trust"},
        trust_requested="trust_requested" in events or track not in {"full", "drop_trust"},
        history_read="history_read" in events or track not in {"full", "drop_trust"},
        history_missing="history_not_available" in events,
        trust_emitted="trust_message_emitted" in events or track == "focused",
        trust_delivered="trust_delivered" in events or track != "full",
        trust_read="trust_message_read" in events or track not in {"focused", "full"},
        trust_adopted="trust_state_adopted" in events or track not in {"focused", "full"},
        trust_updated="trust_updated" in events or track == "focused",
        unauthorized_read=bool(loop.get("dispatcher_read_history")),
        formation_correct=formation_correct,
        update_correct=update_correct,
        stale=(
            formation_action.get("adopted_trust_version") not in {None, "", loop.get("expected_formation_version")}
            or update_action.get("adopted_trust_version") not in {None, "", loop.get("expected_update_version")}
        )
        and target_correct,
    )
    conditioned = process_success(
        track, loop, formation_correct=formation_correct, update_correct=update_correct, other_also=other_also
    )
    cell = compose(
        workflow_id=WORKFLOW_ID,
        instance_id=instance_id,
        measurement_gates=[
            GateResult("execution_valid", r0, layer="R0", detail=r0_detail),
            GateResult("eval_mode_on", True, layer="R0"),
            GateResult("fields_extractable", True, layer="R0"),
        ],
        artifact_gates=[
            GateResult(
                "action_present",
                bool(formation_action.get("value") or update_action.get("value"))
                or track in {"drop_trust", "no_history"},
                layer="R1",
            ),
            GateResult(
                "roles_legal",
                not loop.get("updater_submitted") and not loop.get("dispatcher_read_history"),
                layer="R1",
            ),
        ],
        criteria=[
            CriterionResult(
                criterion_id="formation_correct",
                layer="R2",
                scorer="formation_oracle",
                evaluable=True,
                score=1.0 if formation_correct else 0.0,
                passed=formation_correct,
                critical=False,
                detail=f"got={formation_action.get('value')} oracle={loop['oracle_formation']}",
            ),
            CriterionResult(
                criterion_id="update_correct",
                layer="R2",
                scorer="update_oracle",
                evaluable=True,
                score=1.0 if update_correct else 0.0,
                passed=update_correct,
                critical=False,
                detail=f"got={update_action.get('value')} oracle={loop['oracle_update']}",
            ),
            CriterionResult(
                criterion_id="oracle_conditioned_success",
                layer="R3",
                scorer="trust_bind",
                evaluable=True,
                score=1.0 if conditioned else 0.0,
                passed=conditioned,
                critical=True,
                detail=(
                    f"formation={formation_action.get('evidence_message_id')} "
                    f"update={update_action.get('evidence_message_id')}"
                ),
            ),
        ],
        process_profile={
            "first_error": err,
            "events": events,
            "observer_calls": loop.get("observer_calls"),
            "updater_calls": loop.get("updater_calls"),
            "dispatcher_calls": loop.get("dispatcher_calls"),
            "relationships": loop.get("relationships"),
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
            "formation_correct": formation_correct,
            "update_correct": update_correct,
            "oracle_conditioned_success": conditioned,
            "other_also": other_also,
            "formation_action": formation_action,
            "update_action": update_action,
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
        groups.setdefault(key, {})[extra.get("variant")] = (
            (extra.get("formation_action") or {}).get("value"),
            (extra.get("update_action") or {}).get("value"),
        )
    pairs = [g for g in groups.values() if "control" in g and "intervention" in g]
    if not pairs:
        return None
    locked = 0
    for pair in pairs:
        if pair["control"] and pair["intervention"] and pair["control"] == pair["intervention"]:
            locked += 1
    return round(locked / len(pairs), 4)


def _unauth_rate(cells: list[dict]) -> float:
    if not cells:
        return 0.0
    hits = 0
    for cell in cells:
        if (cell.get("process_profile") or {}).get("first_error") == "unauthorized_history_read":
            hits += 1
    return round(hits / len(cells), 4)


def _decision(rates: dict) -> str:
    f, full, drop, nh = rates.get("focused"), rates.get("full"), rates.get("drop_trust"), rates.get("no_history")
    if any(v is None for v in (f, full, drop, nh)):
        return "出现不可评分。先看 R0，停止信任能力解释。"
    if f >= 0.8 and full >= 0.8 and drop <= 0.4:
        return "Focused/Full 高、Drop 低：信任形成、送达和更新闭环有效。"
    if f >= 0.8 and full < 0.5:
        return "Focused 高、Full 低：看 Rule Full。Rule 高则是模型交互失败；Rule 也低则修平台。"
    if full >= 0.8 and drop >= 0.8:
        return "Full 和 Drop 都高：优先查历史泄漏，或任务可以绕过信任状态。"
    if full >= 0.8 and nh >= 0.8:
        return "Full 和 No-history 都高：历史账本可能并不必要，或当前报告已经泄漏了答案。"
    return "结果混合。按 first_error 拆开形成 / 更新 / 送达 / Dispatcher。"


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
        "drop_trust": _rate(cells, "drop_trust"),
        "no_history": _rate(cells, "no_history"),
        "full_control": _rate(cells, "full", "control"),
        "full_intervention": _rate(cells, "full", "intervention"),
        "drop_control": _rate(cells, "drop_trust", "control"),
        "drop_intervention": _rate(cells, "drop_trust", "intervention"),
    }
    payload = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "experiment_id": "EXP-GM-REL1",
        "task_id": "TASK-REL1",
        "status": "pilot",
        "ranking_eligible": False,
        "phase": phase,
        "summary": summary,
        "target_correct_rate": target_rate,
        "rates": rates,
        "trust_delivery_value": None if rates["full"] is None or rates["drop_trust"] is None else round(rates["full"] - rates["drop_trust"], 4),
        "history_value": None if rates["full"] is None or rates["no_history"] is None else round(rates["full"] - rates["no_history"], 4),
        "trust_propagation_gap": None if rates["focused"] is None or rates["full"] is None else round(rates["focused"] - rates["full"], 4),
        "strict_pair": _strict_pair(cells),
        "strict_pair_full": _strict_pair([c for c in cells if (c.get("extra") or {}).get("track") == "full"]),
        "strict_pair_focused": _strict_pair([c for c in cells if (c.get("extra") or {}).get("track") == "focused"]),
        "strategy_lock_rate": _lock_rate(cells),
        "unauthorized_read_rate": _unauth_rate(cells),
        "decision": "",
    }
    payload["decision"] = _decision(rates)
    (out / "cell_table.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    report = [
        "# EXP-GM-REL1 TASK-REL1 Trust Formation and Update",
        "",
        f"- 时间：{payload['generated_at']}",
        "- 状态：pilot，不可排名",
        "- 路线：04a → 04b → 04c → I1 → REL1",
        "- 只评 Dispatcher 两轮结构化动作；猜对但无合法信任证据不算干净成功",
        "- 当前报告在 control/intervention 完全相同；唯一变化是历史谁被证明正确，以及反转后是否更新信任",
        "",
        "## 覆盖与主结果",
        "",
        f"- requested：{summary['requested']}",
        f"- measurement_valid：{summary['measurement_valid']}",
        f"- coverage：{summary['coverage']}",
        f"- oracle_conditioned FullPass：{summary['full_pass_rate']}",
        f"- target_correct（形成且更新）：{target_rate}",
        f"- StrictPair（全轨）：{payload['strict_pair']}；Focused {payload['strict_pair_focused']}；Full {payload['strict_pair_full']}",
        f"- 策略锁死率：{payload['strategy_lock_rate']}",
        f"- 未经授权读取率：{payload['unauthorized_read_rate']}",
        "",
        "### 分轨与价值",
        "",
        f"- Focused：{rates['focused']}",
        f"- Full：{rates['full']}（control {rates['full_control']} / intervention {rates['full_intervention']}）",
        f"- Drop-trust：{rates['drop_trust']}（control {rates['drop_control']} / intervention {rates['drop_intervention']}）",
        f"- No-history：{rates['no_history']}",
        f"- TrustDeliveryValue (Full − Drop)：{payload['trust_delivery_value']}",
        f"- HistoryValue (Full − NoHistory)：{payload['history_value']}",
        f"- TrustPropagationGap (Focused − Full)：{payload['trust_propagation_gap']}",
        "",
        "## 决策",
        "",
        payload["decision"],
        "",
        "| instance | valid | FullPass | formation | update | conditioned | first_error |",
        "|---|---|---|---|---|---|---|",
    ]
    for cell in summary["cells"]:
        extra = cell.get("extra") or {}
        report.append(
            f"| {cell.get('instance_id')} | {cell.get('measurement_valid')} | {cell.get('full_pass')} | "
            f"{extra.get('formation_correct')} | {extra.get('update_correct')} | "
            f"{extra.get('oracle_conditioned_success')} | "
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
                        f"formation={extra.get('formation_correct')} update={extra.get('update_correct')} "
                        f"first_error={(cell.get('process_profile') or {}).get('first_error')}",
                        flush=True,
                    )
    return cells


def main() -> int:
    ensure_import_paths()
    os.chdir(GAWORLD_ROOT)
    os.environ.setdefault("GAWORLD_LLM_PROVIDER", "paratera_glm")
    _pin_glm()
    out = BRIDGE_ROOT / "output" / "exp_rel1_20260824"
    out.mkdir(parents=True, exist_ok=True)
    print("phase=seed0", flush=True)
    cells = run_matrix(out, [0], mode="llm")
    payload = _pack(cells, out, phase="seed0")
    print((out / "REPORT.md").read_text(encoding="utf-8"))
    if payload["summary"]["coverage"] < 1.0 or payload["summary"]["measurement_valid"] < 24:
        print("seed0 未过测量门，停止补重复。", flush=True)
        return 1
    print("phase=repeats", flush=True)
    cells.extend(run_matrix(out, [1, 2], mode="llm"))
    payload = _pack(cells, out, phase="all")
    print((out / "REPORT.md").read_text(encoding="utf-8"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
