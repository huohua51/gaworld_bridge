"""Scorer must fail missing artifacts and pass a correct stub script."""

from __future__ import annotations

from pathlib import Path

from exp_gm_04.scorer import score_hidden_tests
from exp_gm_04.tasks import TASKS


def test_missing_artifact_is_not_evaluable():
    oracle = TASKS[0]["oracle"]
    out = score_hidden_tests(None, oracle)
    assert out["evaluable"] is False
    assert out["first_error"] == "no_artifact"


def test_correct_wage_gate_passes(tmp_path: Path):
    script = tmp_path / "main.py"
    script.write_text(
        'def decide(reservation_wage, take_home):\n'
        '    return "accept" if take_home >= reservation_wage else "reject"\n',
        encoding="utf-8",
    )
    out = score_hidden_tests(str(script), TASKS[0]["oracle"])
    assert out["passed"] is True
    assert out["pass_count"] == 4
