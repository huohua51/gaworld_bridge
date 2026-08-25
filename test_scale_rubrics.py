from pathlib import Path

from score_scale_rubrics import load_json, score_suite

ROOT = Path(__file__).parent
SUITE = load_json(ROOT / "rubrics" / "suite_v0_1.json")


def test_capable_batch_is_ranking_eligible() -> None:
    report = score_suite(SUITE, load_json(ROOT / "fixtures" / "capable_traces.json"))
    assert report["pair_coverage"] == 1.0
    assert report["macro_pair_accuracy"] == 1.0
    assert report["ranking_eligible"] is True
    assert {item["pair_id"]: item["pair_accuracy"] for item in report["pairs"]} == {
        "trust_reciprocity_scale_001": 1,
        "reservation_wage_apply_001": 1,
    }


def test_locked_strategy_fails_pairs_not_half_credit() -> None:
    report = score_suite(SUITE, load_json(ROOT / "fixtures" / "locked_yes_traces.json"))
    assert report["pair_coverage"] == 1.0
    assert report["macro_pair_accuracy"] == 0.0
    for item in report["pairs"]:
        assert item["control"]["success"] == 1
        assert item["intervention"]["success"] == 0
        assert item["pair_accuracy"] == 0


def test_missing_action_is_not_scored_as_zero() -> None:
    batch = {
        "batch_id": "missing",
        "pairs": {
            "trust_reciprocity_scale_001": {
                "control": {"interview": "我说我很信任。"},
                "intervention": {"interview": "我还是很信任。"},
            },
            "reservation_wage_apply_001": {
                "control": {"target_action": {"payload": {"decision": "accept"}}},
                "intervention": {"target_action": {"payload": {"decision": "reject"}}},
            },
        },
    }
    report = score_suite(SUITE, batch)
    trust = next(item for item in report["pairs"] if item["pair_id"] == "trust_reciprocity_scale_001")
    job = next(item for item in report["pairs"] if item["pair_id"] == "reservation_wage_apply_001")
    assert trust["evaluable"] is False
    assert trust["pair_accuracy"] is None
    assert job["pair_accuracy"] == 1
    assert report["pair_coverage"] == 0.5
    assert report["ranking_eligible"] is False
