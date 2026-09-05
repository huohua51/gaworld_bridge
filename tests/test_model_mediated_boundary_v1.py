from __future__ import annotations

from cross_platform.model_mediated_boundary_v1.run import (
    fixture_client,
    run_calibration,
    run_formal,
)


def test_fixture_calibration_and_formal_matrix(tmp_path):
    calibration = run_calibration(tmp_path / "calibration", fixture_client())
    assert calibration["gate"] == "pass"
    assert calibration["strict_valid"] == 3
    assert calibration["semantic_expected"] == 3
    assert calibration["budget"]["calls_used"] == 3
    assert calibration["budget"]["transport_attempts_observed"] == 0

    manifest = run_formal(tmp_path / "formal", fixture_client(), fixture=True)
    assert manifest["phase"] == "fixture"
    assert manifest["new_model_calls"] == 0
    assert manifest["ranking_eligible"] is False
    assert manifest["platform_summary"] == {
        "GAWorld": {
            "cells": 4,
            "valid_model_responses": 4,
            "model_policy_pass": 4,
            "defense_in_depth_safe": 4,
            "defense_in_depth_not_applicable": 0,
        },
        "YuLan-OneSim": {
            "cells": 4,
            "valid_model_responses": 4,
            "model_policy_pass": 4,
            "defense_in_depth_safe": 4,
            "defense_in_depth_not_applicable": 0,
        },
        "AgentSociety2": {
            "cells": 4,
            "valid_model_responses": 4,
            "model_policy_pass": 4,
            "defense_in_depth_safe": 3,
            "defense_in_depth_not_applicable": 0,
        },
    }
