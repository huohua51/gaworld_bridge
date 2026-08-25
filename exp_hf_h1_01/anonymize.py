"""Convert Full-track functional runs into rater-safe anonymous traces."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

ROLE_MAP = {
    "T3": {"builder": "起草人", "reviewer": "审核员", "executor": "执行人"},
    "I1": {"observer": "观察员", "verifier": "核验员", "dispatcher": "调度员"},
    "L1": {"worker_a": "执行者甲", "coordinator": "协调员", "worker_b": "执行者乙"},
}

TASK_LABEL = {
    "t3_ho_queue_max_001": "窗口排队上限",
    "t3_ho_battery_pct_001": "电量下限告警",
    "t3_ho_noise_db_001": "噪声分贝上限",
    "pier_berth_001": "泊位占用报告",
    "pump_station_001": "泵站线路报告",
    "library_hours_001": "服务台开放报告",
    "l1_ho_crane_load_001": "三钩吊装吨位登记",
    "l1_ho_fridge_log_001": "三段冷柜温度点检",
    "l1_ho_mail_bay_001": "三阶段邮包接收核对入格",
}

VARIANT_CODE = {"control": "A", "intervention": "B"}

_STRIP = (
    re.compile(r"GLM-4-Flash", re.I),
    re.compile(r"paratera_glm", re.I),
    re.compile(r"/home/[^\\s\"']+", re.I),
    re.compile(r"holdout_[a-z0-9_]+", re.I),
    re.compile(r"EXP-GM-[A-Z0-9-]+"),
    re.compile(r"HO-GM-[A-Z0-9-]+"),
)


def _clean(text: str) -> str:
    out = text or ""
    for pat in _STRIP:
        out = pat.sub("[redacted]", out)
    return out


def _turn(t: int, role: str, kind: str, body: str, visible: str = "") -> dict[str, Any]:
    return {
        "t": t,
        "role": role,
        "kind": kind,
        "visible_to_role": visible,
        "body": _clean(body).strip(),
    }


def stimulus_id(construct: str, task_id: str, variant: str) -> str:
    short = {
        "t3_ho_queue_max_001": "queue",
        "t3_ho_battery_pct_001": "battery",
        "t3_ho_noise_db_001": "noise",
        "pier_berth_001": "pier",
        "pump_station_001": "pump",
        "library_hours_001": "library",
        "l1_ho_crane_load_001": "crane",
        "l1_ho_fridge_log_001": "fridge",
        "l1_ho_mail_bay_001": "mail",
    }[task_id]
    return f"h1dev-{construct.lower()}-{short}-{variant}"


def from_t3(run_dir: Path, *, task_id: str, variant: str) -> dict[str, Any]:
    roles = ROLE_MAP["T3"]
    before = (run_dir / "artifact_before.py").read_text(encoding="utf-8")
    after = (run_dir / "artifact_after.py").read_text(encoding="utf-8") if (run_dir / "artifact_after.py").is_file() else before
    review = json.loads((run_dir / "review_action.json").read_text(encoding="utf-8"))
    payload = json.loads((run_dir / "payload_trace.json").read_text(encoding="utf-8")) if (run_dir / "payload_trace.json").is_file() else {}
    envelope = payload.get("envelope") or {}
    decision = review.get("decision")
    evidence = review.get("evidence") or {}
    changes = review.get("required_changes") or []
    brief = TASK_LABEL[task_id]
    turns = [
        _turn(1, roles["builder"], "produce", before, "公开任务说明与当前草稿要求"),
        _turn(
            2,
            roles["reviewer"],
            "decide",
            json.dumps({"decision": decision, "evidence": evidence, "required_changes": changes}, ensure_ascii=False, indent=2),
            "草稿，以及本轮审核可见标准",
        ),
        _turn(
            3,
            roles["executor"],
            "apply",
            after,
            "草稿与审核意见（keep 则确认，update 则按 required_changes 修改）",
        ),
    ]
    return _pack("T3", task_id, variant, turns, brief, extra={"channel_delivered": not bool(payload.get("dropped")), "spec_version": envelope.get("spec_version")})


def from_i1(run_dir: Path, *, task_id: str, variant: str) -> dict[str, Any]:
    roles = ROLE_MAP["I1"]
    lines = (run_dir / "relay.jsonl").read_text(encoding="utf-8").splitlines()
    events = [json.loads(line) for line in lines if line.strip()]
    raw = [e["message"] for e in events if e.get("event") == "raw_sent"]
    verified = next((e.get("message") for e in events if e.get("event") == "verified_emitted"), None)
    action = next((e.get("action") for e in events if e.get("event") == "action_submitted"), None)
    action_view = {k: action.get(k) for k in ("action", "value", "adopted_state_version") if action}
    turns = [
        _turn(1, roles["observer"], "report", json.dumps([{"source_id": m.get("source_id"), "reported_state": m.get("reported_state")} for m in raw], ensure_ascii=False, indent=2), "两个来源的现场报告；不要判断谁可信"),
        _turn(2, roles["verifier"], "verify", json.dumps({k: (verified or {}).get(k) for k in ("verified_state", "source_id", "state_version")}, ensure_ascii=False, indent=2), "原始报告 + 私有可信来源表"),
        _turn(3, roles["dispatcher"], "act", json.dumps(action_view, ensure_ascii=False, indent=2), "已核实状态与动作规则；不能读私有可信表"),
    ]
    return _pack("I1", task_id, variant, turns, TASK_LABEL[task_id])


def from_l1(run_dir: Path, *, task_id: str, variant: str) -> dict[str, Any]:
    roles = ROLE_MAP["L1"]
    raw = json.loads((run_dir / "raw.json").read_text(encoding="utf-8"))
    events = []
    if (run_dir / "continuity.jsonl").is_file():
        events = [json.loads(line) for line in (run_dir / "continuity.jsonl").read_text(encoding="utf-8").splitlines() if line.strip()]
    interrupted = any(e.get("event") == "worker_unavailable" for e in events)
    step1 = _strip_fence(raw.get("step1") or "")
    ckpt = _strip_fence(raw.get("checkpoint") or "")
    handoff = _strip_fence(raw.get("handoff") or "")
    resume = _strip_fence(raw.get("resume") or "")
    step2 = _strip_fence(raw.get("step2") or "")
    step3 = _strip_fence(raw.get("step3") or "")
    successor = roles["worker_b"] if interrupted else roles["worker_a"]
    turns = [
        _turn(1, roles["worker_a"], "produce", step1, "任务步骤与第一步材料"),
        _turn(2, roles["worker_a"], "checkpoint", ckpt, "已完成第一步的结果；版本由平台盖章"),
        _turn(3, roles["coordinator"], "handoff", handoff, "检查点。不能执行具体步骤，不能给出剩余步骤的正确答案"),
    ]
    t = 4
    if interrupted:
        turns.append(_turn(t, roles["worker_a"], "unavailable", "执行者甲在第一里程碑后不可用。", "现场状态"))
        t += 1
    turns.append(_turn(t, successor, "resume", resume, "同一检查点与协调员接替指令"))
    t += 1
    turns.append(_turn(t, successor, "produce", step2, "当前应继续的步骤材料"))
    t += 1
    turns.append(_turn(t, successor, "produce", step3, "最后一步材料；不得覆盖已完成工作"))
    note = "变体 B：甲中断，乙从检查点继续。" if interrupted else "变体 A：甲仍在岗，从下一步继续。"
    return _pack("L1", task_id, variant, turns, TASK_LABEL[task_id], extra={"interrupted": interrupted, "variant_note_internal": note})


def _strip_fence(text: str) -> str:
    raw = (text or "").strip()
    if raw.startswith("```"):
        raw = re.sub(r"^```[a-zA-Z0-9_-]*\n?", "", raw)
        if raw.endswith("```"):
            raw = raw[:-3]
    return raw.strip()


def _pack(construct: str, task_id: str, variant: str, turns: list[dict[str, Any]], brief: str, extra: dict | None = None) -> dict[str, Any]:
    return {
        "stimulus_id": stimulus_id(construct, task_id, variant),
        "construct": construct,
        "task_label": brief,
        "variant_code": VARIANT_CODE[variant],
        "roles": list(ROLE_MAP[construct].values()),
        "turns": turns,
        "source_kind": "agent",
        "h1_role": "development_stimulus",
        "functional_role": "sealed_holdout_result",
        "not_future_h1_holdout": True,
        "rater_must_not_see": ["source_kind", "functional_role", "full_pass", "model", "experiment_id"],
        **({"internal": extra} if extra else {}),
    }


def rater_view(trace: dict[str, Any]) -> dict[str, Any]:
    return {
        "stimulus_id": trace["stimulus_id"],
        "construct": trace["construct"],
        "task_label": trace["task_label"],
        "variant_code": trace["variant_code"],
        "roles": trace["roles"],
        "turns": trace["turns"],
    }
