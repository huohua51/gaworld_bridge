"""W7: agent_capability_test is a model quiz, not a workflow task."""

from __future__ import annotations

from v0_first_batch.paths import ensure_import_paths
from v0_first_batch.schema import CriterionResult, GateResult, compose, summarize_workflow

WORKFLOW_ID = "capability_quiz_not_workflow_001"


def run() -> dict:
    ensure_import_paths()
    import agent_capability_test as quiz

    bank = list(quiz.QUESTION_BANK)
    dimensions = sorted({item.get("dimension") for item in bank})
    measurement = [
        GateResult(
            "workflow_verifiability",
            False,
            layer="R0",
            detail="items are arithmetic/analogy/working-memory quizzes, not GAWorld deliverables",
        )
    ]
    cell = compose(
        workflow_id=WORKFLOW_ID,
        instance_id="question_bank_inspect",
        measurement_gates=measurement,
        artifact_gates=[],
        criteria=[
            CriterionResult(
                criterion_id="not_task_competence",
                layer="R2",
                scorer="rule",
                evaluable=False,
                score=None,
                detail="do not promote this bank into P1 Workflow Performance",
            )
        ],
        extra={"n_items": len(bank), "dimensions": dimensions},
    )
    cell["ranking_eligible"] = False
    summary = summarize_workflow(WORKFLOW_ID, [cell])
    summary["ranking_eligible"] = False
    summary["status"] = "placeholder"
    return summary
