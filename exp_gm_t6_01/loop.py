"""Execute one T6 longitudinal projection cell."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from gaworld.population.projection import PopulationProjectionEngine, TransitionSpec

from exp_gm_t6_01.loader import members_for


def _spec(task: dict[str, Any]) -> TransitionSpec:
    return TransitionSpec(
        metric=str(task["metric"]),
        persistence=float(task["persistence"]),
        subgroup_drift={
            str(group): float(value) for group, value in task["subgroup_drift"].items()
        },
        shocks={int(day): float(value) for day, value in task["shocks"].items()},
    )


def run_cell(
    task: dict[str, Any], mode: str, track: str, out_dir: Path
) -> dict[str, Any]:
    out_dir.mkdir(parents=True, exist_ok=True)
    trace_path = out_dir / "population_trace.jsonl"
    checkpoint_path = out_dir / "population_checkpoint.json"
    members = members_for(task)
    spec = _spec(task)
    engine = PopulationProjectionEngine(str(trace_path), members, spec, mode)
    days = int(task["days"])
    if track == "checkpoint_resume":
        engine.advance_to(days // 2)
        engine.save_checkpoint(str(checkpoint_path))
        engine = PopulationProjectionEngine.resume_from_checkpoint(
            str(trace_path), str(checkpoint_path), members, spec, mode
        )
    engine.advance_to(days)
    finished = engine.finish(days)
    return {
        "trace_path": str(trace_path),
        "checkpoint_path": str(checkpoint_path)
        if track == "checkpoint_resume"
        else None,
        "trace_nonempty": trace_path.is_file() and trace_path.stat().st_size > 0,
        "checkpoint_nonempty": (
            checkpoint_path.is_file() and checkpoint_path.stat().st_size > 0
            if track == "checkpoint_resume"
            else None
        ),
        "mode": mode,
        "track": track,
        "finished": finished,
        "summary": finished["summary"],
        "events": engine.event_names(),
    }
