from __future__ import annotations

from typing import Any

from cal_gm_l1_resume_01.loader import want_resume
from v0_first_batch.schema import CriterionResult, GateResult, compose

PASS_GATE = {
    "coverage": 1.0,
    "ResumeStepAccuracy": 1.0,
    "CompletedStepNotRepeated": 1.0,
    "RemainingStepNotSkipped": 1.0,
    "ResumeContractValid": 1.0,
    "StrictPair": 1.0,
}


def _flags(task: dict[str, Any], action: dict[str, Any], *, contract_ok: bool) -> dict[str, bool]:
    want = want_resume(task)
    resume = str(action.get("resume_step") or "")
    remaining = list(action.get("remaining_steps") or [])
    completed = list(action.get("completed_steps") or [])
    true_completed = list(want["completed_steps"])
    true_remaining = list(want["remaining_steps"])
    resume_ok = contract_ok and resume == want["resume_step"]
    not_repeated = contract_ok and resume not in set(true_completed)
    not_skipped = (
        contract_ok
        and remaining == true_remaining
        and remaining
        and remaining[0] == resume
        and not any(sid in remaining for sid in true_completed)
    )
    completed_echo = contract_ok and completed == true_completed
    return {
        "resume_ok": resume_ok,
        "not_repeated": not_repeated,
        "not_skipped": not_skipped,
        "completed_echo": completed_echo,
        "contract_ok": contract_ok,
    }


def first_error(*, contract_error: str, flags: dict[str, bool]) -> str:
    if contract_error != "ok":
        return str(contract_error)
    if not flags["completed_echo"]:
        return "completed_steps_misread"
    if not flags["not_repeated"]:
        return "completed_step_repeated"
    if not flags["resume_ok"]:
        return "resume_from_wrong_step"
    if not flags["not_skipped"]:
        return "remaining_step_skipped"
    return "none"


def score_cell(
    *,
    task: dict,
    variant: str,
    repeat_id: int,
    loop: dict[str, Any],
    workflow_id: str,
    instance_id: str,
) -> dict[str, Any]:
    action = loop.get("action") or {}
    extractable = True
    contract_ok = bool(loop.get("contract_ok"))
    flags = _flags(task, action, contract_ok=contract_ok)
    r0 = (
        extractable
        and bool(loop.get("budget_valid"))
        and loop.get("calls") == 1
        and bool(loop.get("coordinator_exec_denied", True))
        and bool(loop.get("env_denied", True))
    )
    conditioned = bool(r0 and flags["contract_ok"] and flags["resume_ok"] and flags["not_repeated"] and flags["not_skipped"] and flags["completed_echo"])
    err = first_error(contract_error=str(loop.get("contract_error") or "empty"), flags=flags)
    if conditioned:
        err = "none"
    cell = compose(
        workflow_id=workflow_id,
        instance_id=instance_id,
        measurement_gates=[
            GateResult("execution_valid", r0, layer="R0"),
            GateResult("fields_extractable", extractable, layer="R0"),
            GateResult("single_call", loop.get("calls") == 1, layer="R0"),
            GateResult("coordinator_did_not_execute", bool(loop.get("coordinator_exec_denied", True)), layer="R0"),
            GateResult("environment_did_not_rewrite", bool(loop.get("env_denied", True)), layer="R0"),
            GateResult("eval_mode_on", True, layer="R0"),
        ],
        artifact_gates=[GateResult("resume_json_exists", bool(action), layer="R1")],
        criteria=[
            CriterionResult("resume_contract_valid", "R2", "resume_oracle", True, 1.0 if flags["contract_ok"] else 0.0, passed=flags["contract_ok"]),
            CriterionResult("resume_step_accuracy", "R2", "resume_oracle", True, 1.0 if flags["resume_ok"] else 0.0, passed=flags["resume_ok"]),
            CriterionResult("completed_step_not_repeated", "R2", "resume_oracle", True, 1.0 if flags["not_repeated"] else 0.0, passed=flags["not_repeated"]),
            CriterionResult("remaining_step_not_skipped", "R2", "resume_oracle", True, 1.0 if flags["not_skipped"] else 0.0, passed=flags["not_skipped"]),
            CriterionResult("oracle_conditioned_success", "R3", "resume_oracle", True, 1.0 if conditioned else 0.0, passed=conditioned, critical=True),
        ],
        process_profile={"first_error": err, "contract_error": loop.get("contract_error"), "action": action},
        extra={
            "task_id": task["id"],
            "variant": variant,
            "repeat_id": repeat_id,
            "resume_contract_valid": flags["contract_ok"],
            "resume_step_accuracy": flags["resume_ok"],
            "completed_step_not_repeated": flags["not_repeated"],
            "remaining_step_not_skipped": flags["not_skipped"],
            "action": action,
            "want": want_resume(task),
            "first_error": err,
        },
    )
    cell["ranking_eligible"] = False
    return cell


def _valid(cells: list[dict], variant: str | None = None) -> list[dict]:
    out = []
    for cell in cells:
        extra = cell.get("extra") or {}
        if variant is not None and extra.get("variant") != variant:
            continue
        if cell.get("measurement_valid"):
            out.append(cell)
    return out


def _mean_flag(cells: list[dict], field: str) -> float | None:
    if not cells:
        return None
    return round(sum(int(bool((c.get("extra") or {}).get(field))) for c in cells) / len(cells), 4)


def coverage(cells: list[dict]) -> float:
    if not cells:
        return 0.0
    return round(sum(int(bool(c.get("measurement_valid"))) for c in cells) / len(cells), 4)


def strict_pair(cells: list[dict]) -> float | None:
    groups: dict[tuple[Any, Any], dict[str, dict]] = {}
    for cell in cells:
        extra = cell.get("extra") or {}
        key = (extra.get("task_id"), extra.get("repeat_id"))
        groups.setdefault(key, {})[str(extra.get("variant"))] = cell
    pairs = [g for g in groups.values() if "control" in g and "intervention" in g]
    if not pairs:
        return None
    n_ok = sum(1 for pair in pairs if pair["control"].get("full_pass") == 1 and pair["intervention"].get("full_pass") == 1)
    return round(n_ok / len(pairs), 4)


def metrics(cells: list[dict]) -> dict[str, Any]:
    valid = _valid(cells)
    rates = {
        "Coverage": coverage(cells),
        "ResumeStepAccuracy": _mean_flag(valid, "resume_step_accuracy"),
        "CompletedStepNotRepeated": _mean_flag(valid, "completed_step_not_repeated"),
        "RemainingStepNotSkipped": _mean_flag(valid, "remaining_step_not_skipped"),
        "ResumeContractValid": _mean_flag(valid, "resume_contract_valid"),
        "StrictPair": strict_pair(cells),
        "control_fullpass": _mean_flag(_valid(cells, "control"), "resume_step_accuracy"),
        "intervention_fullpass": _mean_flag(_valid(cells, "intervention"), "resume_step_accuracy"),
    }
    gate = {
        "coverage_ok": rates["Coverage"] == PASS_GATE["coverage"],
        "resume_ok": rates["ResumeStepAccuracy"] == PASS_GATE["ResumeStepAccuracy"],
        "not_repeated_ok": rates["CompletedStepNotRepeated"] == PASS_GATE["CompletedStepNotRepeated"],
        "not_skipped_ok": rates["RemainingStepNotSkipped"] == PASS_GATE["RemainingStepNotSkipped"],
        "contract_ok": rates["ResumeContractValid"] == PASS_GATE["ResumeContractValid"],
        "strict_ok": rates["StrictPair"] == PASS_GATE["StrictPair"],
    }
    gate["holds"] = all(gate.values()) and all(v is not None for v in rates.values())
    return {"rates": rates, "pass_gate": gate}
