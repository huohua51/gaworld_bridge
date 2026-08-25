"""W2: R1 Artifact / Provenance gates on real GAWorld WorkAdapters."""

from __future__ import annotations

import os
import tempfile
from pathlib import Path

from v0_first_batch.paths import ensure_import_paths
from v0_first_batch.schema import CriterionResult, GateResult, compose, summarize_workflow

WORKFLOW_ID = "work_artifact_r1_001"
PLACEHOLDER_MARKERS = (
    "todo",
    "placeholder",
    "lorem ipsum",
    "xxx",
    "tbd",
    "以上由 ai",
    "coming soon",
)
HIDDEN_REFERENCE = "# Hidden Reference\n\nThis is the official answer key article.\n"


def _brief(deliverable: str, adapter: str):
    ensure_import_paths()
    from gaworld.work.schemas import WorkBrief

    return WorkBrief(
        task_id=f"wt_{deliverable}",
        agent_id=2,
        sim_day=1,
        sim_time="10:00",
        activity="工作",
        chosen_action="完成任务",
        deliverable=deliverable,
        adapter=adapter,
        brief_text="【任务】demo",
        estimated_minutes=20,
        submitted_at=1.0,
    )


def _ctx(tmp: str, llm):
    ensure_import_paths()
    from gaworld.work.adapters.base import AdapterContext

    return AdapterContext(artifacts_root=os.path.join(tmp, "art"), llm=llm, config={})


def _body_without_front_matter(text: str) -> str:
    if text.startswith("---"):
        parts = text.split("---", 2)
        if len(parts) >= 3:
            return parts[2].lstrip()
    return text


def _is_placeholder(text: str) -> bool:
    low = text.lower()
    return any(marker in low for marker in PLACEHOLDER_MARKERS)


def _score(instance_id: str, adapter, deliverable: str, llm, reference: str | None = None) -> dict:
    ensure_import_paths()
    tmp = tempfile.mkdtemp(prefix="gaw_r1_")
    result = adapter.run(_brief(deliverable, adapter.name), _ctx(tmp, llm))
    paths = list(result.artifact_paths or [])
    exists = bool(paths) and all(os.path.exists(p) for p in paths)
    text = ""
    if exists:
        text = Path(paths[0]).read_text(encoding="utf-8")
    body = _body_without_front_matter(text)
    nonempty = bool(body.strip())
    placeholder = _is_placeholder(body)
    copied = bool(reference) and reference.strip() and reference.strip() in body
    measurement = [
        GateResult("execution_valid", True, layer="R0", detail=f"adapter={adapter.name} status={result.status}"),
        GateResult("scorer_executable", True, layer="R0", detail="file existence and text checks"),
    ]
    artifact_gates = [
        GateResult("artifact_exists", exists and result.status == "ok", layer="R1", detail=str(paths)),
        GateResult("non_empty", nonempty, layer="R1", detail=f"chars={len(body)}"),
        GateResult("not_placeholder", not placeholder, layer="R1", detail="placeholder marker" if placeholder else "clean"),
        GateResult("not_copy_reference", not copied, layer="R1", detail="copied hidden reference" if copied else "no leak"),
    ]
    criteria = [
        CriterionResult(
            criterion_id="adapter_status_ok",
            layer="R2",
            scorer="exact",
            evaluable=True,
            score=1.0 if result.status == "ok" else 0.0,
            passed=result.status == "ok",
            critical=True,
            evidence_ids=paths,
            detail=result.error or result.summary or result.status,
        )
    ]
    return compose(
        workflow_id=WORKFLOW_ID,
        instance_id=instance_id,
        measurement_gates=measurement,
        artifact_gates=artifact_gates,
        criteria=criteria,
        extra={"status": result.status, "error": result.error, "artifact": paths[:1]},
    )


def run() -> dict:
    ensure_import_paths()
    from gaworld.work.adapters.code import CodeAdapter
    from gaworld.work.adapters.content import ContentAdapter
    from gaworld.work.adapters.teaching import TeachingAdapter
    from gaworld.work.adapters.web_design import WebDesignAdapter

    cells = [
        _score("content_ok", ContentAdapter(), "md_article", lambda _p: "# 标题\n\n## 段落\n\n正文。\n"),
        _score("content_empty", ContentAdapter(), "md_article", lambda _p: ""),
        _score("content_placeholder", ContentAdapter(), "md_article", lambda _p: "# TODO\n\nplaceholder coming soon\n"),
        _score(
            "content_copy_reference",
            ContentAdapter(),
            "md_article",
            lambda _p: HIDDEN_REFERENCE,
            reference=HIDDEN_REFERENCE,
        ),
        _score("code_ok", CodeAdapter(), "py_script", lambda _p: '"""demo"""\n\ndef add(a, b):\n    return a + b\n'),
        _score("code_syntax_fail", CodeAdapter(), "py_script", lambda _p: "def broken( :\n  pass\n"),
        _score(
            "web_html_ok",
            WebDesignAdapter(),
            "html_landing",
            lambda _p: "<!DOCTYPE html><html><head><style>body{color:red}</style></head><body><h1>Hi</h1></body></html>",
        ),
        _score("web_html_invalid", WebDesignAdapter(), "html_landing", lambda _p: "not html at all"),
        _score("teaching_ok", TeachingAdapter(), "lesson_plan", lambda _p: "# 课题\n\n## 教学目标\n- a\n"),
    ]
    return summarize_workflow(WORKFLOW_ID, cells)
