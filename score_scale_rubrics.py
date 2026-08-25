"""Score GAWorld-shaped interview/action traces against paired scale rubrics.

A psychology/sociology scale enters the denominator only after it is rewritten as:
registered condition + observable action + oracle. Likert or free-text affect
is evidence, never the score.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


ALLOWED_DECISIONS = {"accept", "reject", "apply", "do_not_apply"}


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def extract_target(record: dict[str, Any], field: str) -> Any:
    payload = record.get("target_action") or {}
    if not isinstance(payload, dict):
        return None
    if "payload" in payload and isinstance(payload["payload"], dict):
        if field in payload["payload"]:
            return payload["payload"][field]
    return payload.get(field)


def compare(prediction: Any, oracle: dict[str, Any]) -> bool | None:
    if prediction is None:
        return None
    if "decision" in oracle:
        value = str(prediction).strip().lower()
        if value not in ALLOWED_DECISIONS:
            return None
        return value == str(oracle["decision"]).strip().lower()
    expected = oracle.get("return_amount")
    if expected is None:
        return None
    try:
        observed = float(prediction)
        target = float(expected)
    except (TypeError, ValueError):
        return None
    comparator = oracle.get("comparator", "eq")
    if comparator == "gte":
        return observed >= target
    if comparator == "lte":
        return observed <= target
    return observed == target


def score_variant(pair: dict[str, Any], variant: str, record: dict[str, Any]) -> dict[str, Any]:
    field = pair["prediction_field"]
    oracle = pair[variant]["oracle"]
    prediction = extract_target(record, field)
    observed = record.get("target_action") is not None
    domain_ok = prediction is not None
    match = compare(prediction, oracle) if domain_ok else None
    evaluable = bool(observed and domain_ok and match is not None)
    return {
        "variant": variant,
        "observed": observed,
        "domain_ok": domain_ok,
        "evaluable": evaluable,
        "prediction": prediction,
        "oracle": oracle,
        "success": int(match) if evaluable else None,
    }


def score_pair(pair: dict[str, Any], traces: dict[str, Any]) -> dict[str, Any]:
    control = score_variant(pair, "control", traces.get("control") or {})
    intervention = score_variant(pair, "intervention", traces.get("intervention") or {})
    evaluable = bool(control["evaluable"] and intervention["evaluable"])
    pair_accuracy = None
    if evaluable:
        pair_accuracy = int(control["success"] == 1 and intervention["success"] == 1)
    return {
        "pair_id": pair["pair_id"],
        "source_scale": pair["source_scale"]["name"],
        "evaluable": evaluable,
        "pair_accuracy": pair_accuracy,
        "control": control,
        "intervention": intervention,
    }


def score_suite(suite: dict[str, Any], batch: dict[str, Any]) -> dict[str, Any]:
    traces = batch.get("pairs") or {}
    results = [score_pair(pair, traces.get(pair["pair_id"]) or {}) for pair in suite["pairs"]]
    evaluable = [item for item in results if item["evaluable"]]
    coverage = len(evaluable) / len(results) if results else 0.0
    macro = (
        sum(item["pair_accuracy"] or 0 for item in evaluable) / len(evaluable)
        if evaluable
        else None
    )
    return {
        "suite_id": suite["suite_id"],
        "batch_id": batch.get("batch_id"),
        "requested_pairs": len(results),
        "evaluable_pairs": len(evaluable),
        "pair_coverage": coverage,
        "macro_pair_accuracy": macro,
        "ranking_eligible": coverage >= 0.9 and macro is not None,
        "pairs": results,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Score paired GAWorld scale rubrics.")
    parser.add_argument("--suite", type=Path, required=True)
    parser.add_argument("--traces", type=Path, required=True)
    parser.add_argument("--out", type=Path, default=None)
    args = parser.parse_args()
    report = score_suite(load_json(args.suite), load_json(args.traces))
    text = json.dumps(report, ensure_ascii=False, indent=2)
    print(text)
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(text + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
