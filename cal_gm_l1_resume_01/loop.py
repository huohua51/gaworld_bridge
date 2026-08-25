from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Callable

from cal_gm_l1_resume_01.contract import parse_json_object, resume_contract
from gaworld.work.continuity import WorkflowCheckpointChannel

GenerateFn = Callable[[str], str]


def run_cell(
    *,
    task: dict[str, Any],
    variant: str,
    instance_id: str,
    out_dir: Path,
    prompt: str,
    generate_fn: GenerateFn,
) -> dict[str, Any]:
    out_dir.mkdir(parents=True, exist_ok=True)
    channel = WorkflowCheckpointChannel(step_ids=list(task["step_ids"]), path=out_dir / "continuity.jsonl")
    raw_text = generate_fn(prompt) or ""
    parsed = parse_json_object(raw_text)
    action, contract_error = resume_contract(parsed)
    stolen = channel.execute_step(role="coordinator", step_id=task["step_ids"][1], output={"stolen": True})
    env = channel.write_world(role="environment", path=out_dir / "world.json", content="ENVIRONMENT_REWRITE")
    (out_dir / "prompt.txt").write_text(prompt, encoding="utf-8")
    (out_dir / "raw.txt").write_text(raw_text, encoding="utf-8")
    (out_dir / "parsed.json").write_text(json.dumps(parsed or {}, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (out_dir / "action.json").write_text(json.dumps(action, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return {
        "instance_id": instance_id,
        "raw_text": raw_text,
        "parsed": parsed or {},
        "action": action,
        "contract_error": contract_error,
        "contract_ok": contract_error == "ok",
        "prompt": prompt,
        "calls": 1,
        "budget_valid": True,
        "coordinator_exec_denied": stolen.get("ok") is False,
        "env_denied": env.get("ok") is False,
    }
