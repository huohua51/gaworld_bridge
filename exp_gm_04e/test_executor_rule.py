"""Rule negative controls for 04e-E. Executor only."""

from __future__ import annotations

from pathlib import Path

from exp_gm_04c.roles import render_source
from exp_gm_04e.executor import executor_prompt, rule_executor, typed_patches
from exp_gm_04e.loop_e import run_executor_cell
from exp_gm_04e.tasks import TASKS
from exp_gm_04.scorer import score_hidden_tests

_HELDOUT = ("shipping_threshold", "eligibility_age", "inventory_reorder_point")


def _run(tmp: Path, task: dict, protocol: str, executor=None):
    def _default(source: str) -> str:
        return rule_executor(task, protocol=protocol, source=source)

    return run_executor_cell(
        task=task,
        protocol=protocol,
        task_id=f"{task['id']}_{protocol}_rule",
        out_dir=tmp / f"{task['id']}_{protocol}",
        executor_fn=executor or _default,
    )


def test_rule_applies_all_dev_tasks(tmp_path: Path):
    for task in TASKS:
        for protocol in ("legacy", "evidence_bound"):
            loop = _run(tmp_path, task, protocol)
            assert loop["patch_applied"] is True
            assert loop["first_error"] == "none"
            final = tmp_path / f"{task['id']}_{protocol}" / "final_main.py"
            assert score_hidden_tests(str(final), task["v2"]["oracle"])["passed"] is True
            assert score_hidden_tests(str(final), task["v1"]["oracle"])["passed"] is False


def test_version_only_executor_is_caught(tmp_path: Path):
    task = TASKS[1]

    def executor(source: str) -> str:
        return source.replace('SPEC_VERSION = "v1"', 'SPEC_VERSION = "v2"')

    loop = _run(tmp_path, task, "evidence_bound", executor=executor)
    assert loop["patch_applied"] is False
    assert loop["first_error"] == "version_only_updated"
    assert "RATE = 0.3" in loop["after"]


def test_environment_does_not_rewrite_failed_executor(tmp_path: Path):
    task = TASKS[0]

    def executor(source: str) -> str:
        return source

    loop = _run(tmp_path, task, "evidence_bound", executor=executor)
    assert loop["after"] == render_source(task, "v1")
    assert "THRESHOLD = 70000" not in loop["after"]
    assert loop["first_error"] == "patch_not_read"


def test_typed_patch_has_one_value_field():
    task = TASKS[0]
    patches = typed_patches(task, render_source(task, "v1"))
    assert len(patches) == 1
    assert patches[0]["path"] == "reservation_wage"
    assert patches[0]["required_value"] == 70000
    assert patches[0]["observed_value"] == 60000


def test_executor_prompts_omit_heldout_fields():
    task = TASKS[0]
    source = render_source(task, "v1")
    for protocol in ("legacy", "evidence_bound"):
        text = executor_prompt(task, source, protocol=protocol)
        for token in _HELDOUT:
            assert token not in text
        assert "70000" in text  # correct patch may name required_value
        assert "shipping" not in text
