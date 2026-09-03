"""Reproduce the labeled post-hoc fenced-JSON diagnostic; never rescore cells."""

from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path
from typing import Any

from cross_platform.t3_noncode_review.protocol import (
    executor_validator,
    expected_executor,
    expected_review,
    load_tasks,
    proposer_validator,
    reviewer_validator,
)

VALIDATORS = {
    "proposer": proposer_validator,
    "reviewer": reviewer_validator,
    "executor": executor_validator,
}
PLATFORMS = ("GAWorld", "YuLan-OneSim")
VARIANTS = ("verified_support", "verified_conflict")
ROLES = ("proposer", "reviewer", "executor")


def _rows(path: Path) -> list[dict[str, Any]]:
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def _recover(raw: str) -> dict[str, Any] | None:
    text = raw.strip()
    if not text.endswith("```") or "\n" not in text:
        return None
    opening, remainder = text.split("\n", 1)
    if opening.strip().lower() != "```json":
        return None
    try:
        payload = json.loads(remainder[:-3].strip())
    except json.JSONDecodeError:
        return None
    return payload if isinstance(payload, dict) else None


def diagnose(root: Path) -> dict[str, Any]:
    cells = json.loads((root / "cell_table.json").read_text(encoding="utf-8"))
    tasks = {str(task["id"]): task for task in load_tasks()}
    strict = Counter()
    fenced = Counter()
    semantic = Counter()
    prompt_hashes: dict[tuple[str, str, str], dict[str, str]] = {}

    for cell in cells:
        platform = str(cell["extra"]["platform"])
        task_id = str(cell["extra"]["run_context"]["task_id"])
        variant = str(cell["extra"]["variant"])
        task = tasks[task_id]
        rows = _rows(root / "runs" / cell["instance_id"] / "model_trace.jsonl")
        requests = {
            str(row["call_id"]): row
            for row in rows
            if row.get("event") == "model_request"
        }
        responses: dict[str, dict[str, Any]] = {}
        prompt_hashes[(task_id, variant, platform)] = {
            str(row["agent_id"]): str(row["prompt_sha256"])
            for row in requests.values()
        }
        for row in rows:
            if row.get("event") != "model_response":
                continue
            role = str(requests[str(row["call_id"])]["agent_id"])
            strict[(platform, role)] += int(row.get("ok") is True)
            payload = dict(row.get("parsed") or {}) if row.get("ok") else None
            if payload is None:
                payload = _recover(str(row.get("raw_response") or ""))
                if payload is not None:
                    fenced[(platform, role)] += 1
            if payload is None or VALIDATORS[role](payload):
                raise ValueError(
                    f"unrecoverable response: {cell['instance_id']}:{role}"
                )
            responses[role] = payload

        expected_proposal = {
            "proposal_id": str(task["proposal_id"]),
            "proposed_state": dict(task["proposed_state"]),
            "reason_code": "registered_candidate_submitted",
        }
        expected_reviewer = expected_review(task, variant)
        reviewer = responses["reviewer"]
        delivered = cell["process_profile"]["delivered_review"]
        semantic["proposer_oracle_exact"] += int(
            responses["proposer"] == expected_proposal
        )
        semantic["reviewer_full_oracle_exact"] += int(
            reviewer == expected_reviewer
        )
        semantic["reviewer_core_oracle_exact"] += int(
            all(
                reviewer.get(key) == expected_reviewer[key]
                for key in (
                    "decision",
                    "evidence_ids",
                    "failing_criteria",
                    "reason_code",
                )
            )
        )
        semantic["executor_observed_path_exact"] += int(
            responses["executor"] == expected_executor(task, delivered)
        )
        oracle_review = {
            **expected_reviewer,
            "review_id": f"{task_id}_r1",
        }
        semantic["final_state_oracle_exact"] += int(
            responses["executor"].get("final_state")
            == expected_executor(task, oracle_review)["final_state"]
        )

    stage_parity = {
        role: sum(
            prompt_hashes[(task_id, variant, PLATFORMS[0])][role]
            == prompt_hashes[(task_id, variant, PLATFORMS[1])][role]
            for task_id in tasks
            for variant in VARIANTS
        )
        for role in ROLES
    }
    return {
        "diagnostic_kind": "posthoc_fenced_json_does_not_change_primary_score",
        "cells": len(cells),
        "strict_valid_by_platform_role": {
            platform: {role: strict[(platform, role)] for role in ROLES}
            for platform in PLATFORMS
        },
        "fenced_recovered_by_platform_role": {
            platform: {role: fenced[(platform, role)] for role in ROLES}
            for platform in PLATFORMS
        },
        "fenced_recovered_total": sum(fenced.values()),
        "semantic_counts": dict(semantic),
        "stage_prompt_hash_exact": stage_parity,
        "pair_denominator": len(tasks) * len(VARIANTS),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(diagnose(args.root), ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
