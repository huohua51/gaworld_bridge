import hashlib
import json
from pathlib import Path

import yaml

from benchmark_core.audit import audit_repository


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def test_audit_detects_empty_cell_and_hash_mismatch(tmp_path: Path) -> None:
    source = tmp_path / "exp"
    result = tmp_path / "output" / "run"
    task_card = source / "task_card.yaml"
    _write(
        task_card,
        yaml.safe_dump(
            {
                "schema_version": 1,
                "task_id": "task",
                "task_family": "T3",
                "target_axis": "functional",
                "mechanism": ["M3"],
                "control": {},
                "variant": {},
                "oracle": {},
                "required_events": [],
                "primary_metric": "FullPass",
                "diagnostic_metrics": [],
                "human_reference": "N/A",
            }
        ),
    )
    _write(
        result / "FREEZE.yaml",
        yaml.safe_dump({"task_card_hash": "bad", "base_commit": "missing"}),
    )
    _write(result / "runs" / "cell" / "cell_result.json", "")
    _write(
        tmp_path / "benchmark_catalog.yaml",
        yaml.safe_dump(
            {
                "experiments": [
                    {
                        "source_dir": "exp",
                        "result_dir": "output/run",
                        "hash_files": {"task_card_hash": "task_card.yaml"},
                    }
                ]
            }
        ),
    )

    report = audit_repository(tmp_path)
    codes = {issue.code for issue in report.issues}

    assert report.ok is False
    assert "cell_result_empty" in codes
    assert "freeze_hash_mismatch" in codes
    assert "freeze_base_commit_missing" in codes
    assert hashlib.sha256(task_card.read_bytes()).hexdigest() != "bad"


def test_audit_warns_when_critical_result_has_no_evidence(tmp_path: Path) -> None:
    cell = {
        "measurement_valid": True,
        "full_pass": 1,
        "criteria": [{"critical": True, "evaluable": True, "evidence_ids": []}],
    }
    _write(
        tmp_path / "output" / "run" / "runs" / "cell" / "cell_result.json",
        json.dumps(cell),
    )

    report = audit_repository(tmp_path)

    assert any(issue.code == "critical_evidence_id_missing" for issue in report.issues)
