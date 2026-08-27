# EXP-GM-C1-04

Status: completed, registered live gate failed.

The one allowed GLM-5.2 seed-0 run is preserved in
`output/exp_gm_c1_04_20260827`. Coverage was 1.0 and every model response met
the JSON contract, but FullPass was 3/6. All three intervention cells entered
the NACK path; only one recovered. In the other two, the retry moved Agent B
but incorrectly retained Agent A's superseded phase-1 assignment. One control
also chose the wrong phase-1 slot. The registered gate is therefore
`control_spurious_nack`; neither C1 action item closes from this run.

This new-number regression moves `plan_id` and `spec_version` issuance fully to
the platform. A protection revision invalidates the previous plan, rejected
proposals are never stamped, and only claims confirmed against the delivered
current-spec plan enter world state. Three new resource surfaces prevent
post-hoc reuse of C1-03 items.

Run offline calibration:

```powershell
F:\proj\.venv_gaworld_eval\Scripts\python.exe -m exp_gm_c1_04.run_matrix --fixture-oracle --out output\exp_gm_c1_04_fixture_20260827
```

The registered live command below is retained for reproducibility and must not
be rerun as new evidence:

```powershell
F:\proj\.venv_gaworld_eval\Scripts\python.exe -m exp_gm_c1_04.run_matrix --provider paratera_glm --allow-live-model --out output\exp_gm_c1_04_20260827
```
