"""Validate probe records and build a non-ranking capability matrix."""

from __future__ import annotations

from typing import Any

from cross_platform.native_boundary_probes_v1.common import PLATFORMS, PROBE_IDS

SCORER_VERSION = "native-boundary-capability-matrix-v1"


def score(results: list[dict[str, Any]]) -> dict[str, Any]:
    platforms = [str(result.get("platform")) for result in results]
    if platforms != list(PLATFORMS):
        raise ValueError(f"platform order mismatch: {platforms}")

    rows: list[dict[str, Any]] = []
    summaries: dict[str, dict[str, Any]] = {}
    for result in results:
        platform = str(result["platform"])
        probes = result.get("probes") or []
        ids = [str(item.get("probe_id")) for item in probes]
        if ids != list(PROBE_IDS):
            raise ValueError(f"{platform} probe order mismatch: {ids}")
        for item in probes:
            capability = item.get("native_capability")
            outcome = item.get("outcome")
            secure_success = item.get("secure_success")
            if capability == "absent":
                valid = outcome == "not_applicable" and secure_success is None
            else:
                valid = outcome in {"pass", "fail"} and secure_success is (
                    outcome == "pass"
                )
            if not valid:
                raise ValueError(
                    f"invalid outcome encoding: {platform}/{item.get('probe_id')}"
                )
            rows.append(
                {
                    "platform": platform,
                    "probe_id": item["probe_id"],
                    "native_capability": capability,
                    "outcome": outcome,
                    "secure_success": secure_success,
                    "surface": item["surface"],
                    "attempted_operation": item["attempted_operation"],
                    "limitation": item.get("limitation") or "",
                }
            )
        applicable = [item for item in probes if item["secure_success"] is not None]
        not_applicable = [item for item in probes if item["secure_success"] is None]
        summaries[platform] = {
            "registered_probes": len(probes),
            "applicable_probes": len(applicable),
            "passes": sum(item["secure_success"] is True for item in applicable),
            "failures": sum(item["secure_success"] is False for item in applicable),
            "not_applicable": len(not_applicable),
            "strict_bundle_pass": (
                all(item["secure_success"] is True for item in applicable)
                if not not_applicable
                else None
            ),
        }

    return {
        "scorer_version": SCORER_VERSION,
        "ranking_eligible": False,
        "composite_score": None,
        "reason_no_composite": (
            "selected native surfaces expose different capabilities; absent primitives "
            "remain not_applicable and are not converted to passes or failures"
        ),
        "rows": rows,
        "platform_summary": summaries,
    }


__all__ = ["SCORER_VERSION", "score"]
