from __future__ import annotations

from pathlib import Path

from benchmark_core.model_runner import ModelCallBudget, RecordedModelRunner
from exp_gm_c1_04.channel import CoordinationDeliveryChannel
from exp_gm_c1_04.fixture import fixture_client
from exp_gm_c1_04.loader import VARIANTS, load_tasks
from exp_gm_c1_04.protocol import run_cell
from exp_gm_c1_04.scorer import score_cell


def test_c1_v4_fixture_exercises_control_and_nack_retry(tmp_path: Path) -> None:
    budget = ModelCallBudget(36)
    cells = []
    for task in load_tasks():
        for variant in VARIANTS:
            run_dir = tmp_path / task["id"] / variant
            runner = RecordedModelRunner(
                run_dir / "model_trace.jsonl",
                fixture_client(),
                budget,
                temperature=0.0,
                allow_live_model=False,
                run_id=f"{task['id']}_{variant}",
            )
            loop = run_cell(task, variant, run_dir, runner)
            cells.append(score_cell(task=task, variant=variant, seed=0, loop=loop))

    assert budget.snapshot()["calls_used"] == 36
    assert all(cell["measurement_valid"] for cell in cells)
    assert all(cell["full_pass"] == 1 for cell in cells)
    interventions = [cell for cell in cells if cell["extra"]["variant"] == "intervention"]
    controls = [cell for cell in cells if cell["extra"]["variant"] == "control"]
    assert all(cell["extra"]["nack_path_coverage"] for cell in interventions)
    assert not any(cell["extra"]["nack_path_coverage"] for cell in controls)
    assert all(cell["extra"]["stale_plan_rejected"] for cell in cells)
    assert all(cell["extra"]["platform_identifier_ownership"] for cell in cells)


def test_delivery_rejects_unstamped_or_dropped_plan(tmp_path: Path) -> None:
    channel = CoordinationDeliveryChannel(tmp_path / "delivery.jsonl")
    denied = channel.deliver_accepted_plan({"assignments": {}})
    assert denied == {"ok": False, "reason": "accepted_platform_plan_required"}

    plan = {
        "plan_id": "plan-001",
        "spec_version": "spec-002",
        "assignments": {"agent_a": "x1", "agent_b": "x2"},
    }
    dropped = channel.deliver_accepted_plan(plan, drop=True)
    assert dropped == {"ok": True, "dropped": True}
    assert channel.read_plan("agent_a")["reason"] == "plan_not_delivered"
