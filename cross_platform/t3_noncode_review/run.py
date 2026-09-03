"""Run the preregistered paired GAWorld/YuLan non-code T3 experiment."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
from copy import deepcopy
from pathlib import Path
from typing import Any

import yaml

from benchmark_core.eval_mode import capture_eval_mode_evidence
from benchmark_core.model_runner import (
    GAWorldModelClient,
    ModelCallBudget,
    ModelClient,
    RecordedModelRunner,
)
from v0_first_batch.paths import BRIDGE_ROOT, ensure_import_paths

ensure_import_paths()

from cross_platform.t3_noncode_review.fixture import oracle_fixture_client
from cross_platform.t3_noncode_review.gaworld_adapter import run_cell as run_gaworld
from cross_platform.t3_noncode_review.protocol import (
    PROTOCOL,
    ROLES,
    TASK_IDS,
    VARIANTS,
    load_tasks,
)
from cross_platform.t3_noncode_review.scorer import SCORER_VERSION, score_cell
from cross_platform.t3_noncode_review.yulan_adapter import run_cell as run_yulan

REGISTRATION_PATH = Path(__file__).with_name("registration_t3_noncode_glm52.yaml")
YULAN_ROOT = Path(r"F:\proj\YuLan-OneSim-official")
YULAN_COMMIT = "9829d722b528b733f8c8317315637071fa23b206"
GAWORLD_REVIEW = Path(r"F:\proj\GAWorld\gaworld\work\review.py")
PLATFORMS = ("GAWorld", "YuLan-OneSim")
MAX_CALLS = 36
MAX_TOKENS = 256
TEMPERATURE = 0.0
THINKING = "disabled"


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _registration() -> tuple[dict[str, Any], str]:
    payload = yaml.safe_load(REGISTRATION_PATH.read_text(encoding="utf-8")) or {}
    errors: list[str] = []
    for relative, expected in (payload.get("frozen_inputs") or {}).items():
        path = BRIDGE_ROOT / str(relative)
        if not path.is_file():
            errors.append(f"missing:{relative}")
        elif _sha256(path) != str(expected):
            errors.append(f"sha256_mismatch:{relative}:{_sha256(path)}")
    design = payload.get("design") or {}
    registered = {
        "task_ids": tuple(design.get("task_ids") or ()),
        "variants": tuple(design.get("variants") or ()),
        "platforms": tuple(design.get("platforms") or ()),
        "roles": tuple(design.get("roles") or ()),
        "cells": int(design.get("cells") or 0),
        "max_calls": int(design.get("max_calls") or 0),
        "prompt_protocol": str(design.get("prompt_protocol") or ""),
        "scorer_version": str(design.get("scorer_version") or ""),
    }
    actual = {
        "task_ids": TASK_IDS,
        "variants": VARIANTS,
        "platforms": PLATFORMS,
        "roles": ROLES,
        "cells": len(TASK_IDS) * len(VARIANTS) * len(PLATFORMS),
        "max_calls": MAX_CALLS,
        "prompt_protocol": PROTOCOL,
        "scorer_version": SCORER_VERSION,
    }
    for key, expected in actual.items():
        if registered[key] != expected:
            errors.append(f"registered_{key}_mismatch:{registered[key]}!={expected}")
    actual_commit = subprocess.run(
        ["git", "-C", str(YULAN_ROOT), "rev-parse", "HEAD"],
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
    if actual_commit != YULAN_COMMIT:
        errors.append(f"yulan_commit_mismatch:{actual_commit}")
    registered_review_hash = str(
        ((payload.get("systems") or {}).get("gaworld") or {}).get(
            "review_channel_sha256", ""
        )
    )
    if _sha256(GAWORLD_REVIEW) != registered_review_hash:
        errors.append("gaworld_review_channel_hash_mismatch")
    if errors:
        raise RuntimeError("preregistration validation failed: " + ",".join(errors))
    return payload, _sha256(REGISTRATION_PATH)


def _eval_evidence() -> dict[str, Any]:
    from config import CONFIG

    config = deepcopy(CONFIG)
    config.setdefault("eval_mode", {})["enabled"] = True
    return capture_eval_mode_evidence(config)


def _criterion(cell: dict[str, Any], criterion_id: str) -> bool:
    return bool(
        next(item for item in cell["criteria"] if item["criterion_id"] == criterion_id)[
            "passed"
        ]
    )


def _paired_comparison(
    task_id: str,
    variant: str,
    by_key: dict[tuple[str, str, str], dict[str, Any]],
) -> dict[str, Any]:
    gaworld = by_key[(task_id, variant, "GAWorld")]
    yulan = by_key[(task_id, variant, "YuLan-OneSim")]
    ga_process = gaworld["process_profile"]
    yu_process = yulan["process_profile"]
    return {
        "task_id": task_id,
        "variant": variant,
        "prompt_hashes_exact": (
            gaworld["extra"]["prompt_sha256_by_role"]
            == yulan["extra"]["prompt_sha256_by_role"]
        ),
        "role_outputs_exact": (
            gaworld["extra"]["role_outputs"] == yulan["extra"]["role_outputs"]
        ),
        "proposal_exact": ga_process["proposal"] == yu_process["proposal"],
        "review_exact": ga_process["review"] == yu_process["review"],
        "executor_exact": (
            ga_process["executor_output"] == yu_process["executor_output"]
        ),
        "final_state_exact": (
            ga_process["executor_output"].get("final_state")
            == yu_process["executor_output"].get("final_state")
        ),
        "full_pass_exact": gaworld["full_pass"] == yulan["full_pass"],
        "gaworld_full_pass": gaworld["full_pass"],
        "yulan_full_pass": yulan["full_pass"],
    }


def _write_report(out: Path, report: dict[str, Any]) -> None:
    lines = [
        "# T3 非代码独立审核：GAWorld / YuLan-OneSim 同面实验",
        "",
        f"- 阶段：`{report['phase']}`",
        f"- 门禁：`{report['gate']}`",
        f"- 模型：`{report['provider']} / {report['model_version']}`",
        f"- 单元：{report['n_cells']}；调用：{report['budget']['calls_used']}/{report['budget']['max_calls']}",
        f"- GAWorld FullPass：{report['platform_summary']['GAWorld']['full_pass_rate']}",
        f"- YuLan-OneSim FullPass：{report['platform_summary']['YuLan-OneSim']['full_pass_rate']}",
        f"- 跨平台提示词逐角色完全一致：{report['exact_matches']['prompt_hashes_exact']}/{report['exact_matches']['denominator']}",
        f"- 跨平台三角色输出完全一致：{report['exact_matches']['role_outputs_exact']}/{report['exact_matches']['denominator']}",
        "",
        "## 结果边界",
        "",
        "这是三类新非代码任务、两种证据条件和单一模型的一轮协议同面对照。它测量提案—独立审核—采纳/拒绝—状态更新链，不代表全部 T3，更不构成平台总排名。",
        "GAWorld 的原生审核通道只接受 approve/revise；本适配器把共同语义中的 reject 作为 revise 载体传递，并在执行者提示前还原为 reject。YuLan 使用锁定提交的原生 EventBus，任务语义与判分规则均由 Benchmark 冻结。",
        "",
    ]
    (out / "REPORT.md").write_text("\n".join(lines), encoding="utf-8")


def run_matrix(
    out: Path,
    client: ModelClient,
    *,
    allow_live_model: bool,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    registration, registration_sha256 = _registration()
    if client.info.live:
        provider = registration["provider"]
        if (
            client.info.provider != provider["name"]
            or client.info.model_version != provider["model"]
        ):
            raise ValueError("live provider/model does not match preregistration")
    out.mkdir(parents=True, exist_ok=False)
    evidence = _eval_evidence()
    budget = ModelCallBudget(MAX_CALLS, max_response_chars=2_000)
    cells: list[dict[str, Any]] = []
    by_key: dict[tuple[str, str, str], dict[str, Any]] = {}
    adapters = {"GAWorld": run_gaworld, "YuLan-OneSim": run_yulan}

    for task in load_tasks():
        task_id = str(task["id"])
        for variant in VARIANTS:
            for platform in PLATFORMS:
                platform_slug = "gaworld" if platform == "GAWorld" else "yulan"
                run_id = f"t3nc_{platform_slug}_{task_id}_{variant}"
                run_dir = out / "runs" / run_id
                runner = RecordedModelRunner(
                    run_dir / "model_trace.jsonl",
                    client,
                    budget,
                    temperature=TEMPERATURE,
                    allow_live_model=allow_live_model,
                    run_id=run_id,
                )
                loop = adapters[platform](task, variant, run_dir, runner)
                cell = score_cell(
                    task=task,
                    variant=variant,
                    platform=platform,
                    run_id=run_id,
                    loop=loop,
                    eval_mode_evidence=evidence,
                )
                cell_path = run_dir / "cell_result.json"
                cell_path.write_text(
                    json.dumps(cell, ensure_ascii=False, indent=2) + "\n",
                    encoding="utf-8",
                )
                cells.append(cell)
                by_key[(task_id, variant, platform)] = cell

    comparisons = [
        _paired_comparison(task_id, variant, by_key)
        for task_id in TASK_IDS
        for variant in VARIANTS
    ]
    platform_summary: dict[str, dict[str, Any]] = {}
    for platform in PLATFORMS:
        selected = [cell for cell in cells if cell["extra"]["platform"] == platform]
        platform_summary[platform] = {
            "cells": len(selected),
            "measurement_valid": sum(bool(cell["measurement_valid"]) for cell in selected),
            "full_pass": sum(int(cell.get("full_pass") or 0) for cell in selected),
            "full_pass_rate": round(
                sum(int(cell.get("full_pass") or 0) for cell in selected)
                / len(selected),
                4,
            ),
            "support_adoption_rate": round(
                sum(
                    _criterion(cell, "adoption_effect_correct")
                    for cell in selected
                    if cell["extra"]["variant"] == "verified_support"
                )
                / len(TASK_IDS),
                4,
            ),
            "conflict_rejection_rate": round(
                sum(
                    _criterion(cell, "adoption_effect_correct")
                    for cell in selected
                    if cell["extra"]["variant"] == "verified_conflict"
                )
                / len(TASK_IDS),
                4,
            ),
        }
    exact_keys = (
        "prompt_hashes_exact",
        "role_outputs_exact",
        "proposal_exact",
        "review_exact",
        "executor_exact",
        "final_state_exact",
        "full_pass_exact",
    )
    exact_matches = {
        key: sum(bool(item[key]) for item in comparisons) for key in exact_keys
    }
    exact_matches["denominator"] = len(comparisons)
    offline_calibrated = bool(
        not client.info.live
        and len(cells) == 12
        and int(budget.snapshot()["calls_used"]) == MAX_CALLS
        and all(cell["measurement_valid"] and cell["full_pass"] == 1 for cell in cells)
        and all(item["prompt_hashes_exact"] for item in comparisons)
        and all(item["role_outputs_exact"] for item in comparisons)
    )
    report = {
        "experiment_id": "CROSS-PLATFORM-T3-NONCODE-REVIEW-v1",
        "preregistration_id": registration["preregistration_id"],
        "registration_path": str(REGISTRATION_PATH),
        "registration_sha256": registration_sha256,
        "phase": "live_protocol_parity" if client.info.live else "offline_fixture_calibration",
        "gate": (
            "offline_runner_calibration_pass"
            if offline_calibrated
            else "model_pilot_recorded"
            if client.info.live
            else "offline_runner_calibration_failed"
        ),
        "provider": client.info.provider,
        "model_version": client.info.model_version,
        "live_model": client.info.live,
        "live_model_explicitly_allowed": allow_live_model,
        "prompt_protocol": PROTOCOL,
        "scorer_version": SCORER_VERSION,
        "ranking_eligible": False,
        "n_cells": len(cells),
        "platform_summary": platform_summary,
        "exact_matches": exact_matches,
        "comparisons": comparisons,
        "budget": budget.snapshot(),
    }
    (out / "cell_table.json").write_text(
        json.dumps(cells, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    (out / "RUN_MANIFEST.yaml").write_text(
        yaml.safe_dump(report, allow_unicode=True, sort_keys=False), encoding="utf-8"
    )
    _write_report(out, report)
    return cells, report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--provider")
    parser.add_argument("--allow-live-model", action="store_true")
    parser.add_argument("--fixture-oracle", action="store_true")
    parser.add_argument("--temperature", type=float, default=TEMPERATURE)
    parser.add_argument("--max-tokens", type=int, default=MAX_TOKENS)
    parser.add_argument("--max-calls", type=int, default=MAX_CALLS)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    if (args.temperature, args.max_tokens, args.max_calls) != (
        TEMPERATURE,
        MAX_TOKENS,
        MAX_CALLS,
    ):
        parser.error("registered run requires temperature=0, max-tokens=256, max-calls=36")
    if args.fixture_oracle:
        if args.provider or args.allow_live_model:
            parser.error("fixture cannot be combined with live options")
        client: ModelClient = oracle_fixture_client()
    else:
        if not args.allow_live_model or args.provider != "paratera_glm":
            parser.error("live run requires --provider paratera_glm --allow-live-model")
        os.environ["GAWORLD_LLM_MODEL"] = "GLM-5.2"
        os.environ["GAWORLD_LLM_THINKING"] = THINKING
        os.environ.pop("GAWORLD_LLM_REASONING_EFFORT", None)
        client = GAWorldModelClient(
            args.provider,
            temperature=TEMPERATURE,
            max_tokens=MAX_TOKENS,
        )
    _, report = run_matrix(
        out=args.out,
        client=client,
        allow_live_model=args.allow_live_model,
    )
    print(yaml.safe_dump(report, allow_unicode=True, sort_keys=False))
    return 1 if report["gate"] == "offline_runner_calibration_failed" else 0


if __name__ == "__main__":
    raise SystemExit(main())
