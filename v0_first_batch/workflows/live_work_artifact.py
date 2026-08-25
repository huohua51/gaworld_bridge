"""Live GLM WorkAdapter R1: produce real artifacts, then gate them.

R1 pass means a legal deliverable was filed. It is not Task Competence.
"""

from __future__ import annotations

import os
from pathlib import Path

from v0_first_batch.paths import GAWORLD_ROOT, ensure_import_paths
from v0_first_batch.schema import CriterionResult, GateResult, compose, summarize_workflow
from v0_first_batch.workflows.work_artifact_r1 import (
    PLACEHOLDER_MARKERS,
    _body_without_front_matter,
    _is_placeholder,
)

WORKFLOW_ID = "live_work_artifact_r1_001"
DEFAULT_OUT = (
    Path(__file__).resolve().parents[2] / "output" / "live_run_20260823" / "work"
)


def _llm(prompt: str) -> str:
    ensure_import_paths()
    from config import CONFIG
    from llm_providers import LLMRouter

    providers = CONFIG.setdefault("llm", {}).setdefault("providers", {})
    glm = providers.setdefault("paratera_glm", {})
    if isinstance(glm, dict):
        glm["max_tokens"] = max(int(glm.get("max_tokens") or 0), 2048)
    routing = CONFIG.setdefault("llm", {}).setdefault("routing", {})
    routing["default"] = "paratera_glm"
    tasks = dict(routing.get("tasks") or {})
    tasks["schedule"] = "paratera_glm"
    routing["tasks"] = tasks
    return LLMRouter(CONFIG).call(prompt, task="interview") or ""


def _brief(task_id: str, deliverable: str, adapter: str, brief_text: str):
    from gaworld.work.schemas import WorkBrief

    return WorkBrief(
        task_id=task_id,
        agent_id=4,
        sim_day=1,
        sim_time="10:00",
        activity="工作",
        chosen_action="完成任务",
        deliverable=deliverable,
        adapter=adapter,
        brief_text=brief_text,
        estimated_minutes=20,
        submitted_at=1.0,
    )


def _score_live(instance_id: str, adapter, deliverable: str, brief_text: str, out_root: Path) -> dict:
    ensure_import_paths()
    from gaworld.work.adapters.base import AdapterContext

    brief = _brief(instance_id, deliverable, adapter.name, brief_text)
    ctx = AdapterContext(artifacts_root=str(out_root / "artifacts"), llm=_llm, config={})
    result = adapter.run(brief, ctx)
    paths = list(result.artifact_paths or [])
    exists = bool(paths) and all(os.path.exists(p) for p in paths)
    text = Path(paths[0]).read_text(encoding="utf-8") if exists else ""
    body = _body_without_front_matter(text)
    placeholder = _is_placeholder(body)
    measurement = [
        GateResult("execution_valid", True, layer="R0", detail=f"live GLM adapter={adapter.name}"),
        GateResult("scorer_executable", True, layer="R0", detail="file existence and placeholder checks"),
    ]
    artifact = [
        GateResult("artifact_exists", exists and result.status == "ok", layer="R1", detail=str(paths)),
        GateResult("non_empty", bool(body.strip()), layer="R1", detail=f"chars={len(body)}"),
        GateResult("not_placeholder", not placeholder, layer="R1", detail="placeholder" if placeholder else "clean"),
        GateResult(
            "hash_not_forbidden",
            True,
            critical=False,
            layer="R1",
            detail="not_enabled: no sealed reference blacklist",
        ),
    ]
    return compose(
        workflow_id=WORKFLOW_ID,
        instance_id=instance_id,
        measurement_gates=measurement,
        artifact_gates=artifact,
        criteria=[
            CriterionResult(
                criterion_id="artifact_gate_pass",
                layer="R1",
                scorer="rule",
                evaluable=True,
                score=1.0 if result.status == "ok" and exists and body.strip() and not placeholder else 0.0,
                passed=result.status == "ok" and exists and bool(body.strip()) and not placeholder,
                critical=True,
                evidence_ids=paths,
                detail=result.error or result.summary or result.status,
            )
        ],
        extra={
            "status": result.status,
            "error": result.error,
            "summary": result.summary,
            "artifact_paths": paths,
            "chars": len(body),
            "note": "artifact_gate_pass only; no hidden reference / domain verifier",
        },
    )


def run(out_root: Path | None = None) -> dict:
    ensure_import_paths()
    os.chdir(GAWORLD_ROOT)
    from gaworld.work.adapters.code import CodeAdapter
    from gaworld.work.adapters.content import ContentAdapter
    from gaworld.work.adapters.teaching import TeachingAdapter

    out_root = Path(out_root or DEFAULT_OUT)
    out_root.mkdir(parents=True, exist_ok=True)
    cells = [
        _score_live(
            "content_md_article",
            ContentAdapter(),
            "md_article",
            "【创作者】许曼婷\n【职业】新媒体运营\n【调性】克制、观察城市日常\n【任务】写一篇杭州滨江骑行通勤观察\n用两个小节写早高峰和晚间回程，避免空话。",
            out_root,
        ),
        _score_live(
            "teaching_lesson_plan",
            TeachingAdapter(),
            "lesson_plan",
            "【教师】王思远\n【职业】产品经理转兼职讲师\n【任务】一节 45 分钟的数据分析入门课\n对象是零基础新媒体同学，教学目标要可检查。",
            out_root,
        ),
        _score_live(
            "code_py_script",
            CodeAdapter(),
            "py_script",
            "【工程师】王思远\n【职业】产品经理\n【任务】写一个独立 Python 脚本，计算两组整数的保留工资决策\n输入保留工资和到手月薪，输出 accept 或 reject；带一个可运行的 main。",
            out_root,
        ),
    ]
    summary = summarize_workflow(WORKFLOW_ID, cells)
    summary["note"] = (
        "Live GLM-4-Flash WorkAdapter R1. Legal deliverable only; "
        "not Task Competence / FullPass of a work workflow."
    )
    return summary
