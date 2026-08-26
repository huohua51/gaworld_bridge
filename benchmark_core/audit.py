"""Read-only conformance audit for source cards and frozen evidence bundles."""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
from collections import Counter
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

import yaml

from benchmark_core.task_card import validate_task_card


@dataclass(frozen=True)
class AuditIssue:
    severity: str
    code: str
    path: str
    detail: str = ""


@dataclass
class AuditReport:
    root: str
    cards_checked: int = 0
    freezes_checked: int = 0
    cells_checked: int = 0
    zero_byte_files: int = 0
    issues: list[AuditIssue] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not any(issue.severity == "error" for issue in self.issues)

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["ok"] = self.ok
        payload["issue_counts"] = {
            severity: sum(1 for issue in self.issues if issue.severity == severity)
            for severity in ("error", "warning", "info")
        }
        return payload


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _commit_exists(root: Path, commit: str) -> bool:
    if not commit:
        return False
    result = subprocess.run(
        ["git", "cat-file", "-e", f"{commit}^{{commit}}"],
        cwd=root,
        capture_output=True,
        check=False,
        text=True,
    )
    return result.returncode == 0


def _load_yaml(path: Path) -> dict[str, Any]:
    payload = yaml.safe_load(path.read_text(encoding="utf-8"))
    return payload if isinstance(payload, dict) else {}


def _audit_task_card(report: AuditReport, path: Path, root: Path) -> None:
    report.cards_checked += 1
    relative = str(path.relative_to(root))
    try:
        card = _load_yaml(path)
    except (OSError, UnicodeError, yaml.YAMLError) as exc:
        report.issues.append(
            AuditIssue("error", "task_card_unreadable", relative, str(exc))
        )
        return
    validation = validate_task_card(card)
    schema_version = int(card.get("schema_version") or 0)
    severity = "error" if schema_version >= 1 else "warning"
    report.issues.extend(
        AuditIssue(severity, error, relative) for error in validation.errors
    )
    report.issues.extend(
        AuditIssue("warning", warning, relative) for warning in validation.warnings
    )


def _audit_freeze(report: AuditReport, entry: dict[str, Any], root: Path) -> None:
    result_dir = root / str(entry.get("result_dir") or "")
    source_dir = root / str(entry.get("source_dir") or "")
    freeze_path = result_dir / "FREEZE.yaml"
    if not freeze_path.is_file() or freeze_path.stat().st_size == 0:
        report.issues.append(
            AuditIssue("error", "freeze_missing", str(freeze_path.relative_to(root)))
        )
        return

    report.freezes_checked += 1
    freeze = _load_yaml(freeze_path)
    base_commit = str(freeze.get("base_commit") or "")
    if not _commit_exists(root, base_commit):
        report.issues.append(
            AuditIssue(
                "error",
                "freeze_base_commit_missing",
                str(freeze_path.relative_to(root)),
                base_commit,
            )
        )

    for hash_key, relative_source in (entry.get("hash_files") or {}).items():
        source = source_dir / str(relative_source)
        expected = str(freeze.get(hash_key) or "")
        if not source.is_file():
            report.issues.append(
                AuditIssue(
                    "error",
                    "frozen_source_missing",
                    str(source.relative_to(root)),
                    str(hash_key),
                )
            )
            continue
        actual = _sha256(source)
        if not expected:
            report.issues.append(
                AuditIssue(
                    "warning",
                    "freeze_hash_not_registered",
                    str(source.relative_to(root)),
                    str(hash_key),
                )
            )
        elif actual != expected:
            report.issues.append(
                AuditIssue(
                    "error",
                    "freeze_hash_mismatch",
                    str(source.relative_to(root)),
                    f"{hash_key}: expected={expected} actual={actual}",
                )
            )


def _audit_cells(report: AuditReport, root: Path) -> None:
    output = root / "output"
    if not output.is_dir():
        return
    for path in output.rglob("cell_result.json"):
        report.cells_checked += 1
        relative = str(path.relative_to(root))
        if path.stat().st_size == 0:
            report.issues.append(AuditIssue("error", "cell_result_empty", relative))
            continue
        try:
            cell = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, UnicodeError, json.JSONDecodeError) as exc:
            report.issues.append(
                AuditIssue("error", "cell_result_unreadable", relative, str(exc))
            )
            continue
        if not isinstance(cell, dict):
            report.issues.append(
                AuditIssue("error", "cell_result_not_object", relative)
            )
            continue
        critical = [
            criterion
            for criterion in cell.get("criteria") or []
            if criterion.get("critical") and criterion.get("evaluable")
        ]
        if (
            cell.get("measurement_valid")
            and cell.get("full_pass") is not None
            and not critical
        ):
            report.issues.append(
                AuditIssue("error", "critical_criterion_missing", relative)
            )
        if any(not criterion.get("evidence_ids") for criterion in critical):
            report.issues.append(
                AuditIssue("warning", "critical_evidence_id_missing", relative)
            )


def audit_repository(root: Path, catalog_path: Path | None = None) -> AuditReport:
    root = root.resolve()
    report = AuditReport(root=str(root))
    report.zero_byte_files = sum(
        1 for path in root.rglob("*") if path.is_file() and path.stat().st_size == 0
    )

    for path in root.rglob("task_card.yaml"):
        if "output" not in path.relative_to(root).parts:
            _audit_task_card(report, path, root)

    catalog_file = catalog_path or root / "benchmark_catalog.yaml"
    if catalog_file.is_file():
        catalog = _load_yaml(catalog_file)
        for entry in catalog.get("experiments") or []:
            if isinstance(entry, dict) and entry.get("result_dir"):
                _audit_freeze(report, entry, root)
    else:
        report.issues.append(
            AuditIssue("warning", "catalog_missing", str(catalog_file))
        )

    _audit_cells(report, root)
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", type=Path, default=Path.cwd())
    parser.add_argument("--catalog", type=Path)
    parser.add_argument("--json", action="store_true", dest="as_json")
    parser.add_argument("--max-issues", type=int, default=50)
    args = parser.parse_args()

    report = audit_repository(args.repo, args.catalog)
    payload = report.to_dict()
    if args.as_json:
        payload["issues"] = payload["issues"][: args.max_issues]
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    else:
        print(
            f"ok={report.ok} cards={report.cards_checked} freezes={report.freezes_checked} "
            f"cells={report.cells_checked} zero_byte_files={report.zero_byte_files}"
        )
        severity_counts = Counter(issue.severity for issue in report.issues)
        code_counts = Counter(issue.code for issue in report.issues)
        print(
            "issue_counts="
            + ",".join(
                f"{name}:{severity_counts.get(name, 0)}"
                for name in ("error", "warning", "info")
            )
        )
        print(
            "top_codes="
            + ",".join(f"{code}:{count}" for code, count in code_counts.most_common(12))
        )
        for issue in report.issues[: args.max_issues]:
            suffix = f" ({issue.detail})" if issue.detail else ""
            print(f"{issue.severity}: {issue.code}: {issue.path}{suffix}")
        if len(report.issues) > args.max_issues:
            print(f"... {len(report.issues) - args.max_issues} more issues")
    return 0 if report.ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
