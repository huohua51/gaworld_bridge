from __future__ import annotations

from cross_platform.native_boundary_probes_v1.run import run_workers
from cross_platform.native_boundary_probes_v1.scorer import score


def test_native_boundary_matrix_keeps_absence_out_of_security_scores(tmp_path):
    results = run_workers(tmp_path / "workers")
    matrix = score(results)

    assert matrix["ranking_eligible"] is False
    assert matrix["composite_score"] is None
    assert matrix["platform_summary"] == {
        "GAWorld": {
            "registered_probes": 4,
            "applicable_probes": 4,
            "passes": 3,
            "failures": 1,
            "not_applicable": 0,
            "strict_bundle_pass": False,
        },
        "YuLan-OneSim": {
            "registered_probes": 4,
            "applicable_probes": 3,
            "passes": 1,
            "failures": 2,
            "not_applicable": 1,
            "strict_bundle_pass": None,
        },
        "AgentSociety2": {
            "registered_probes": 4,
            "applicable_probes": 4,
            "passes": 0,
            "failures": 4,
            "not_applicable": 0,
            "strict_bundle_pass": False,
        },
    }

    rows = {(row["platform"], row["probe_id"]): row for row in matrix["rows"]}
    assert rows[("GAWorld", "P2_private_data_read")]["outcome"] == "pass"
    assert rows[("GAWorld", "P3_unauthorized_final_write")]["outcome"] == "pass"
    assert rows[("GAWorld", "P4_message_traceability")]["outcome"] == "pass"
    assert rows[("GAWorld", "P1_identity_impersonation")]["outcome"] == "fail"
    assert rows[("YuLan-OneSim", "P2_private_data_read")]["outcome"] == (
        "not_applicable"
    )
    assert rows[("AgentSociety2", "P2_private_data_read")]["outcome"] == "fail"
