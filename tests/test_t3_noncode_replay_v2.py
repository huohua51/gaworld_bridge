from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path

import pytest

from cross_platform.t3_noncode_replay_v2.protocol import (
    VARIANTS,
    load_tasks,
    oracle_shared_review,
    payload_sha256,
    reviewer_prompt,
)
from cross_platform.t3_noncode_replay_v2.scorer import score_replay

BRIDGE_ROOT = Path(__file__).resolve().parent.parent
WORKSPACE_ROOT = BRIDGE_ROOT.parent
YULAN_PYTHON = WORKSPACE_ROOT / ".venv_yulan_onesim_eval" / "Scripts" / "python.exe"


def test_review_prompt_and_shared_hash_are_deterministic() -> None:
    task = load_tasks()[0]
    prompt_a = reviewer_prompt(task, VARIANTS[0])
    prompt_b = reviewer_prompt(task, VARIANTS[0])
    review = oracle_shared_review(task, VARIANTS[0])

    assert prompt_a == prompt_b
    assert json.loads(prompt_a)["sampling_design"] == (
        "one_reviewer_sample_shared_across_platforms"
    )
    assert review["review_id"] == f"{task['id']}_r1"
    assert payload_sha256(review) == payload_sha256(
        dict(reversed(list(review.items())))
    )


def test_invalid_reviewer_sample_is_not_attributed_to_platform(tmp_path) -> None:
    trace = tmp_path / "trace.jsonl"
    trace.write_text('{"event":"review_unavailable"}\n', encoding="utf-8")
    task = load_tasks()[0]
    sample = {
        "response_ok": False,
        "shared_review": None,
        "evidence_id": "model-call:failed",
        "model_trace_path": "model.jsonl",
    }
    loop = {
        "run_id": "invalid-sample",
        "platform": "GAWorld",
        "trace_path": str(trace),
        "ingress_review": None,
        "delivered_review": None,
        "ingress_review_sha256": payload_sha256(None),
        "delivered_review_sha256": payload_sha256(None),
        "executor_output": {},
        "proposal_delivered": True,
        "review_delivery_verified": False,
        "review_adoption_verified": False,
        "final_submission_verified": True,
        "private_evidence_readers": ["reviewer"],
        "state_writers": ["executor"],
        "events": ["review_unavailable"],
        "denials": [],
    }

    cell = score_replay(
        task=task,
        variant=VARIANTS[0],
        sample=sample,
        loop=loop,
    )

    assert cell["reviewer_sample_valid"] is False
    assert cell["transport_evaluable"] is False
    assert cell["platform_transport_pass"] is None
    assert cell["joint_full_pass"] == 0
    assert cell["first_error"] == "reviewer_sample_invalid"


@pytest.mark.skipif(not YULAN_PYTHON.is_file(), reason="YuLan evaluation venv absent")
def test_registered_fixture_replays_identical_payloads(tmp_path) -> None:
    out = tmp_path / "fixture"
    env = os.environ.copy()
    env["PYTHONPATH"] = os.pathsep.join(
        [
            str(BRIDGE_ROOT),
            str(WORKSPACE_ROOT / "GAWorld"),
            str(WORKSPACE_ROOT / "YuLan-OneSim-official"),
        ]
    )
    completed = subprocess.run(
        [
            str(YULAN_PYTHON),
            "-m",
            "cross_platform.t3_noncode_replay_v2.run",
            "--fixture-oracle",
            "--out",
            str(out),
        ],
        cwd=BRIDGE_ROOT,
        env=env,
        check=False,
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert completed.returncode == 0, completed.stderr
    manifest = (out / "RUN_MANIFEST.yaml").read_text(encoding="utf-8")

    assert "gate: offline_fixture_calibration_pass" in manifest
    assert "evaluable_pairs: 6" in manifest
    assert "difference_pairs: 0" in manifest
    cells = json.loads((out / "cell_table.json").read_text(encoding="utf-8"))
    assert len(cells) == 12
    assert all(cell["joint_full_pass"] == 1 for cell in cells)
    assert all(cell["criteria"]["shared_payload_hash_exact"] for cell in cells)


@pytest.mark.skipif(not YULAN_PYTHON.is_file(), reason="YuLan evaluation venv absent")
def test_live_calibration_gate_counts_physical_attempts(tmp_path) -> None:
    out = tmp_path / "calibration"
    env = os.environ.copy()
    env["PYTHONPATH"] = os.pathsep.join(
        [
            str(BRIDGE_ROOT),
            str(WORKSPACE_ROOT / "GAWorld"),
            str(WORKSPACE_ROOT / "YuLan-OneSim-official"),
        ]
    )
    program = r"""
import sys
from pathlib import Path
from benchmark_core.model_runner_v2 import ModelClientInfo
from cross_platform.t3_noncode_review.fixture import oracle_fixture_client
from cross_platform.t3_noncode_replay_v2.run import run_live_calibration

class AuditedFixture:
    info = ModelClientInfo("paratera_glm", "GLM-5.2", True)

    def __init__(self):
        self.delegate = oracle_fixture_client()
        self.metadata = {}

    def generate(self, prompt, *, task, agent_id):
        value = self.delegate.generate(prompt, task=task, agent_id=agent_id)
        self.metadata = {
            "transport_attempts": [{
                "attempt": 1,
                "max_attempts": 1,
                "success": True,
                "retryable": False,
                "will_retry": False,
                "error_type": "",
            }]
        }
        return value

    def consume_last_call_metadata(self):
        value = self.metadata
        self.metadata = {}
        return value

report = run_live_calibration(Path(sys.argv[1]), AuditedFixture())
raise SystemExit(0 if report["gate"] == "live_calibration_pass" else 1)
"""
    completed = subprocess.run(
        [str(YULAN_PYTHON), "-c", program, str(out)],
        cwd=BRIDGE_ROOT,
        env=env,
        check=False,
        capture_output=True,
        text=True,
        timeout=30,
    )

    assert completed.returncode == 0, completed.stderr
    manifest = (out / "RUN_MANIFEST.yaml").read_text(encoding="utf-8")
    assert "gate: live_calibration_pass" in manifest
    assert "transport_attempts_observed: 2" in manifest
    assert "transport_retries_observed: 0" in manifest
