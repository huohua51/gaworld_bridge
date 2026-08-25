from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Callable

from cal_gm_c1_priority_02.contract import action_contract, parse_json_object
from cal_gm_c1_priority_02.loader import feasible_map, initial_assignments
from cal_gm_c1_priority_02.prompts import agent_prompt
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
    channel = JointAssignmentChannel(
        resource_id=str(task["resource_id"]),
        slots=list(task["slots"]),
        priority=list(task["priority"]),
        feasible=feasible_map(task, variant),
        max_retries=1,
        path=out_dir / "coord.jsonl",
    )
    initial = initial_assignments(task, variant)
    saved = channel.save_initial(initial)
    inspect = channel.inspect_violations()
    violations = list(inspect.get("violations") or [])
    prompt = agent_prompt(task, variant, violations=violations, retry=False)
    raw_text = generate_fn(prompt) or ""
    parsed = parse_json_object(raw_text)
    action, contract_error = action_contract(parsed)
    calls = 1
    propose = None
    retry_prompt = ""
    retry_raw = ""
    first_nack: list[dict[str, Any]] = []
    if contract_error == "ok":
        propose = channel.propose_joint_assignment("coordinator", action["assignments"])
        first_nack = list(propose.get("violations") or [])
        if not propose.get("accepted") and int(propose.get("retries_remaining") or 0) > 0:
            rejected = dict(propose.get("observed_assignments") or action.get("assignments") or {})
            retry_prompt = agent_prompt(
                task,
                variant,
                violations=list(propose.get("violations") or []),
                retry=True,
                rejected=rejected,
            )
            retry_raw = generate_fn(retry_prompt) or ""
            calls = 2
            parsed2 = parse_json_object(retry_raw)
            action2, err2 = action_contract(parsed2)
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
    env = channel.write_assignment(role="environment", assignments={"agent_a": "ENV", "agent_b": "ENV"})
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
    repair_slot = str(task["oracle"][variant]["assignments"]["agent_b"])
    nack_blob = json.dumps(first_nack) + json.dumps((propose or {}).get("violations") or [])
    inspect_blob = json.dumps(inspect)
    leaked = repair_slot in json.dumps(first_nack) or "suggested_slot" in inspect_blob or "suggested_slot" in nack_blob
    return {
        "instance_id": instance_id,
        "raw_text": raw_text if not retry_raw else raw_text + "\n---retry---\n" + retry_raw,
        "parsed": parsed or {},
        "action": action,
        "contract_error": contract_error,
        "contract_ok": contract_error == "ok",
        "prompt": prompt,
        "retry_prompt": retry_prompt,
        "calls": calls,
        "budget_valid": calls <= 2,
        "env_denied": env.get("reason") == "unauthorized_assignment_write",
        "leaked_repair_slot_in_nack": leaked,
        "channel": {
            "world": world,
            "inspect": inspect,
            "propose": propose,
            "unregistered_modification": world.get("unregistered_modification", 0),
            "actual_final_conflict_free": world.get("actual_final_conflict_free"),
            "assignments": world.get("assignments") or {},
            "initial": world.get("initial_assignments") or initial,
        },
    }
