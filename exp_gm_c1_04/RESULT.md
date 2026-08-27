# EXP-GM-C1-04 registered result

- Model: GLM-5.2 through `paratera_glm`
- Cells/calls: 6/36
- Coverage: 1.0
- Strict JSON responses: 36/36
- FullPass: 3/6
- Intervention NACK path: 3/3
- Intervention retry recovery: 1/3
- Control NACK path: 1/3
- Registered gate: `control_spurious_nack`

First errors were `none` in three cells, `retry_assignment_incorrect` in two
intervention cells, and `initial_assignment_incorrect` in one control cell.
The two failed retries changed Agent B but retained Agent A's superseded
phase-1 slot instead of applying the registered protected assignment. This is
a semantic recovery failure, not a transport, provider, parse, or model-output
identifier failure.

The frozen C1-04 inputs and result remain unchanged. Any clarification and
rerun must use a new experiment number and fresh task surfaces.
