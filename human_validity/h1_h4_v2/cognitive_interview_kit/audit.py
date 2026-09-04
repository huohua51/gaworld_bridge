"""Audit generated cognitive-interview packets and anonymous record files."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from collections.abc import Iterable
from pathlib import Path
from typing import Any

FORBIDDEN_PARTICIPANT_TOKENS = (
    "condition_code",
    "source_kind",
    "expected_concept",
    "hidden_bindings",
    "correct_action",
    "expected_result",
    "feasible_plan_example_for_rule_calibration_only",
    "functional_score",
    "formal_data_collection_allowed",
    "条件A",
    "条件B",
)

FORBIDDEN_RECORD_KEYS = {
    "name",
    "real_name",
    "participant_name",
    "student_id",
    "school",
    "university",
    "phone",
    "mobile",
    "email",
    "wechat",
    "qq",
    "address",
    "contact",
}

PII_PATTERNS = {
    "email": re.compile(r"[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}", re.IGNORECASE),
    "mainland_mobile": re.compile(r"(?<!\d)1[3-9]\d{9}(?!\d)"),
    "mainland_id": re.compile(r"(?<!\d)\d{17}[0-9Xx](?!\d)"),
    "long_numeric_identifier": re.compile(r"(?<![\d-])\d{8,17}(?![\d-])"),
    "explicit_contact_label": re.compile(
        r"(?:微信|wechat|手机号|手机|电话|邮箱|email|学号|姓名|学校)\s*[:：=]\s*\S+",
        re.IGNORECASE,
    ),
}


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def walk_keys(value: Any) -> Iterable[str]:
    if isinstance(value, dict):
        for key, child in value.items():
            yield str(key)
            yield from walk_keys(child)
    elif isinstance(value, list):
        for child in value:
            yield from walk_keys(child)


def audit_public_model(
    model: dict[str, Any], private_literals: Iterable[str]
) -> list[str]:
    failures: list[str] = []
    forbidden_keys = {
        "condition",
        "condition_code",
        "source_kind",
        "hidden_bindings",
        "expected_concept",
        "correct_action",
        "expected_result",
        "other_role_cards",
    }
    leaked_keys = sorted(forbidden_keys.intersection(walk_keys(model)))
    if leaked_keys:
        failures.append(f"forbidden_public_model_keys:{','.join(leaked_keys)}")

    serialized = json.dumps(model, ensure_ascii=False, sort_keys=True)
    for literal in sorted(
        {item.strip() for item in private_literals if len(item.strip()) >= 4}
    ):
        if literal in serialized:
            failures.append(
                f"private_literal_present_sha256:{hashlib.sha256(literal.encode()).hexdigest()}"
            )
    return failures


def audit_participant_html(path: Path) -> list[str]:
    text = path.read_text(encoding="utf-8")
    lower = text.lower()
    failures: list[str] = []
    for token in FORBIDDEN_PARTICIPANT_TOKENS:
        if token.lower() in lower:
            failures.append(f"forbidden_token:{token}")
    if "<script" in lower:
        failures.append("participant_packet_contains_script")
    if "<form" in lower or "<input" in lower or "<textarea" in lower:
        failures.append("participant_packet_collects_input")
    if re.search(r"(?:src|href)=[\"'](?:https?:|//)", lower):
        failures.append("participant_packet_has_external_resource")
    if "connect-src 'none'" not in lower or "default-src 'none'" not in lower:
        failures.append("participant_packet_missing_restrictive_csp")
    return failures


def _record_text(value: Any) -> str:
    if isinstance(value, dict):
        return "\n".join(_record_text(child) for child in value.values())
    if isinstance(value, list):
        return "\n".join(_record_text(child) for child in value)
    return "" if value is None else str(value)


def audit_record(path: Path) -> list[str]:
    failures: list[str] = []
    try:
        record = json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, json.JSONDecodeError):
        return ["record_not_valid_json"]
    if not isinstance(record, dict):
        return ["record_root_not_object"]

    lowered_keys = {key.lower() for key in walk_keys(record)}
    for key in sorted(FORBIDDEN_RECORD_KEYS.intersection(lowered_keys)):
        failures.append(f"forbidden_identity_key:{key}")

    text = _record_text(record)
    for label, pattern in PII_PATTERNS.items():
        if pattern.search(text):
            failures.append(f"possible_pii:{label}")
    return failures


def audit_dist(dist: Path) -> dict[str, Any]:
    manifest_path = dist / "MANIFEST.json"
    if not manifest_path.is_file():
        return {"passed": False, "failures": ["missing_MANIFEST.json"]}
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    failures: list[str] = []
    checked_files = 0
    for relative, expected in manifest.get("output_sha256", {}).items():
        path = dist / relative
        if not path.is_file():
            failures.append(f"missing_output:{relative}")
            continue
        checked_files += 1
        if sha256_file(path) != expected:
            failures.append(f"hash_mismatch:{relative}")

    packet_dir = dist / "participant_packets"
    packets = sorted(packet_dir.glob("CI??.html")) if packet_dir.is_dir() else []
    if len(packets) != 6:
        failures.append(f"participant_packet_count:{len(packets)}")
    for packet in packets:
        failures.extend(
            f"{packet.name}:{failure}" for failure in audit_participant_html(packet)
        )
    return {
        "passed": not failures,
        "checked_manifest_files": checked_files,
        "participant_packets": len(packets),
        "failures": failures,
    }


def parse_args() -> argparse.Namespace:
    default_dist = Path(__file__).resolve().parent / "dist"
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dist", type=Path, default=default_dist)
    parser.add_argument(
        "--records",
        type=Path,
        help="Optional private directory containing exported JSON records.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    result = {"materials": audit_dist(args.dist)}
    failed = not result["materials"]["passed"]
    if args.records:
        record_results: dict[str, list[str]] = {}
        for path in sorted(args.records.glob("*.json")):
            findings = audit_record(path)
            record_results[path.name] = findings
            failed = failed or bool(findings)
        result["records"] = {
            "files_checked": len(record_results),
            "passed": not any(record_results.values()),
            "findings_by_file": record_results,
            "manual_review_still_required": True,
        }
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
