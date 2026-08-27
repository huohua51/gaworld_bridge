# EXP-GM-C1-04

Status: preregistered, not run. No live result exists yet.

This new-number regression moves `plan_id` and `spec_version` issuance fully to
the platform. A protection revision invalidates the previous plan, rejected
proposals are never stamped, and only claims confirmed against the delivered
current-spec plan enter world state. Three new resource surfaces prevent
post-hoc reuse of C1-03 items.

Run offline calibration:

```powershell
F:\proj\.venv_gaworld_eval\Scripts\python.exe -m exp_gm_c1_04.run_matrix --fixture-oracle --out output\exp_gm_c1_04_fixture_20260827
```

Run the registered live seed-0 matrix:

```powershell
F:\proj\.venv_gaworld_eval\Scripts\python.exe -m exp_gm_c1_04.run_matrix --provider paratera_glm --allow-live-model --out output\exp_gm_c1_04_20260827
```
