"""Rule negative controls for 04e-R. Reviewer only."""

from __future__ import annotations

from pathlib import Path

from exp_gm_04c.roles import render_source
from exp_gm_04e.loop import run_reviewer_cell
from exp_gm_04e.roles import evidence_prompt, facts_for, legacy_prompt, rule_reviewer
from exp_gm_04e.tasks import TASKS
from gaworld.work.artifact_facts import nack_payload

_HELDOUT = ("shipping_threshold", "eligibility_age", "inventory_reorder_point")


def _run(tmp: Path, task: dict, variant: str, protocol: str, reviewer=None):
    def _default(source, private, extra):
        return rule_reviewer(task, source, private, protocol=protocol)

    return run_reviewer_cell(
        task=task,
        variant=variant,
        protocol=protocol,
        task_id=f"{task['id']}_{variant}_{protocol}_rule",
        out_dir=tmp / f"{task['id']}_{variant}_{protocol}",
        reviewer_fn=reviewer or _default,
    )


def test_nack_leaks_no_oracle():
    text = str(nack_payload())
    assert "70000" not in text
    assert "0.5" not in text
    assert "accepted" in text
    assert "mismatch evidence is not supported by the current artifact" in text


def test_rule_evidence_bound_control_approves(tmp_path: Path):
    loop = _run(tmp_path, TASKS[0], "control", "evidence_bound")
    assert loop["review"]["decision"] == "approve"
    assert loop["false_positive_revision"] is False
    assert loop["grounded"] is True
    assert loop["first_error"] == "none"
    assert loop["reviewer_calls"] == 1


def test_rule_evidence_bound_intervention_revises(tmp_path: Path):
    loop = _run(tmp_path, TASKS[0], "intervention", "evidence_bound")
    assert loop["review"]["decision"] == "revise"
    assert loop["true_revision"] is True
    assert loop["grounded"] is True
    assert loop["reviewer_calls"] == 1


def test_rule_all_dev_tasks_both_protocols(tmp_path: Path):
    for task in TASKS:
        control = _run(tmp_path, task, "control", "evidence_bound")
        intervention = _run(tmp_path, task, "intervention", "evidence_bound")
        assert control["review"]["decision"] == "approve"
        assert control["grounded"] is True
        assert intervention["true_revision"] is True
        assert intervention["grounded"] is True


def test_rule_legacy_matches_04c_shape(tmp_path: Path):
    control = _run(tmp_path, TASKS[0], "control", "legacy")
    intervention = _run(tmp_path, TASKS[0], "intervention", "legacy")
    assert control["review"]["decision"] == "approve"
    assert intervention["review"]["decision"] == "revise"
    assert intervention["true_revision"] is True
    assert control["reviewer_calls"] == 1


def test_fabricated_observed_is_rejected_and_draft_untouched(tmp_path: Path):
    extras: list[str] = []

    def reviewer(source, private, extra):
        extras.append(extra)
        return {
            "decision": "revise",
            "mismatches": [
                {
                    "criterion_id": "reservation_wage_threshold",
                    "fact_id": "fact-02",
                    "observed_value": 1,
                    "required_value": 70000,
                    "operator": "equals",
                }
            ],
        }

    loop = _run(tmp_path, TASKS[0], "intervention", "evidence_bound", reviewer=reviewer)
    assert loop["grounded"] is False
    assert loop["first_error"] == "observed_value_false"
    assert loop["reviewer_calls"] == 2
    assert extras[0] == ""
    assert "70000" not in extras[1]
    assert "accepted" in extras[1].lower() or '"accepted": false' in extras[1].lower()
    assert extras[1].count("70000") == 0
    draft = (tmp_path / f"{TASKS[0]['id']}_intervention_evidence_bound" / "draft_main.py").read_text(encoding="utf-8")
    assert "THRESHOLD = 60000" in draft
    assert "THRESHOLD = 70000" not in draft
    assert loop["source"] == render_source(TASKS[0], "v1")


def test_control_invented_mismatch_is_rejected(tmp_path: Path):
    def reviewer(source, private, extra):
        return {
            "decision": "revise",
            "mismatches": [
                {
                    "criterion_id": "reservation_wage_threshold",
                    "fact_id": "fact-02",
                    "observed_value": 60000,
                    "required_value": 70000,
                    "operator": "equals",
                }
            ],
        }

    loop = _run(tmp_path, TASKS[0], "control", "evidence_bound", reviewer=reviewer)
    assert loop["grounded"] is False
    assert loop["false_positive_revision"] is True
    assert loop["first_error"] == "required_value_not_registered"


def test_public_facts_omit_required_value():
    source = render_source(TASKS[0], "v1")
    facts = facts_for(TASKS[0], source)
    public = [item.to_public_dict() for item in facts]
    blob = str(public)
    assert "70000" not in blob
    assert all("required_value" not in item for item in public)


def test_protocol_templates_omit_heldout_fields():
    source = render_source(TASKS[0], "v1")
    private = {"criterion_id": "reservation_wage_threshold", "required_change": {"reservation_wage": 60000}}
    prompts = [
        evidence_prompt(source, facts_for(TASKS[0], source), private),
        legacy_prompt(source, private),
        Path("/home/wuxingye/projects/gaworld_eval_bridge/exp_gm_04e/roles.py").read_text(encoding="utf-8"),
        Path("/home/wuxingye/projects/gaworld_eval_bridge/exp_gm_04e/loop.py").read_text(encoding="utf-8"),
    ]
    for text in prompts:
        for token in _HELDOUT:
            assert token not in text
