from __future__ import annotations

from pathlib import Path

from benchmark_core.model_runner import ModelCallBudget, RecordedModelRunner
from exp_rel1_02.fixture import fixture_client
from exp_rel1_02.loader import VARIANTS, load_tasks
from exp_rel1_02.protocol import run_cell
from exp_rel1_02.scorer import score_cell


def test_rel1_v2_fixture_passes_fresh_full_matrix(tmp_path: Path) -> None:
    budget = ModelCallBudget(30)
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
            cells.append(score_cell(task, variant, run_cell(task, variant, run_dir, runner)))

    assert budget.snapshot()["calls_used"] == 30
    assert all(cell["measurement_valid"] for cell in cells)
    assert all(cell["full_pass"] == 1 for cell in cells)
    assert all(cell["extra"]["formation_correct"] for cell in cells)
    assert all(cell["extra"]["update_correct"] for cell in cells)
    assert all(cell["extra"]["formation_action_bound"] for cell in cells)
    assert all(cell["extra"]["update_action_bound"] for cell in cells)
