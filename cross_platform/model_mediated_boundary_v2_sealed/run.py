"""Run the sealed platform-card pressure comparison."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
from pathlib import Path
from typing import Any

import yaml

from benchmark_core.model_runner_v2 import (
    CallableModelClient,
    GAWorldModelClient,
    ModelCallBudget,
    ModelClient,
    RecordedModelRunner,
)
from cross_platform.model_mediated_boundary_v2_sealed.common import (
    CONDITIONS,
    EXPERIMENT_ID,
    PLATFORMS,
    PROTOCOL,
    build_prompt,
    load_cards,
    sha256_file,
    validator,
)
from cross_platform.model_mediated_boundary_v2_sealed.scorer import (
    SCORER_VERSION,
    score_cell,
    summarize,
)
from v0_first_batch.paths import BRIDGE_ROOT, ensure_import_paths

ensure_import_paths()

PROVIDER = "paratera_glm"
MODEL = "GLM-5.2"
BASE_URL = "https://llmapi.paratera.com/v1"
TEMPERATURE = 0.0
MAX_TOKENS = 160
RETRY_ATTEMPTS = 2
RESPONSE_FORMAT = {"type": "json_object"}
JSON_NORMALIZATION = "strict"
FORMAL_CALLS = 24
REGISTRATION_PATH = Path(__file__).with_name("registration_v1.yaml")
NATIVE_RESULT_PATH = (
    BRIDGE_ROOT
    / "output"
    / "cross_platform_native_boundary_probes_v1_20260905"
    / "probe_results.json"
)
CALIBRATION_PATH = (
    BRIDGE_ROOT
    / "output"
    / "model_mediated_boundary_v2_sealed_calibration_20260905"
    / "CALIBRATION_MANIFEST.yaml"
)
GAWORLD_ROOT = BRIDGE_ROOT.parent / "GAWorld"
GAWORLD_COMMIT = "bfcd2a665a299ddc25660a33102169f8bcfd856e"
GAWORLD_AUDITED_PROVIDER_PATH = GAWORLD_ROOT / "llm_providers_audited.py"
NATIVE_EVIDENCE_COMMIT = "cf973dfac6cbc6303c6c20cee6c09d3bdbb0e3e4"


def _git_head(path: Path) -> str:
    return subprocess.run(
        ["git", "-C", str(path), "rev-parse", "HEAD"],
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()


def _registration() -> tuple[dict[str, Any], str]:
    if not REGISTRATION_PATH.is_file():
        raise RuntimeError("formal run requires registration_v1.yaml")
    payload = yaml.safe_load(REGISTRATION_PATH.read_text(encoding="utf-8")) or {}
    errors: list[str] = []
    for relative, expected in (payload.get("frozen_inputs") or {}).items():
        path = BRIDGE_ROOT / str(relative)
        if not path.is_file():
            errors.append(f"missing:{relative}")
        elif sha256_file(path) != str(expected):
            errors.append(f"sha256_mismatch:{relative}")
    provider = payload.get("provider") or {}
    expected_provider = {
        "name": PROVIDER,
        "model": MODEL,
        "base_url": BASE_URL,
        "temperature": TEMPERATURE,
        "thinking": "disabled",
        "max_tokens_per_call": MAX_TOKENS,
        "response_format": RESPONSE_FORMAT,
        "retry_attempts": RETRY_ATTEMPTS,
        "json_normalization": JSON_NORMALIZATION,
    }
    for key, expected in expected_provider.items():
        if provider.get(key) != expected:
            errors.append(f"provider_{key}_mismatch")
    design = payload.get("design") or {}
    if design.get("platform_order") != list(PLATFORMS):
        errors.append("platform_order_mismatch")
    if design.get("condition_order") != list(CONDITIONS):
        errors.append("condition_order_mismatch")
    if design.get("formal_calls") != FORMAL_CALLS:
        errors.append("formal_calls_mismatch")
    if design.get("scorer_version") != SCORER_VERSION:
        errors.append("scorer_version_mismatch")
    if sha256_file(NATIVE_RESULT_PATH) != str(
        payload.get("native_probe_results_sha256") or ""
    ):
        errors.append("native_results_hash_mismatch")
    if sha256_file(CALIBRATION_PATH) != str(
        payload.get("calibration_manifest_sha256") or ""
    ):
        errors.append("calibration_manifest_hash_mismatch")
    if _git_head(GAWORLD_ROOT) != GAWORLD_COMMIT:
        errors.append("gaworld_commit_mismatch")
    if payload.get("gaworld_commit") != GAWORLD_COMMIT:
        errors.append("registered_gaworld_commit_mismatch")
    if sha256_file(GAWORLD_AUDITED_PROVIDER_PATH) != str(
        payload.get("gaworld_audited_provider_sha256") or ""
    ):
        errors.append("audited_provider_hash_mismatch")
    calibration = yaml.safe_load(CALIBRATION_PATH.read_text(encoding="utf-8")) or {}
    if not (
        calibration.get("gate") == "pass"
        and calibration.get("model_version") == MODEL
        and calibration.get("strict_valid") == 3
        and calibration.get("full_expected") == 3
    ):
        errors.append("calibration_gate_mismatch")
    registration_relative = REGISTRATION_PATH.relative_to(BRIDGE_ROOT).as_posix()
    tracked = subprocess.run(
        [
            "git",
            "-C",
            str(BRIDGE_ROOT),
            "ls-files",
            "--error-unmatch",
            registration_relative,
        ],
        check=False,
        capture_output=True,
        text=True,
    )
    if tracked.returncode != 0:
        errors.append("registration_not_committed")
    diff = subprocess.run(
        [
            "git",
            "-C",
            str(BRIDGE_ROOT),
            "diff",
            "--quiet",
            "--",
            registration_relative,
        ],
        check=False,
    )
    if diff.returncode != 0:
        errors.append("registration_has_uncommitted_change")
    ancestor = subprocess.run(
        [
            "git",
            "-C",
            str(BRIDGE_ROOT),
            "merge-base",
            "--is-ancestor",
            NATIVE_EVIDENCE_COMMIT,
            "HEAD",
        ],
        check=False,
    )
    if ancestor.returncode != 0:
        errors.append("native_evidence_commit_not_ancestor")
    if errors:
        raise RuntimeError("preregistration validation failed: " + ",".join(errors))
    return payload, sha256_file(REGISTRATION_PATH)


def fixture_client() -> ModelClient:
    cards = load_cards()
    expected_by_task = {
        task["task_id"]: task["expected"] for task in cards["formal_tasks"]
    }
    calibration = cards["calibration_task"]
    expected_by_task[calibration["task_id"]] = calibration["expected"]

    def handler(_prompt: str, task: str, _agent_id: str | None) -> str:
        task_id = task.split(":", 1)[1]
        expected = expected_by_task[task_id]
        return json.dumps(expected, separators=(",", ":"))

    return CallableModelClient(handler)


def live_client() -> ModelClient:
    os.environ["GAWORLD_LLM_MODEL"] = MODEL
    os.environ["GAWORLD_LLM_THINKING"] = "disabled"
    os.environ["GAWORLD_LLM_API_BASE"] = BASE_URL
    os.environ.pop("GAWORLD_LLM_REASONING_EFFORT", None)
    return GAWorldModelClient(
        PROVIDER,
        temperature=TEMPERATURE,
        max_tokens=MAX_TOKENS,
        response_format=RESPONSE_FORMAT,
        retry_attempts=RETRY_ATTEMPTS,
    )


def _runner(
    out: Path, client: ModelClient, calls: int, run_id: str
) -> tuple[RecordedModelRunner, ModelCallBudget]:
    budget = ModelCallBudget(calls, max_response_chars=2_000)
    return (
        RecordedModelRunner(
            out / "model_trace.jsonl",
            client,
            budget,
            temperature=TEMPERATURE,
            allow_live_model=client.info.live,
            run_id=run_id,
            json_normalization=JSON_NORMALIZATION,
        ),
        budget,
    )


def _sample(
    *,
    runner: RecordedModelRunner,
    platform: str,
    task: dict[str, Any],
    condition: str,
    calibration: bool,
) -> dict[str, Any]:
    prompt = build_prompt(
        platform=platform,
        task=task,
        condition=condition,
        calibration=calibration,
    )
    response = runner.call_json(
        prompt,
        task=f"sealed_boundary:{task['task_id']}",
        agent_id=f"{platform}:{task['actor']}",
        validator=validator(task),
    )
    return {
        "platform": platform,
        "task_id": task["task_id"],
        "probe_id": task.get("probe_id", "CALIBRATION"),
        "condition": condition,
        "response_ok": response.ok,
        "response_error": response.error,
        "parsed": response.parsed,
        "evidence_id": response.evidence_id,
        "call_id": response.call_id,
        "prompt_sha256": hashlib.sha256(prompt.encode("utf-8")).hexdigest(),
        "normalization_applied": response.normalization_applied,
    }


def run_calibration(out: Path, client: ModelClient) -> dict[str, Any]:
    out.mkdir(parents=True, exist_ok=False)
    task = load_cards()["calibration_task"]
    runner, budget = _runner(out, client, 3, "sealed_boundary_v2_calibration")
    samples = [
        _sample(
            runner=runner,
            platform=platform,
            task=task,
            condition="calibration",
            calibration=True,
        )
        for platform in PLATFORMS
    ]
    valid = sum(sample["response_ok"] for sample in samples)
    full = sum(
        sample["response_ok"] and sample["parsed"] == task["expected"]
        for sample in samples
    )
    report = {
        "experiment_id": EXPERIMENT_ID,
        "phase": "non_scoring_live_calibration" if client.info.live else "fixture",
        "gate": "pass" if valid == 3 and full == 3 else "fail",
        "ranking_eligible": False,
        "provider": client.info.provider,
        "model_version": client.info.model_version,
        "calls": 3,
        "strict_valid": valid,
        "full_expected": full,
        "budget": budget.snapshot(),
        "samples": samples,
    }
    (out / "CALIBRATION_MANIFEST.yaml").write_text(
        yaml.safe_dump(report, allow_unicode=True, sort_keys=False), encoding="utf-8"
    )
    return report


def _native_lookup() -> dict[tuple[str, str], dict[str, Any]]:
    results = json.loads(NATIVE_RESULT_PATH.read_text(encoding="utf-8"))
    return {
        (result["platform"], item["probe_id"]): item
        for result in results
        for item in result["probes"]
    }


def _write_report(
    out: Path, manifest: dict[str, Any], cells: list[dict[str, Any]]
) -> None:
    lines = [
        f"# {EXPERIMENT_ID} 结果",
        "",
        f"模型：`{manifest['provider']} / {manifest['model_version']}`；逻辑调用：{manifest['new_model_calls']}；物理尝试：{manifest['budget']['transport_attempts_observed']}；重试：{manifest['budget']['transport_retries_observed']}。",
        "",
        "| 平台 | 有效 | 动作正确 | 权威绑定 | Owner正确 | FullPass | 压力对通过 | 纵深安全 |",
        "|---|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for platform, values in manifest["platform_summary"].items():
        lines.append(
            f"| {platform} | {values['valid_responses']}/8 | "
            f"{values['action_correct']}/8 | {values['authority_binding_correct']}/8 | "
            f"{values['owner_correct']}/8 | {values['full_policy_pass']}/8 | "
            f"{values['pressure_pairs_full_pass']}/4 | "
            f"{values['defense_in_depth_safe']}/8 |"
        )
    lines.extend(
        [
            "",
            "## 逐格",
            "",
            "| 平台 | 任务 | 条件 | 选择 | 规则 | Owner | 动作 | 绑定 | Full | 配对结果 |",
            "|---|---|---|---|---|---|---:|---:|---:|---|",
        ]
    )
    for cell in cells:
        lines.append(
            f"| {cell['platform']} | {cell['task_id']} | {cell['condition']} | "
            f"{cell['observed_choice_id'] or 'invalid'} | "
            f"{cell['observed_governing_record_id'] or 'invalid'} | "
            f"{cell['observed_action_owner'] or 'invalid'} | "
            f"{str(cell['action_correct']).lower()} | "
            f"{str(cell['authority_binding_correct']).lower()} | "
            f"{str(cell['full_policy_pass']).lower()} | {cell['paired_defense_result']} |"
        )
    lines.extend(
        [
            "",
            "## 边界",
            "",
            "这是密封后的描述性先导。每个格只有一个模型样本；routine与authority_pressure是不同输入，不是同输入重复。平台卡文字不可避免地不同，因此不做显著性检验或总体排名。",
            "",
            "对话历史在单次提示中静态呈现，不是动态多轮Agent会话。平台动作没有重新执行；纵深结果来自本轮模型选择与已冻结原生强制探针的配对。",
        ]
    )
    (out / "REPORT.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def run_formal(
    out: Path, client: ModelClient, *, fixture: bool = False
) -> dict[str, Any]:
    registration = None
    registration_sha = None
    if not fixture:
        registration, registration_sha = _registration()
    out.mkdir(parents=True, exist_ok=False)
    tasks = load_cards()["formal_tasks"]
    runner, budget = _runner(out, client, FORMAL_CALLS, "sealed_boundary_v2_formal")
    samples = [
        _sample(
            runner=runner,
            platform=platform,
            task=task,
            condition=condition,
            calibration=False,
        )
        for platform in PLATFORMS
        for task in tasks
        for condition in CONDITIONS
    ]
    native = _native_lookup()
    tasks_by_id = {task["task_id"]: task for task in tasks}
    cells = [
        score_cell(
            sample=sample,
            task=tasks_by_id[sample["task_id"]],
            native_probe=native[(sample["platform"], sample["probe_id"])],
        )
        for sample in samples
    ]
    calibration_sha = (
        sha256_file(CALIBRATION_PATH) if CALIBRATION_PATH.is_file() else None
    )
    manifest = {
        "experiment_id": EXPERIMENT_ID,
        "protocol": PROTOCOL,
        "phase": "fixture" if fixture else "formal_live",
        "preregistration_id": (
            registration.get("preregistration_id") if registration else None
        ),
        "registration_sha256": registration_sha,
        "provider": client.info.provider,
        "model_version": client.info.model_version,
        "new_model_calls": 0 if fixture else FORMAL_CALLS,
        "budget": budget.snapshot(),
        "ranking_eligible": False,
        "native_probe_results_path": str(NATIVE_RESULT_PATH),
        "native_probe_results_sha256": sha256_file(NATIVE_RESULT_PATH),
        "calibration_manifest_path": str(CALIBRATION_PATH),
        "calibration_manifest_sha256": calibration_sha,
        "platform_summary": summarize(cells),
    }
    (out / "samples.json").write_text(
        json.dumps(samples, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    (out / "cell_table.json").write_text(
        json.dumps(cells, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    (out / "RUN_MANIFEST.yaml").write_text(
        yaml.safe_dump(manifest, allow_unicode=True, sort_keys=False), encoding="utf-8"
    )
    _write_report(out, manifest, cells)
    return manifest


def main() -> int:
    parser = argparse.ArgumentParser()
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--fixture", action="store_true")
    mode.add_argument("--calibration", action="store_true")
    mode.add_argument("--formal", action="store_true")
    parser.add_argument("--allow-live-model", action="store_true")
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    if (args.calibration or args.formal) and not args.allow_live_model:
        parser.error("live modes require --allow-live-model")
    client = fixture_client() if args.fixture else live_client()
    report = (
        run_calibration(args.out, client)
        if args.calibration
        else run_formal(args.out, client, fixture=args.fixture)
    )
    print(yaml.safe_dump(report, allow_unicode=True, sort_keys=False))
    return 1 if report.get("gate") == "fail" else 0


if __name__ == "__main__":
    raise SystemExit(main())


__all__ = ["fixture_client", "live_client", "run_calibration", "run_formal"]
