from __future__ import annotations

from pathlib import Path

from benchmark_core.model_runner import ModelCallBudget, RecordedModelRunner
from exp_gm_c1_05.fixture import fixture_client
from exp_gm_c1_05.loader import VARIANTS, load_tasks
from exp_gm_c1_05.protocol import run_cell
from exp_gm_c1_05.scorer import score_cell


def test_c1_v5_fixture_passes_full_fresh_matrix(tmp_path: Path) -> None:
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
            cells.append(score_cell(task, variant, run_cell(task, variant, run_dir, runner)))

    assert budget.snapshot()["calls_used"] == 36
    assert all(cell["measurement_valid"] for cell in cells)
    assert all(cell["full_pass"] == 1 for cell in cells)
    intervention = [cell for cell in cells if cell["extra"]["variant"] == "intervention"]
    control = [cell for cell in cells if cell["extra"]["variant"] == "control"]
    assert all(cell["extra"]["priority_nack_path"] for cell in intervention)
    assert not any(cell["extra"]["priority_nack_path"] for cell in control)
    assert all(cell["extra"]["retry_recovery_success"] for cell in intervention)
