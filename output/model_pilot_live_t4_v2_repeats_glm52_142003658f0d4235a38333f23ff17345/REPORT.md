# GLM-5.2 T4-v2 full-track repeats 1/2

## Scope

- Preregistration: `T4-REGISTERED-TRANSPORT-GLM52-REPEATS-v1`
- Registration SHA-256: `0374bf30313dec60ab794570c4d870ac7b88b77a252c4d8b834a62143cd9391f`
- Frozen seed-0 reference: `model_pilot_live_t4_v2_glm52_cbf1c8069f254797ab6e5a795c898399`
- Provider/model: `paratera_glm / GLM-5.2`
- Inference: `temperature=0`, `thinking=disabled`, `max_tokens=256`
- New design: 3 tasks × 2 variants × repeats 1/2 × full track = 12 cells
- Combined analysis: seed 0/1/2 = 18 cells
- Ranking eligible: `false`

The registration, runner and frozen seed-0 evidence were committed and pushed
before the new calls. No invalid or failed cell was replaced.

## Results

All six task-variant pairs produced the same registered pattern:

| Metric across seed 0/1/2 | Result |
| --- | ---: |
| Source prompt hash stable within each pair | 6/6 |
| Source `forward=true,true,true` | 6/6 |
| Complete-path rate | 100% |
| Target-acceptance rate | 100% |
| Model-contract rate | 100% |
| FullPass rate | 100% |

New-run audit:

- Measurement-valid cells: 12/12
- FullPass cells: 12/12
- Structured model responses: 48/48
- Logical model calls: 48/48
- First errors: `none=12`
- Transport retry events recorded in model traces: 0
- Critical criteria without evidence: 0
- Credential-like strings found: 0

## Interpretation boundary

The seed-0 success remained stable at repeats 1 and 2 for every registered
T4-v2 full-track task and variant. Within this fixed GLM-5.2 protocol, the v1
control-forwarding instability did not recur across three runs.

This is repeat evidence for one model and one explicit protocol. It does not
establish cross-model robustness, isolate prompt wording from the new task
surfaces, or qualify the run for ranking.

The previously recorded scorer metadata erratum remains: cell-level
`extra.phase` is hard-coded as offline even for live calls. The manifest and raw
traces correctly identify the live provider/model. The label is not scored, and
the frozen scorer and cell evidence were not rewritten.
