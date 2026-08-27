# EXP-GM-C1-05

Status: completed, registered live gate failed.

This follow-up preserves the C1-04 failure and tests whether an explicit
authoritative-current-spec transition resolves the remaining semantic retry
error on three new task surfaces.

Offline calibration and the registered live run use `exp_gm_c1_05.run_matrix`;
live execution is limited to the one 36-call seed-0 matrix in
`registration.yaml`.

The frozen GLM-5.2 run is stored in `output/exp_gm_c1_05_20260827`.
Intervention priority NACK and retry recovery both reached 3/3, improving the
C1-04 retry result from 1/3. Strict FullPass was nevertheless 4/6: one control
retry created a duplicate claim and one intervention phase-1 proposal chose
the wrong fallback slot before later recovering correctly. The registered
gate is `platform_binding_failed`, so the two action items remain formally
open and no C1-06 is created merely to chase run-to-run variation.
