from benchmark_core.task_card import validate_task_card


def _card() -> dict:
    return {
        "task_id": "TASK-T3-001",
        "task_family": "T3",
        "target_axis": "functional",
        "mechanism": ["M3", "M5"],
        "control": {"communication": "on"},
        "variant": {"communication": "drop"},
        "oracle": {"result": "registered"},
        "required_events": ["message_sent", "message_adopted"],
        "primary_metric": "FullPass",
        "diagnostic_metrics": ["first_error"],
        "human_reference": "N/A",
    }


def test_valid_task_card() -> None:
    result = validate_task_card(_card())
    assert result.valid is True
    assert result.errors == ()


def test_task_card_rejects_renamed_family_and_missing_fields() -> None:
    card = _card()
    card["task_family"] = "L1"
    del card["oracle"]

    result = validate_task_card(card)

    assert result.valid is False
    assert "invalid_task_family:L1" in result.errors
    assert "missing:oracle" in result.errors
