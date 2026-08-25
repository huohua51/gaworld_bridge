"""04b hidden oracles must separate v1 from v2; coincidence is detectable."""

from __future__ import annotations

from pathlib import Path

from exp_gm_04.scorer import score_hidden_tests
from exp_gm_04b.tasks import TASKS
from exp_gm_04b.versioning import first_error, parse_artifact_spec_version


def _write(tmp: Path, source: str) -> str:
    path = tmp / "main.py"
    path.write_text(source, encoding="utf-8")
    return str(path)


def test_wage_oracles_are_mutually_exclusive(tmp_path: Path):
    v1 = _write(tmp_path, 'SPEC_VERSION = "v1"\nTHRESHOLD = 60000\ndef decide(take_home):\n    return "accept" if take_home >= THRESHOLD else "reject"\n')
    wage = TASKS[0]
    assert score_hidden_tests(v1, wage["v1"]["oracle"])["passed"] is True
    assert score_hidden_tests(v1, wage["v2"]["oracle"])["passed"] is False
    v2_dir = tmp_path / "v2"
    v2_dir.mkdir()
    v2 = _write(v2_dir, 'SPEC_VERSION = "v2"\nTHRESHOLD = 70000\ndef decide(take_home):\n    return "accept" if take_home >= THRESHOLD else "reject"\n')
    assert score_hidden_tests(v2, wage["v2"]["oracle"])["passed"] is True
    assert score_hidden_tests(v2, wage["v1"]["oracle"])["passed"] is False


def test_parse_spec_version(tmp_path: Path):
    path = _write(tmp_path, 'SPEC_VERSION = "v2"\n\ndef decide(take_home):\n    return "accept"\n')
    assert parse_artifact_spec_version(path) == "v2"


def test_first_error_revision_not_delivered():
    assert (
        first_error(
            track="pipeline",
            variant="intervention",
            expected_version="v2",
            revision_emitted=True,
            revision_ok=False,
            delivered_version=None,
            input_spec_version="v1",
            artifact_spec_version="v1",
            artifact_exists=True,
            adapter_ok=True,
            target_correct=False,
            other_version_also_passes=False,
            absorbed=True,
            oracle_first_error="oracle_tests_failed",
        )
        == "revision_not_delivered"
    )


def test_coincident_pass_is_not_clean():
    assert (
        first_error(
            track="pipeline",
            variant="intervention",
            expected_version="v2",
            revision_emitted=True,
            revision_ok=True,
            delivered_version="v2",
            input_spec_version="v2",
            artifact_spec_version="v1",
            artifact_exists=True,
            adapter_ok=True,
            target_correct=True,
            other_version_also_passes=True,
            absorbed=True,
            oracle_first_error="none",
        )
        == "artifact_not_reworked"
    )
