from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Callable

from cal_gm_c1_repair_01.contract import action_contract, parse_json_object
from cal_gm_c1_repair_01.loader import feasible_map, initial_assignments
from cal_gm_c1_repair_01.prompts import agent_prompt
from gaworld.work.coordination import JointAssignmentChannel

GenerateFn = Callable[[str], str]


def _dump(path: Path, payload: Any) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def run_cell(
    *,
    task: dict[str, Any],
    variant: str,
    instance_id: str,
    out_dir: Path,
    generate_fn: GenerateFn,
) -> dict[str, Any]:
    out_dir.mkdir(parents=True, exist_ok=True)
    component = task["component"]
    if component != "C":
        prompt = agent_prompt(task, variant)
        raw_text = generate_fn(prompt) or ""
        parsed = parse_json_object(raw_text)
        action, contract_error = action_contract(component, parsed)
        (out_dir / "prompt.txt").write_text(prompt, encoding="utf-8")
        (out_dir / "raw.txt").write_text(raw_text, encoding="utf-8")
        _dump(out_dir / "parsed.json", parsed or {})
        _dump(out_dir / "action.json", action)
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
            "component": component,
            "channel": None,
        }

    coord_path = out_dir / "coord.jsonl"
    channel = JointAssignmentChannel(
        resource_id=str(task["resource_id"]),
        slots=list(task["slots"]),
        priority=list(task["priority"]),
        feasible=feasible_map(task, variant),
        max_retries=1,
        path=coord_path,
    )
    initial = initial_assignments(task, variant)
    saved = channel.save_initial(initial)
    inspect = channel.inspect_violations()
    violations = list(inspect.get("violations") or [])
    prompt = agent_prompt(task, variant, violations=violations, retry=False)
    raw_text = generate_fn(prompt) or ""
    parsed = parse_json_object(raw_text)
    action, contract_error = action_contract("C", parsed)
    calls = 1
    propose = None
    retry_prompt = ""
    retry_raw = ""
    if contract_error == "ok":
        propose = channel.propose_joint_assignment("coordinator", action["assignments"])
        if not propose.get("accepted") and int(propose.get("retries_remaining") or 0) > 0:
            retry_prompt = agent_prompt(task, variant, violations=list(propose.get("violations") or []), retry=True)
            retry_raw = generate_fn(retry_prompt) or ""
            calls = 2
            parsed2 = parse_json_object(retry_raw)
            action2, err2 = action_contract("C", parsed2)
            if err2 == "ok":
                propose = channel.propose_joint_assignment("coordinator", action2["assignments"])
                parsed = parsed2
                action = action2
                contract_error = err2
            else:
                parsed = parsed2
                action = action2
                contract_error = err2
    world = channel.world_state()
    (out_dir / "prompt.txt").write_text(prompt, encoding="utf-8")
    (out_dir / "raw.txt").write_text(raw_text, encoding="utf-8")
    if retry_prompt:
        (out_dir / "retry_prompt.txt").write_text(retry_prompt, encoding="utf-8")
        (out_dir / "retry_raw.txt").write_text(retry_raw, encoding="utf-8")
    _dump(out_dir / "parsed.json", parsed or {})
    _dump(out_dir / "action.json", action)
    _dump(out_dir / "inspect.json", inspect)
    _dump(out_dir / "propose.json", propose or {})
    _dump(out_dir / "world.json", world)
    _dump(out_dir / "initial.json", saved)
    return {
        "instance_id": instance_id,
        "raw_text": raw_text if not retry_raw else raw_text + "\n---retry---\n" + retry_raw,
        "parsed": parsed or {},
        "action": action,
        "contract_error": contract_error,
        "contract_ok": contract_error == "ok",
        "prompt": prompt,
        "calls": calls,
        "budget_valid": calls <= 2,
        "component": "C",
        "channel": {
            "world": world,
            "inspect": inspect,
            "propose": propose,
            "unregistered_modification": world.get("unregistered_modification", 0),
            "actual_final_conflict_free": world.get("actual_final_conflict_free"),
            "assignments": world.get("assignments") or {},
        },
    }
