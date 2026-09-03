"""Calibrate and run the preregistered shared-review cross-platform replay."""

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
from benchmark_core.model_runner_v2 import (
    GAWorldModelClient,
    ModelCallBudget,
    ModelClient,
    RecordedModelRunner,
)
from v0_first_batch.paths import BRIDGE_ROOT, ensure_import_paths

ensure_import_paths()

from cross_platform.t3_noncode_replay_v2.gaworld_replay import replay as replay_gaworld
from cross_platform.t3_noncode_replay_v2.protocol import (
    CALIBRATION_CASES,
    PLATFORMS,
    PROTOCOL,
    TASK_IDS,
    VARIANTS,
    load_tasks,
    oracle_shared_review,
    payload_sha256,
    reviewer_prompt,
    reviewer_validator,
    shared_review,
)
from cross_platform.t3_noncode_replay_v2.scorer import SCORER_VERSION, score_replay
from cross_platform.t3_noncode_replay_v2.yulan_replay import replay as replay_yulan
from cross_platform.t3_noncode_review.fixture import oracle_fixture_client

EXPERIMENT_ID = "CROSS-PLATFORM-T3-NONCODE-SHARED-REPLAY-v2"
REGISTRATION_PATH = Path(__file__).with_name(
    "registration_t3_noncode_replay_glm52.yaml"
)
YULAN_ROOT = Path(r"F:\proj\YuLan-OneSim-official")
YULAN_COMMIT = "9829d722b528b733f8c8317315637071fa23b206"
GAWORLD_ROOT = Path(r"F:\proj\GAWorld")
GAWORLD_COMMIT = "bfcd2a665a299ddc25660a33102169f8bcfd856e"
GAWORLD_REVIEW = GAWORLD_ROOT / "gaworld" / "work" / "review.py"
GAWORLD_AUDITED_PROVIDER = GAWORLD_ROOT / "llm_providers_audited.py"
MODEL_RUNNER_V2 = BRIDGE_ROOT / "benchmark_core" / "model_runner_v2.py"
PROVIDER = "paratera_glm"
MODEL = "GLM-5.2"
BASE_URL = "https://llmapi.paratera.com/v1"
TEMPERATURE = 0.0
MAX_TOKENS = 256
RETRY_ATTEMPTS = 1
RESPONSE_FORMAT = {"type": "json_object"}
JSON_NORMALIZATION = "strict"
CALIBRATION_CALLS = len(CALIBRATION_CASES)
REPLAY_CALLS = len(TASK_IDS) * len(VARIANTS)


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _git_head(path: Path) -> str:
    return subprocess.run(
        ["git", "-C", str(path), "rev-parse", "HEAD"],
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()


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
    expected_design = {
        "task_ids": list(TASK_IDS),
        "variants": list(VARIANTS),
        "platforms": list(PLATFORMS),
        "calibration_calls": CALIBRATION_CALLS,
        "scored_reviewer_calls": REPLAY_CALLS,
        "prompt_protocol": PROTOCOL,
        "scorer_version": SCORER_VERSION,
    }
    for key, expected in expected_design.items():
        if design.get(key) != expected:
            errors.append(f"registered_{key}_mismatch")
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
            errors.append(f"registered_provider_{key}_mismatch")
    systems = payload.get("systems") or {}
    if _git_head(YULAN_ROOT) != YULAN_COMMIT:
        errors.append("yulan_commit_mismatch")
    if _git_head(GAWORLD_ROOT) != GAWORLD_COMMIT:
        errors.append("gaworld_commit_mismatch")
    if _sha256(GAWORLD_REVIEW) != str(
        (systems.get("gaworld") or {}).get("review_channel_sha256") or ""
    ):
        errors.append("gaworld_review_channel_hash_mismatch")
    if _sha256(GAWORLD_AUDITED_PROVIDER) != str(
        (systems.get("gaworld") or {}).get("audited_provider_sha256") or ""
    ):
        errors.append("gaworld_audited_provider_hash_mismatch")
    if _sha256(MODEL_RUNNER_V2) != str(
        (systems.get("bridge") or {}).get("model_runner_v2_sha256") or ""
    ):
        errors.append("model_runner_v2_hash_mismatch")
    if errors:
        raise RuntimeError("preregistration validation failed: " + ",".join(errors))
    return payload, _sha256(REGISTRATION_PATH)


def _eval_evidence() -> dict[str, Any]:
    from config import CONFIG

    config = deepcopy(CONFIG)
    config.setdefault("eval_mode", {})["enabled"] = True
    return capture_eval_mode_evidence(config)


def _assert_registered_client(client: ModelClient) -> None:
    if client.info.live and (
        client.info.provider != PROVIDER or client.info.model_version != MODEL
    ):
        raise ValueError(
            f"live provider/model mismatch: {client.info.provider}/{client.info.model_version}"
        )


def _sample(
    *,
    task: dict[str, Any],
    variant: str,
    runner: RecordedModelRunner,
) -> dict[str, Any]:
    prompt = reviewer_prompt(task, variant)
    response = runner.call_json(
        prompt,
        task="benchmark_t3_noncode_shared_review",
        agent_id="reviewer",
        validator=reviewer_validator,
    )
    review = shared_review(task, response.parsed) if response.ok else None
    oracle = oracle_shared_review(task, variant)
    return {
        "task_id": str(task["id"]),
        "variant": variant,
        "response_ok": response.ok,
        "response_error": response.error,
        "evidence_id": response.evidence_id,
        "call_id": response.call_id,
        "model_trace_path": str(runner.path),
        "prompt_sha256": hashlib.sha256(prompt.encode("utf-8")).hexdigest(),
        "raw_response_sha256": hashlib.sha256(
            response.raw_response.encode("utf-8")
        ).hexdigest(),
        "normalization_applied": response.normalization_applied,
        "normalization_rule": response.normalization_rule,
        "shared_review": review,
        "shared_review_sha256": payload_sha256(review),
        "oracle_shared_review": oracle,
        "reviewer_oracle_correct": review == oracle,
    }


def _write_calibration_report(out: Path, report: dict[str, Any]) -> None:
    lines = [
        "# GLM-5.2 结构化接口不计分校准",
        "",
        f"- 门禁：`{report['gate']}`",
        f"- 模型：`{report['provider']} / {report['model_version']}`",
        f"- 逻辑调用：{report['budget']['calls_used']}/{CALIBRATION_CALLS}",
        f"- 物理尝试：{report['budget']['transport_attempts_observed']}",
        f"- 内部重试：{report['budget']['transport_retries_observed']}",
        f"- 严格结构化响应：{report['strict_valid_responses']}/{CALIBRATION_CALLS}",
        "",
        "这两次调用只检查运行时模型身份、严格 JSON 和逐请求审计，不进入 T3 得分。",
        "语义是否命中 Oracle 仅记录，不作为是否启动正式采样的选择门。",
    ]
    (out / "REPORT.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def run_live_calibration(out: Path, client: ModelClient) -> dict[str, Any]:
    registration, registration_sha256 = _registration()
    _assert_registered_client(client)
    if not client.info.live:
        raise ValueError("live calibration requires a live client")
    out.mkdir(parents=True, exist_ok=False)
    budget = ModelCallBudget(CALIBRATION_CALLS, max_response_chars=2_000)
    runner = RecordedModelRunner(
        out / "model_trace.jsonl",
        client,
        budget,
        temperature=TEMPERATURE,
        allow_live_model=True,
        run_id="t3nc_replay_v2_live_calibration",
        json_normalization=JSON_NORMALIZATION,
    )
    tasks = {str(task["id"]): task for task in load_tasks()}
    samples = [
        _sample(task=tasks[task_id], variant=variant, runner=runner)
        for task_id, variant in CALIBRATION_CASES
    ]
    snapshot = budget.snapshot()
    strict_valid = sum(bool(sample["response_ok"]) for sample in samples)
    gate_pass = bool(
        strict_valid == CALIBRATION_CALLS
        and snapshot["calls_used"] == CALIBRATION_CALLS
        and snapshot["transport_attempts_observed"] == CALIBRATION_CALLS
        and snapshot["transport_retries_observed"] == 0
        and all(not sample["normalization_applied"] for sample in samples)
    )
    report = {
        "experiment_id": EXPERIMENT_ID,
        "preregistration_id": registration["preregistration_id"],
        "registration_sha256": registration_sha256,
        "phase": "live_interface_calibration_non_scoring",
        "gate": "live_calibration_pass" if gate_pass else "live_calibration_failed",
        "ranking_eligible": False,
        "provider": client.info.provider,
        "model_version": client.info.model_version,
        "settings": dict(registration["provider"]),
        "strict_valid_responses": strict_valid,
        "semantic_oracle_correct_recorded_not_gated": sum(
            bool(sample["reviewer_oracle_correct"]) for sample in samples
        ),
        "samples": samples,
        "budget": snapshot,
    }
    (out / "RUN_MANIFEST.yaml").write_text(
        yaml.safe_dump(report, allow_unicode=True, sort_keys=False),
        encoding="utf-8",
    )
    _write_calibration_report(out, report)
    return report


def _validate_calibration(
    path: Path, registration_sha256: str
) -> tuple[dict[str, Any], str]:
    payload = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    errors: list[str] = []
    if payload.get("gate") != "live_calibration_pass":
        errors.append("calibration_gate_not_passed")
    if payload.get("registration_sha256") != registration_sha256:
        errors.append("calibration_registration_mismatch")
    if payload.get("provider") != PROVIDER or payload.get("model_version") != MODEL:
        errors.append("calibration_model_mismatch")
    if errors:
        raise RuntimeError("live replay blocked: " + ",".join(errors))
    return payload, _sha256(path)


def _pair_comparison(cells: list[dict[str, Any]]) -> dict[str, Any]:
    gaworld = next(cell for cell in cells if cell["platform"] == "GAWorld")
    yulan = next(cell for cell in cells if cell["platform"] == "YuLan-OneSim")
    ga_profile = gaworld["process_profile"]
    yu_profile = yulan["process_profile"]
    evaluable = bool(gaworld["transport_evaluable"] and yulan["transport_evaluable"])
    return {
        "task_id": gaworld["task_id"],
        "variant": gaworld["variant"],
        "transport_evaluable": evaluable,
        "shared_sample_evidence_id_exact": (
            gaworld["evidence"]["model_evidence_id"]
            == yulan["evidence"]["model_evidence_id"]
        ),
        "ingress_review_hash_exact": (
            gaworld["evidence"]["ingress_review_sha256"]
            == yulan["evidence"]["ingress_review_sha256"]
        ),
        "delivered_review_exact": (
            ga_profile["delivered_review"] == yu_profile["delivered_review"]
        ),
        "executor_output_exact": (
            ga_profile["executor_output"] == yu_profile["executor_output"]
        ),
        "platform_transport_pass_exact": (
            gaworld["platform_transport_pass"] == yulan["platform_transport_pass"]
        ),
        "platform_difference": bool(
            evaluable
            and gaworld["platform_transport_pass"] != yulan["platform_transport_pass"]
        ),
    }


def _write_replay_report(out: Path, report: dict[str, Any]) -> None:
    lines = [
        "# T3 非代码共享审核载荷双平台重放 v2",
        "",
        f"- 阶段：`{report['phase']}`",
        f"- 门禁：`{report['gate']}`",
        f"- 模型：`{report['provider']} / {report['model_version']}`",
        f"- reviewer 逻辑调用：{report['budget']['calls_used']}/{REPLAY_CALLS}",
        f"- reviewer 严格结构化有效：{report['review_samples']['valid']}/{REPLAY_CALLS}",
        f"- reviewer Oracle 命中：{report['review_samples']['oracle_correct']}/{REPLAY_CALLS}",
        f"- 平台效应可评价对：{report['platform_effect']['evaluable_pairs']}/{REPLAY_CALLS}",
        f"- 平台差异对：{report['platform_effect']['difference_pairs']}",
        "",
        "## 平台运输结果",
        "",
    ]
    for platform, summary in report["platform_summary"].items():
        lines.append(
            f"- {platform}：transport {summary['transport_pass']}/{summary['transport_evaluable']}；"
            f"joint FullPass {summary['joint_full_pass']}/{REPLAY_CALLS}"
        )
    lines.extend(
        [
            "",
            "## 解释边界",
            "",
            "每个任务条件只在平台外采样一次 reviewer；两个平台收到相同 evidence_id 和审核对象。",
            "平台比较只使用 reviewer 响应有效的条件，固定分母的 joint FullPass 仍保留所有无效响应。",
            "该实验隔离当前适配器的载荷运输差异，不构成两个平台的总体能力排名。",
        ]
    )
    (out / "REPORT.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def run_replay_matrix(
    out: Path,
    client: ModelClient,
    *,
    allow_live_model: bool,
    calibration_manifest: Path | None = None,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    registration, registration_sha256 = _registration()
    _assert_registered_client(client)
    calibration: dict[str, Any] | None = None
    calibration_sha256: str | None = None
    if client.info.live:
        if not allow_live_model or calibration_manifest is None:
            raise ValueError(
                "live replay requires explicit permission and passed calibration"
            )
        calibration, calibration_sha256 = _validate_calibration(
            calibration_manifest, registration_sha256
        )
    out.mkdir(parents=True, exist_ok=False)
    budget = ModelCallBudget(REPLAY_CALLS, max_response_chars=2_000)
    runner = RecordedModelRunner(
        out / "model_trace.jsonl",
        client,
        budget,
        temperature=TEMPERATURE,
        allow_live_model=allow_live_model,
        run_id="t3nc_shared_replay_v2",
        json_normalization=JSON_NORMALIZATION,
    )
    adapters = {"GAWorld": replay_gaworld, "YuLan-OneSim": replay_yulan}
    samples: list[dict[str, Any]] = []
    cells: list[dict[str, Any]] = []
    comparisons: list[dict[str, Any]] = []
    for task in load_tasks():
        for variant in VARIANTS:
            sample = _sample(task=task, variant=variant, runner=runner)
            samples.append(sample)
            paired_cells: list[dict[str, Any]] = []
            for platform in PLATFORMS:
                platform_slug = "gaworld" if platform == "GAWorld" else "yulan"
                run_id = f"t3ncr2_{task['id']}_{variant}_{platform_slug}"
                loop = adapters[platform](
                    task,
                    variant,
                    sample.get("shared_review"),
                    out / "runs" / run_id,
                )
                loop["run_id"] = run_id
                cell = score_replay(
                    task=task,
                    variant=variant,
                    sample=sample,
                    loop=loop,
                )
                cell_path = out / "runs" / run_id / "cell_result.json"
                cell_path.write_text(
                    json.dumps(cell, ensure_ascii=False, indent=2) + "\n",
                    encoding="utf-8",
                )
                cells.append(cell)
                paired_cells.append(cell)
            comparisons.append(_pair_comparison(paired_cells))

    (out / "review_samples.json").write_text(
        json.dumps(samples, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    (out / "cell_table.json").write_text(
        json.dumps(cells, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    platform_summary: dict[str, dict[str, int]] = {}
    for platform in PLATFORMS:
        selected = [cell for cell in cells if cell["platform"] == platform]
        evaluable = [cell for cell in selected if cell["transport_evaluable"]]
        platform_summary[platform] = {
            "cells": len(selected),
            "transport_evaluable": len(evaluable),
            "transport_pass": sum(
                int(cell["platform_transport_pass"] is True) for cell in evaluable
            ),
            "joint_full_pass": sum(int(cell["joint_full_pass"]) for cell in selected),
        }
    snapshot = budget.snapshot()
    fixture_pass = bool(
        not client.info.live
        and snapshot["calls_used"] == REPLAY_CALLS
        and all(sample["response_ok"] for sample in samples)
        and all(sample["reviewer_oracle_correct"] for sample in samples)
        and all(cell["joint_full_pass"] == 1 for cell in cells)
        and all(
            comparison["shared_sample_evidence_id_exact"]
            and comparison["ingress_review_hash_exact"]
            and comparison["delivered_review_exact"]
            and comparison["executor_output_exact"]
            for comparison in comparisons
        )
    )
    live_complete = bool(
        client.info.live
        and snapshot["calls_used"] == REPLAY_CALLS
        and len(cells) == REPLAY_CALLS * len(PLATFORMS)
    )
    report = {
        "experiment_id": EXPERIMENT_ID,
        "preregistration_id": registration["preregistration_id"],
        "registration_sha256": registration_sha256,
        "phase": (
            "live_shared_review_replay"
            if client.info.live
            else "offline_fixture_calibration"
        ),
        "gate": (
            "live_replay_recorded"
            if live_complete
            else "offline_fixture_calibration_pass"
            if fixture_pass
            else "run_incomplete_or_fixture_failed"
        ),
        "ranking_eligible": False,
        "provider": client.info.provider,
        "model_version": client.info.model_version,
        "settings": dict(registration["provider"]),
        "eval_mode_evidence": _eval_evidence(),
        "calibration_manifest": str(calibration_manifest) if calibration else None,
        "calibration_manifest_sha256": calibration_sha256,
        "review_samples": {
            "requested": REPLAY_CALLS,
            "valid": sum(bool(sample["response_ok"]) for sample in samples),
            "oracle_correct": sum(
                bool(sample["reviewer_oracle_correct"]) for sample in samples
            ),
        },
        "platform_summary": platform_summary,
        "platform_effect": {
            "evaluable_pairs": sum(
                bool(comparison["transport_evaluable"]) for comparison in comparisons
            ),
            "difference_pairs": sum(
                bool(comparison["platform_difference"]) for comparison in comparisons
            ),
            "comparisons": comparisons,
        },
        "budget": snapshot,
    }
    (out / "RUN_MANIFEST.yaml").write_text(
        yaml.safe_dump(report, allow_unicode=True, sort_keys=False),
        encoding="utf-8",
    )
    _write_replay_report(out, report)
    return cells, report


def _live_client() -> GAWorldModelClient:
    os.environ["GAWORLD_LLM_API_BASE"] = BASE_URL
    os.environ["GAWORLD_LLM_MODEL"] = MODEL
    os.environ["GAWORLD_LLM_THINKING"] = "disabled"
    os.environ.pop("GAWORLD_LLM_REASONING_EFFORT", None)
    return GAWorldModelClient(
        PROVIDER,
        temperature=TEMPERATURE,
        max_tokens=MAX_TOKENS,
        response_format=RESPONSE_FORMAT,
        retry_attempts=RETRY_ATTEMPTS,
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    phase = parser.add_mutually_exclusive_group(required=True)
    phase.add_argument("--fixture-oracle", action="store_true")
    phase.add_argument("--live-calibration", action="store_true")
    phase.add_argument("--live-replay", action="store_true")
    parser.add_argument("--provider")
    parser.add_argument("--allow-live-model", action="store_true")
    parser.add_argument("--calibration-manifest", type=Path)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    if args.fixture_oracle:
        if args.provider or args.allow_live_model or args.calibration_manifest:
            parser.error("fixture phase cannot use live options")
        _, report = run_replay_matrix(
            args.out,
            oracle_fixture_client(),
            allow_live_model=False,
        )
    else:
        if args.provider != PROVIDER or not args.allow_live_model:
            parser.error(
                "live phase requires --provider paratera_glm --allow-live-model"
            )
        client = _live_client()
        if args.live_calibration:
            if args.calibration_manifest:
                parser.error("calibration phase does not accept a calibration manifest")
            report = run_live_calibration(args.out, client)
        else:
            if args.calibration_manifest is None:
                parser.error("live replay requires --calibration-manifest")
            _, report = run_replay_matrix(
                args.out,
                client,
                allow_live_model=True,
                calibration_manifest=args.calibration_manifest,
            )
    print(yaml.safe_dump(report, allow_unicode=True, sort_keys=False))
    return 0 if report["gate"].endswith(("pass", "recorded")) else 1


if __name__ == "__main__":
    raise SystemExit(main())
