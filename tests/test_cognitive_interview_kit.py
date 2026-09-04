from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

from human_validity.h1_h4_v2.cognitive_interview_kit.audit import (
    audit_dist,
    audit_participant_html,
    audit_record,
)
from human_validity.h1_h4_v2.cognitive_interview_kit.generate import (
    DEFAULT_OUT,
    FAMILY_FILES,
    H1H4_DIR,
    KIT_DIR,
    REPO_ROOT,
    generate,
    load_yaml,
    prepare_output,
    role_for,
    surface_for,
    validate_assignments,
)


def source_materials() -> tuple[dict, dict, dict]:
    config = load_yaml(KIT_DIR / "assignments.yaml")
    tasks = {
        family: load_yaml(H1H4_DIR / "tasks" / directory / "task_card.yaml")
        for family, directory in FAMILY_FILES.items()
    }
    instructions = {
        family: load_yaml(
            H1H4_DIR / "tasks" / directory / "participant_instructions.yaml"
        )
        for family, directory in FAMILY_FILES.items()
    }
    return config, tasks, instructions


def test_assignments_cover_each_family_role_once_and_balance_hidden_conditions() -> (
    None
):
    config, tasks, instructions = source_materials()
    validate_assignments(config, tasks, instructions)
    cards = [
        card for assignment in config["assignments"] for card in assignment["cards"]
    ]
    assert len(cards) == 12
    assert len({(card["family"], card["role_id"]) for card in cards}) == 12
    assert [card["condition"] for card in cards].count("A") == 6
    assert [card["condition"] for card in cards].count("B") == 6


def test_generation_is_deterministic_and_packets_are_isolated(tmp_path: Path) -> None:
    first = tmp_path / "first"
    second = tmp_path / "second"
    manifest_a = generate(first)
    manifest_b = generate(second)
    assert manifest_a == manifest_b
    assert audit_dist(first)["passed"] is True
    assert audit_dist(second)["passed"] is True

    config, tasks, instructions = source_materials()
    for assignment in config["assignments"]:
        interview_id = assignment["interview_id"]
        packet = first / "participant_packets" / f"{interview_id}.html"
        text = packet.read_text(encoding="utf-8")
        assert audit_participant_html(packet) == []
        assert set(re.findall(r"CI\d{2}", text)) == {interview_id}
        for card in assignment["cards"]:
            family = card["family"]
            assert (
                role_for(instructions[family], card["role_id"])["screen_title"] in text
            )
            assert surface_for(tasks[family], card["surface_id"])["label"] in text
            for item in instructions[family]["pre_task_comprehension"]["items"]:
                assert item["prompt"] in text
                assert item["expected_concept"] not in text


def test_committed_distribution_hashes_and_leak_audit_are_current() -> None:
    result = audit_dist(DEFAULT_OUT)
    assert result["passed"] is True, result["failures"]
    leak_report = json.loads(
        (DEFAULT_OUT / "LEAK_AUDIT.json").read_text(encoding="utf-8")
    )
    assert leak_report["passed"] is True
    assert len(leak_report["packets"]) == 6
    facilitator = (DEFAULT_OUT / "admin" / "facilitator_record.html").read_text(
        encoding="utf-8"
    )
    assert "split(/\\r?\\n/)" in facilitator
    assert "JSON.stringify(record,null,2)+'\\n'" in facilitator


def test_record_audit_does_not_echo_content_and_detects_common_pii(
    tmp_path: Path,
) -> None:
    safe = tmp_path / "safe.json"
    safe.write_text(
        json.dumps(
            {
                "interview_id": "CI01",
                "material_version": "CIKIT-example",
                "consent": True,
                "ambiguous_phrases": ["结束条件不清楚"],
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    assert audit_record(safe) == []

    unsafe = tmp_path / "unsafe.json"
    unsafe.write_text(
        json.dumps(
            {
                "interview_id": "CI01",
                "participant_name": "不应保存",
                "feedback": "联系邮箱 test.person@example.org",
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    findings = audit_record(unsafe)
    assert "forbidden_identity_key:participant_name" in findings
    assert "possible_pii:email" in findings
    assert all(
        "test.person" not in finding and "不应保存" not in finding
        for finding in findings
    )


def test_output_replacement_requires_owned_marker_and_rejects_broad_paths(
    tmp_path: Path,
) -> None:
    unowned = tmp_path / "unowned"
    unowned.mkdir()
    (unowned / "keep.txt").write_text("user data", encoding="utf-8")
    with pytest.raises(ValueError, match="unowned output"):
        prepare_output(unowned)
    assert (unowned / "keep.txt").read_text(encoding="utf-8") == "user data"

    with pytest.raises(ValueError, match="broad output"):
        prepare_output(REPO_ROOT)
