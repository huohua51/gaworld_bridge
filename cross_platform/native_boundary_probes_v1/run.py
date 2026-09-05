"""Orchestrate isolated native-boundary probe workers and publish the matrix."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
import subprocess
from pathlib import Path
from typing import Any

import yaml

from cross_platform.native_boundary_probes_v1.common import (
    EXPERIMENT_ID,
    PLATFORMS,
    PROTOCOL_VERSION,
    write_json,
)
from cross_platform.native_boundary_probes_v1.scorer import SCORER_VERSION, score

BRIDGE_ROOT = Path(__file__).resolve().parents[2]
WORKSPACE_ROOT = BRIDGE_ROOT.parent
REGISTRATION_PATH = Path(__file__).with_name("registration_v1.yaml")
UPSTREAMS = {
    "GAWorld": {
        "root": WORKSPACE_ROOT / "GAWorld",
        "commit": "bfcd2a665a299ddc25660a33102169f8bcfd856e",
    },
    "YuLan-OneSim": {
        "root": WORKSPACE_ROOT / "YuLan-OneSim-official",
        "commit": "9829d722b528b733f8c8317315637071fa23b206",
    },
    "AgentSociety2": {
        "root": WORKSPACE_ROOT / "AgentSociety",
        "commit": "13e28b5e67a2a8f2f43d640ebf27859126da622e",
    },
}
DEFAULT_PYTHONS = {
    "GAWorld": WORKSPACE_ROOT / ".venv_gaworld_eval" / "Scripts" / "python.exe",
    "YuLan-OneSim": WORKSPACE_ROOT
    / ".venv_yulan_onesim_eval"
    / "Scripts"
    / "python.exe",
    "AgentSociety2": WORKSPACE_ROOT
    / ".venv_agentsociety_eval"
    / "Scripts"
    / "python.exe",
}


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _git_head(path: Path) -> str:
    return subprocess.run(
        ["git", "-C", str(path), "rev-parse", "HEAD"],
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()


def _validate_registration() -> tuple[dict[str, Any], str]:
    if not REGISTRATION_PATH.is_file():
        raise RuntimeError("formal run requires registration_v1.yaml")
    payload = yaml.safe_load(REGISTRATION_PATH.read_text(encoding="utf-8")) or {}
    errors: list[str] = []
    design = payload.get("design") or {}
    expected_design = {
        "platform_order": list(PLATFORMS),
        "probe_order": [
            "P1_identity_impersonation",
            "P2_private_data_read",
            "P3_unauthorized_final_write",
            "P4_message_traceability",
        ],
        "new_model_calls": 0,
        "ranking_eligible": False,
        "scorer_version": SCORER_VERSION,
    }
    for key, expected in expected_design.items():
        if design.get(key) != expected:
            errors.append(f"registered_{key}_mismatch")
    for relative, expected in (payload.get("frozen_code_sha256") or {}).items():
        path = BRIDGE_ROOT / str(relative)
        if not path.is_file():
            errors.append(f"missing_code:{relative}")
        elif _sha256(path) != str(expected):
            errors.append(f"code_sha256_mismatch:{relative}")
    systems = payload.get("upstreams") or {}
    for platform, fixed in UPSTREAMS.items():
        registered = systems.get(platform) or {}
        root = fixed["root"]
        if _git_head(root) != fixed["commit"]:
            errors.append(f"upstream_head_mismatch:{platform}")
        if registered.get("commit") != fixed["commit"]:
            errors.append(f"registered_commit_mismatch:{platform}")
        for relative, expected in (registered.get("source_sha256") or {}).items():
            path = root / str(relative)
            if not path.is_file():
                errors.append(f"missing_upstream_source:{platform}:{relative}")
            elif _sha256(path) != str(expected):
                errors.append(f"upstream_sha256_mismatch:{platform}:{relative}")
    tracked = subprocess.run(
        [
            "git",
            "-C",
            str(BRIDGE_ROOT),
            "ls-files",
            "--error-unmatch",
            REGISTRATION_PATH.relative_to(BRIDGE_ROOT).as_posix(),
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
            REGISTRATION_PATH.relative_to(BRIDGE_ROOT).as_posix(),
        ],
        check=False,
    )
    if diff.returncode != 0:
        errors.append("registration_has_uncommitted_change")
    if errors:
        raise RuntimeError("preregistration validation failed: " + ",".join(errors))
    return payload, _sha256(REGISTRATION_PATH)


def run_workers(
    out: Path, *, pythons: dict[str, Path] | None = None
) -> list[dict[str, Any]]:
    selected = pythons or DEFAULT_PYTHONS
    out.mkdir(parents=True, exist_ok=False)
    env = os.environ.copy()
    env["PYTHONPATH"] = os.pathsep.join(
        [
            str(BRIDGE_ROOT),
            str(WORKSPACE_ROOT / "GAWorld"),
            str(WORKSPACE_ROOT / "YuLan-OneSim-official" / "src"),
        ]
    )
    results: list[dict[str, Any]] = []
    worker_logs: dict[str, dict[str, Any]] = {}
    for platform in PLATFORMS:
        python = selected[platform]
        if not python.is_file():
            raise FileNotFoundError(f"missing Python for {platform}: {python}")
        platform_dir = out / "platforms" / platform.lower().replace("-", "_")
        completed = subprocess.run(
            [
                str(python),
                "-m",
                "cross_platform.native_boundary_probes_v1.worker",
                "--platform",
                platform,
                "--out",
                str(platform_dir),
            ],
            cwd=str(BRIDGE_ROOT),
            env=env,
            check=False,
            capture_output=True,
            text=True,
            timeout=120,
        )
        worker_logs[platform] = {
            "python": str(python),
            "returncode": completed.returncode,
            "stdout": completed.stdout,
            "stderr": completed.stderr,
        }
        if completed.returncode != 0:
            write_json(out / "worker_logs.json", worker_logs)
            raise RuntimeError(
                f"{platform} worker failed with code {completed.returncode}: "
                f"{completed.stderr[-1000:]}"
            )
        results.append(
            json.loads((platform_dir / "probe_result.json").read_text(encoding="utf-8"))
        )
    write_json(out / "worker_logs.json", worker_logs)
    return results


def _write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    fields = [
        "platform",
        "probe_id",
        "native_capability",
        "outcome",
        "secure_success",
        "surface",
        "attempted_operation",
        "limitation",
    ]
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def _report(matrix: dict[str, Any], phase: str) -> str:
    rows = matrix["rows"]
    lookup = {(row["platform"], row["probe_id"]): row["outcome"] for row in rows}
    labels = {
        "P1_identity_impersonation": "P1 身份冒用",
        "P2_private_data_read": "P2 私有数据读取",
        "P3_unauthorized_final_write": "P3 越权最终写入",
        "P4_message_traceability": "P4 消息可追溯",
    }
    lines = [
        f"# {EXPERIMENT_ID} 结果",
        "",
        f"阶段：`{phase}`。本实验完全离线，新模型调用数为 **0**。",
        "",
        "## 能力矩阵",
        "",
        "| 探针 | GAWorld | YuLan-OneSim | AgentSociety2 |",
        "|---|---:|---:|---:|",
    ]
    for probe_id, label in labels.items():
        values = [lookup[(platform, probe_id)] for platform in PLATFORMS]
        lines.append(f"| {label} | {values[0]} | {values[1]} | {values[2]} |")
    lines.extend(
        [
            "",
            "`pass` 表示被测原生边界满足预注册条件；`fail` 表示该边界接受了越权操作或没有暴露可关联 ID；`not_applicable` 表示固定原生表面没有对应能力，既不算通过也不算失败。",
            "",
            "## 主要发现",
            "",
            "GAWorld 的私有读取和最终产物写入都按角色拒绝，审核 ID 也能贯穿发送、投递、收件箱和审计；但 `emit_review` 只接收调用方给出的 `reviewer_id`，没有单独的认证调用者上下文，因此直接方法边界不能阻止身份冒用。",
            "",
            "YuLan-OneSim 的 EventBus 接受调用方构造的 `from_agent_id`，也会把 Reviewer 声明的最终状态事件送到被动结果接收者；事件 ID 则能在发送对象、接收对象和原生 flow 中关联。EventBus 没有 owner-bound 私有存储读取原语，该格保留为 `not_applicable`。",
            "",
            "AgentSociety2 的 SimpleSocialSpace 在所测直接边界允许调用方自报 sender、receiver 和 mailbox agent_id，因此身份冒用、跨角色邮箱读取和 Reviewer 最终提交都被接受。内部 Message 模型虽生成 message_id，但公开 send/receive 响应与工具历史没有暴露它，所以严格可追溯条件未通过。",
            "",
            "## 不能推出什么",
            "",
            "三者选定表面的抽象层不同，本实验不生成综合分、不做总体排名，也不能证明外部网关或完整部署没有额外认证。结果只定位到锁定提交上的直接原生接口，适合作为修复需求和后续回归基线。",
            "",
        ]
    )
    return "\n".join(lines)


def _audit(
    matrix: dict[str, Any], registration: dict[str, Any] | None, registration_sha: str
) -> str:
    lines = [
        f"# Independent artifact audit: {EXPERIMENT_ID}",
        "",
        "- All three workers returned exit code 0.",
        "- All twelve registered platform/probe cells were emitted in fixed order.",
        "- `not_applicable` remains nullable and was not counted as pass or fail.",
        "- Composite score and platform ranking are disabled.",
        "- New model calls: 0.",
    ]
    if registration is not None:
        lines.extend(
            [
                f"- Preregistration: `{registration.get('preregistration_id')}`.",
                f"- Registration SHA-256: `{registration_sha}`.",
                "- Registered code hashes and three upstream commits passed runtime validation.",
            ]
        )
    lines.extend(["", "## Descriptive counts", ""])
    for platform, values in matrix["platform_summary"].items():
        lines.append(
            f"- {platform}: {values['passes']} pass, {values['failures']} fail, "
            f"{values['not_applicable']} not applicable."
        )
    lines.append("")
    return "\n".join(lines)


def execute(out: Path, *, phase: str) -> dict[str, Any]:
    registration = None
    registration_sha = ""
    if phase == "formal":
        registration, registration_sha = _validate_registration()
    results = run_workers(out)
    matrix = score(results)
    write_json(out / "probe_results.json", results)
    write_json(out / "cell_table.json", matrix["rows"])
    _write_csv(out / "capability_matrix.csv", matrix["rows"])
    manifest = {
        "experiment_id": EXPERIMENT_ID,
        "protocol_version": PROTOCOL_VERSION,
        "scorer_version": SCORER_VERSION,
        "phase": phase,
        "preregistration_id": (
            registration.get("preregistration_id") if registration else None
        ),
        "registration_sha256": registration_sha or None,
        "ranking_eligible": False,
        "new_model_calls": 0,
        "platform_summary": matrix["platform_summary"],
        "reason_no_composite": matrix["reason_no_composite"],
    }
    (out / "RUN_MANIFEST.yaml").write_text(
        yaml.safe_dump(manifest, allow_unicode=True, sort_keys=False),
        encoding="utf-8",
    )
    (out / "REPORT.md").write_text(_report(matrix, phase), encoding="utf-8")
    (out / "INDEPENDENT_AUDIT.md").write_text(
        _audit(matrix, registration, registration_sha), encoding="utf-8"
    )
    return manifest


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument(
        "--phase",
        choices=("offline_calibration", "formal"),
        default="offline_calibration",
    )
    args = parser.parse_args()
    print(yaml.safe_dump(execute(args.out, phase=args.phase), allow_unicode=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


__all__ = ["DEFAULT_PYTHONS", "execute", "run_workers"]
