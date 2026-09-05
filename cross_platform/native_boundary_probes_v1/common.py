"""Shared contracts and serialization helpers for native-boundary probes."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

EXPERIMENT_ID = "CROSS-PLATFORM-NATIVE-BOUNDARY-PROBES-v1"
PROTOCOL_VERSION = "native-boundary-probes-v1"
PLATFORMS = ("GAWorld", "YuLan-OneSim", "AgentSociety2")
PROBE_IDS = (
    "P1_identity_impersonation",
    "P2_private_data_read",
    "P3_unauthorized_final_write",
    "P4_message_traceability",
)


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2, default=str) + "\n",
        encoding="utf-8",
    )


def probe(
    probe_id: str,
    *,
    surface: str,
    capability: str,
    secure_success: bool | None,
    attempted_operation: str,
    evidence: dict[str, Any],
    limitation: str = "",
) -> dict[str, Any]:
    if probe_id not in PROBE_IDS:
        raise ValueError(f"unknown probe_id: {probe_id}")
    if capability not in {"present", "absent"}:
        raise ValueError(f"invalid capability: {capability}")
    if capability == "absent" and secure_success is not None:
        raise ValueError("absent capability must use secure_success=None")
    if capability == "present" and secure_success is None:
        raise ValueError("present capability needs a boolean secure_success")
    return {
        "probe_id": probe_id,
        "surface": surface,
        "native_capability": capability,
        "secure_success": secure_success,
        "outcome": (
            "not_applicable"
            if secure_success is None
            else "pass"
            if secure_success
            else "fail"
        ),
        "attempted_operation": attempted_operation,
        "evidence": evidence,
        "limitation": limitation,
    }


__all__ = [
    "EXPERIMENT_ID",
    "PLATFORMS",
    "PROBE_IDS",
    "PROTOCOL_VERSION",
    "probe",
    "sha256_file",
    "write_json",
]
