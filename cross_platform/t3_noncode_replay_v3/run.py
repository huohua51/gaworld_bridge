"""Run the AgentSociety 2 extension against frozen T3 reviewer samples."""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
from pathlib import Path
from typing import Any

import yaml

from cross_platform.t3_noncode_replay_v2.protocol import (
    TASK_IDS,
    VARIANTS,
    load_tasks,
    oracle_shared_review,
    payload_sha256,
)
from cross_platform.t3_noncode_replay_v3.agentsociety_replay import replay
from cross_platform.t3_noncode_replay_v3.scorer import SCORER_VERSION, score_replay
from v0_first_batch.paths import BRIDGE_ROOT

EXPERIMENT_ID = "CROSS-PLATFORM-T3-NONCODE-AGENTSOCIETY-EXTENSION-v3"
REGISTRATION_PATH = Path(__file__).with_name("registration_agentsociety_v1.yaml")
AGENTSOCIETY_ROOT = Path(r"F:\proj\AgentSociety")
AGENTSOCIETY_COMMIT = "13e28b5e67a2a8f2f43d640ebf27859126da622e"
SOURCE_ROOT = (
    BRIDGE_ROOT / "output" / "cross_platform_t3_noncode_replay_v2_glm52_20260904"
)


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
            errors.append(f"sha256_mismatch:{relative}")
    system = payload.get("agentsociety2") or {}
    if _git_head(AGENTSOCIETY_ROOT) != AGENTSOCIETY_COMMIT:
        errors.append("agentsociety_commit_mismatch")
    if str(system.get("commit")) != AGENTSOCIETY_COMMIT:
        errors.append("registered_agentsociety_commit_mismatch")
    for relative, expected in (system.get("source_sha256") or {}).items():
        path = AGENTSOCIETY_ROOT / str(relative)
        if not path.is_file():
            errors.append(f"agentsociety_missing:{relative}")
        elif _sha256(path) != str(expected):
            errors.append(f"agentsociety_sha256_mismatch:{relative}")
    design = payload.get("design") or {}
    expected_design = {
        "task_ids": list(TASK_IDS),
        "variants": list(VARIANTS),
        "source_review_samples": 6,
        "agentsociety_platform_cells": 6,
        "new_model_calls": 0,
        "scorer_version": SCORER_VERSION,
    }
    for key, expected in expected_design.items():
        if design.get(key) != expected:
            errors.append(f"registered_{key}_mismatch")
    if errors:
        raise RuntimeError("preregistration validation failed: " + ",".join(errors))
    return payload, _sha256(REGISTRATION_PATH)


def _fixture_sample(task: dict[str, Any], variant: str) -> dict[str, Any]:
    review = oracle_shared_review(task, variant)
    return {
        "task_id": str(task["id"]),
        "variant": variant,
        "response_ok": True,
        "response_error": "",
        "evidence_id": f"fixture:{task['id']}:{variant}",
        "model_trace_path": "fixture",
        "shared_review": review,
        "shared_review_sha256": payload_sha256(review),
        "reviewer_oracle_correct": True,
    }


def _run_samples(*, samples: list[dict[str, Any]], out: Path) -> list[dict[str, Any]]:
    tasks = {str(task["id"]): task for task in load_tasks()}
    expected_order = [
        (task_id, variant) for task_id in TASK_IDS for variant in VARIANTS
    ]
    actual_order = [(str(item["task_id"]), str(item["variant"])) for item in samples]
    if actual_order != expected_order:
        raise ValueError("review sample task/variant order mismatch")
    cells = []
    for sample in samples:
        task_id = str(sample["task_id"])
        variant = str(sample["variant"])
        loop = replay(
            tasks[task_id],
            variant,
            sample.get("shared_review"),
            out / "runs" / f"t3ncr3_{task_id}_{variant}_agentsociety2",
        )
        cell = score_replay(
            task=tasks[task_id], variant=variant, sample=sample, loop=loop
        )
        cell_path = Path(loop["trace_path"]).parent / "cell_result.json"
        cell_path.write_text(
            json.dumps(cell, ensure_ascii=False, indent=2, default=str) + "\n",
            encoding="utf-8",
        )
        cells.append(cell)
    return cells


def run_fixture(out: Path) -> dict[str, Any]:
    out.mkdir(parents=True, exist_ok=False)
    tasks = {str(task["id"]): task for task in load_tasks()}
    samples = [
        _fixture_sample(tasks[task_id], variant)
        for task_id in TASK_IDS
        for variant in VARIANTS
    ]
    cells = _run_samples(samples=samples, out=out)
    report = {
        "experiment_id": EXPERIMENT_ID,
        "phase": "offline_oracle_fixture",
        "gate": "fixture_pass"
        if all(cell["functional_full_pass"] == 1 for cell in cells)
        else "fixture_failed",
        "ranking_eligible": False,
        "cells": len(cells),
        "payload_transport_pass": sum(
            cell["payload_transport_pass"] is True for cell in cells
        ),
        "functional_full_pass": sum(cell["functional_full_pass"] for cell in cells),
        "native_acl_enforced": sum(
            bool(cell["criteria"]["native_acl_enforced_at_tested_boundary"])
            for cell in cells
        ),
        "new_model_calls": 0,
        "agentsociety_runtime": cells[0]["capability_evidence"]["runtime"],
    }
    (out / "FIXTURE_MANIFEST.yaml").write_text(
        yaml.safe_dump(report, allow_unicode=True, sort_keys=False), encoding="utf-8"
    )
    (out / "cell_table.json").write_text(
        json.dumps(cells, ensure_ascii=False, indent=2, default=str) + "\n",
        encoding="utf-8",
    )
    return report


def _source_access_summary() -> dict[str, Any]:
    run_root = SOURCE_ROOT / "runs"
    gaworld_manifests = list(run_root.glob("*_gaworld/replay_manifest.json"))
    gaworld_acl = []
    for path in gaworld_manifests:
        item = json.loads(path.read_text(encoding="utf-8"))
        gaworld_acl.append(
            bool(
                not (item.get("reviewer_write_probe") or {}).get("ok")
                and (item.get("reviewer_write_probe") or {}).get("reason")
                == "unauthorized_artifact_write"
                and not (item.get("executor_private_probe") or {}).get("ok")
                and (item.get("executor_private_probe") or {}).get("reason")
                == "unauthorized_private_read"
            )
        )
    return {
        "GAWorld": {
            "probe_scope": "reviewer final-write plus executor private-read",
            "cells_tested": len(gaworld_acl),
            "cells_denied_both": sum(gaworld_acl),
            "native_acl_evidence": "verified"
            if gaworld_acl and all(gaworld_acl)
            else "failed",
        },
        "YuLan-OneSim": {
            "probe_scope": "no adversarial identity/ACL probe in frozen v2",
            "native_acl_evidence": "not_tested",
        },
        "AgentSociety2": {
            "probe_scope": "SimpleSocialSpace.receive_messages claimed-agent-id boundary",
            "native_acl_evidence": "reported_per_new_cell",
        },
    }


def run_historical(out: Path) -> dict[str, Any]:
    registration, registration_sha = _registration()
    out.mkdir(parents=True, exist_ok=False)
    samples_path = SOURCE_ROOT / "review_samples.json"
    source_manifest_path = SOURCE_ROOT / "RUN_MANIFEST.yaml"
    source_cells_path = SOURCE_ROOT / "cell_table.json"
    samples = json.loads(samples_path.read_text(encoding="utf-8"))
    source_manifest = yaml.safe_load(source_manifest_path.read_text(encoding="utf-8"))
    json.loads(source_cells_path.read_text(encoding="utf-8"))
    cells = _run_samples(samples=samples, out=out)

    evaluable = [cell for cell in cells if cell["transport_evaluable"]]
    source_platform = source_manifest["platform_summary"]
    report = {
        "experiment_id": EXPERIMENT_ID,
        "preregistration_id": registration["preregistration_id"],
        "registration_sha256": registration_sha,
        "phase": "historical_shared_payload_agentsociety_extension",
        "gate": "extension_recorded",
        "ranking_eligible": False,
        "source_experiment_id": source_manifest["experiment_id"],
        "source_artifacts": {
            "run_manifest": str(source_manifest_path),
            "run_manifest_sha256": _sha256(source_manifest_path),
            "review_samples": str(samples_path),
            "review_samples_sha256": _sha256(samples_path),
            "cell_table": str(source_cells_path),
            "cell_table_sha256": _sha256(source_cells_path),
        },
        "sample_identity": {
            "requested": len(samples),
            "valid": sum(bool(sample.get("response_ok")) for sample in samples),
            "model_evidence_ids_reused_exactly": len(
                {str(sample.get("evidence_id")) for sample in samples}
            )
            == len(samples),
            "new_model_calls": 0,
        },
        "agentsociety_runtime": {
            "repository_root": str(AGENTSOCIETY_ROOT),
            "commit": AGENTSOCIETY_COMMIT,
            **cells[0]["capability_evidence"]["runtime"],
        },
        "platform_summary": {
            "GAWorld": source_platform["GAWorld"],
            "YuLan-OneSim": source_platform["YuLan-OneSim"],
            "AgentSociety2": {
                "cells": len(cells),
                "transport_evaluable": len(evaluable),
                "payload_transport_pass": sum(
                    cell["payload_transport_pass"] is True for cell in evaluable
                ),
                "functional_full_pass": sum(
                    cell["functional_full_pass"] for cell in cells
                ),
                "strict_role_isolated_full_pass": sum(
                    cell["strict_role_isolated_full_pass"] for cell in cells
                ),
            },
        },
        "agentsociety_capabilities": {
            "native_acl_enforced_cells": sum(
                bool(cell["criteria"]["native_acl_enforced_at_tested_boundary"])
                for cell in cells
            ),
            "cross_actor_read_accepted_cells": sum(
                bool(
                    cell["capability_evidence"]["identity_binding_probe"].get(
                        "cross_actor_read_accepted"
                    )
                )
                for cell in cells
            ),
            "native_message_id_observable_cells": sum(
                bool(
                    cell["criteria"]["native_message_id_observable_at_receive_boundary"]
                )
                for cell in cells
            ),
        },
        "cross_platform_acl_evidence": _source_access_summary(),
        "claim_boundary": (
            "This extension tests one AgentSociety2 SimpleSocialSpace surface with "
            "the six already-frozen reviewer samples. It is not an overall platform "
            "ranking or an H1-H7 human-validity result."
        ),
    }
    (out / "RUN_MANIFEST.yaml").write_text(
        yaml.safe_dump(report, allow_unicode=True, sort_keys=False), encoding="utf-8"
    )
    (out / "cell_table.json").write_text(
        json.dumps(cells, ensure_ascii=False, indent=2, default=str) + "\n",
        encoding="utf-8",
    )
    lines = [
        "# T3 共享审核载荷：AgentSociety 2 横向扩展",
        "",
        f"- 门禁：`{report['gate']}`",
        "- 新模型调用：0（复用 v2 六个 reviewer evidence_id 与审核对象）",
        f"- AgentSociety 可评价运输：{len(evaluable)}/{len(cells)}",
        (
            "- AgentSociety payload transport："
            f"{report['platform_summary']['AgentSociety2']['payload_transport_pass']}/{len(evaluable)}"
        ),
        (
            "- AgentSociety functional FullPass："
            f"{report['platform_summary']['AgentSociety2']['functional_full_pass']}/{len(cells)}"
        ),
        (
            "- AgentSociety 严格角色隔离 FullPass："
            f"{report['platform_summary']['AgentSociety2']['strict_role_isolated_full_pass']}/{len(cells)}"
        ),
        "- AgentSociety 离线启动：使用基准占位凭据与本机丢弃端点；真实 API key 未读取",
        "",
        "## 解释",
        "",
        "SimpleSocialSpace 能无损传递共同审核对象并形成原生工具调用历史。",
        "但被测 receive_messages 工具只接受调用者提供的 agent_id，没有认证调用者上下文；",
        "跨角色读取探测因此被接受。接收结果也不暴露内部 message_id。",
        "这是一项被测接口能力边界，不代表 AgentSociety 2 的所有环境模块或上层部署都不安全。",
        "YuLan v2 没有做同等对抗式 ACL 探测，因此本轮不把其角色隔离状态推断为通过或失败。",
    ]
    (out / "REPORT.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    return report


def main() -> int:
    parser = argparse.ArgumentParser()
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--fixture-oracle", action="store_true")
    mode.add_argument("--historical-replay", action="store_true")
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    report = run_fixture(args.out) if args.fixture_oracle else run_historical(args.out)
    print(yaml.safe_dump(report, allow_unicode=True, sort_keys=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
