"""W1: tighten GAWorld interview JSON into an R0/R1 contract gate.

Current interview_agent() falls back to pasting the same prose onto every
question when JSON parse fails. This workflow scores the tight contract:
1:1 question-answer mapping, no prose fallback, no identical-answer reuse.
"""

from __future__ import annotations

import json

from v0_first_batch.paths import ensure_import_paths
from v0_first_batch.schema import CriterionResult, GateResult, compose, summarize_workflow

WORKFLOW_ID = "contract_interview_001"
QUESTIONS = [
    "你今天为什么选择这个行动？",
    "你记得昨天的日程吗？",
    "如果工资降到保留线以下，你还会接受吗？",
]


def _parse(raw: str, questions: list[str]) -> list[dict]:
    ensure_import_paths()
    from generative_city_sim import _parse_interview

    return _parse_interview(raw, questions)


def _fallback_like_interview_agent(raw: str, questions: list[str]) -> tuple[list[dict], bool]:
    parsed = _parse(raw, questions)
    if parsed:
        return parsed, False
    fallback = raw.strip()
    if not fallback:
        return [], False
    return [{"question": q, "answer": fallback} for q in questions], True


def _score_instance(instance_id: str, raw: str, apply_runtime_fallback: bool) -> dict:
    measurement = [
        GateResult(
            gate_id="execution_valid",
            passed=True,
            layer="R0",
            detail="parser callable; raw text captured",
        )
    ]
    if apply_runtime_fallback:
        parsed, used_fallback = _fallback_like_interview_agent(raw, QUESTIONS)
    else:
        parsed, used_fallback = _parse(raw, QUESTIONS), False

    n = len(QUESTIONS)
    answers = [str(item.get("answer") or "").strip() for item in parsed]
    count_ok = len(parsed) == n
    reuse = n > 1 and len(set(answers)) <= 1 and all(answers)
    prose = bool(raw.strip()) and not parsed and not used_fallback

    r1_pass = count_ok and not used_fallback and not reuse and not prose
    artifact_gates = [
        GateResult(
            gate_id="json_shape_1to1",
            passed=count_ok,
            layer="R1",
            detail=f"parsed={len(parsed)} expected={n}",
        ),
        GateResult(
            gate_id="no_prose_fallback",
            passed=not used_fallback and not prose,
            layer="R1",
            detail="runtime reused one prose blob" if used_fallback else (
                "parser empty on nonempty prose" if prose else "structured parse"
            ),
        ),
        GateResult(
            gate_id="no_identical_answer_reuse",
            passed=not reuse,
            layer="R1",
            detail="same answer stamped on every question" if reuse else "answers differ or n=1",
        ),
    ]
    criteria = [
        CriterionResult(
            criterion_id="each_question_answered",
            layer="R2",
            scorer="exact",
            evaluable=True,
            score=float(sum(1 for a in answers if a)) / n,
            passed=count_ok and all(answers),
            critical=True,
            evidence_ids=[f"q{i}" for i in range(len(parsed))],
            detail=json.dumps(parsed, ensure_ascii=False)[:400],
        )
    ]
    return compose(
        workflow_id=WORKFLOW_ID,
        instance_id=instance_id,
        measurement_gates=measurement,
        artifact_gates=artifact_gates,
        criteria=criteria,
        process_profile={"parsed_count": len(parsed), "used_fallback": used_fallback},
        extra={"raw": raw, "parsed": parsed},
    )


def run() -> dict:
    valid = json.dumps(
        [
            {"question": QUESTIONS[0], "answer": "因为地铁更准时。"},
            {"question": QUESTIONS[1], "answer": "昨天上午在公司，晚上回家。"},
            {"question": QUESTIONS[2], "answer": "不会，低于保留工资就拒绝。"},
        ],
        ensure_ascii=False,
    )
    pair_array = json.dumps(
        [
            [QUESTIONS[0], "先完成已承诺的工作。"],
            [QUESTIONS[1], "记得，早八到晚六。"],
            [QUESTIONS[2], "低于底线就拒。"],
        ],
        ensure_ascii=False,
    )
    prose = "我今天心情不错，一切都还好，没有特别的安排。"
    partial = json.dumps(
        [
            {"question": QUESTIONS[0], "answer": "去上班。"},
            {"question": QUESTIONS[1], "answer": ""},
        ],
        ensure_ascii=False,
    )
    cells = [
        _score_instance("valid_object_json", valid, apply_runtime_fallback=False),
        _score_instance("valid_pair_array_json", pair_array, apply_runtime_fallback=False),
        _score_instance("prose_no_json", prose, apply_runtime_fallback=False),
        _score_instance("runtime_prose_fallback", prose, apply_runtime_fallback=True),
        _score_instance("partial_missing_answers", partial, apply_runtime_fallback=False),
    ]
    return summarize_workflow(WORKFLOW_ID, cells)
