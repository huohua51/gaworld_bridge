# GLM-5.2 T4-v2 registered-transport pilot

## Scope

- Preregistration: `T4-REGISTERED-TRANSPORT-GLM52-v2`
- Registered base commit: `899bb909c57143eed87b3b0c34c9485a2b80657c`
- Registration SHA-256: `d472a71a6b161232e4b8ecfa65223c2c0ea955af67cf5e8ca869bc3de4b41499`
- Provider/model: `paratera_glm / GLM-5.2`
- Inference: `temperature=0`, `thinking=disabled`, `max_tokens=256`
- Design: 3 tasks × 2 variants × 3 tracks = 18 cells, seed 0
- Ranking eligible: `false`

The run used the frozen prompt, scorer, task files, execution order and 60-call
budget. No failed or invalid cell was replaced.

## Registered outcomes

| Track | Control FullPass | Intervention FullPass |
| --- | ---: | ---: |
| `full` | 100% | 100% |
| `remove_bridge` | 100% | 0% |
| `drop_bridge` | 100% | 0% |

- Measurement-valid cells: 18/18
- Structured model responses: 60/60
- Model contract rate: 100%
- Source `forward=true`: 18/18 cells
- Full-track target acceptance: 6/6 cells
- FullPass: 12/18 cells; the six intervention failures in bridge tracks are
  the registered negative-control outcome
- Logical model calls: 60/60
- Transport retry events recorded in model traces: 0
- Critical criteria without evidence: 0
- First errors: `none=12`, `bridge_message_not_delivered=6`

## Recorded metadata erratum

The frozen scorer writes `extra.phase=model_seed0_offline_calibration` inside
each cell even when the client is live. The top-level manifest, run context,
provider/model fields and raw model traces correctly identify this run as live.
The hard-coded cell label is not a gate or scored criterion and does not change
any outcome above. To preserve preregistration integrity, neither the frozen
scorer nor the recorded cells were changed after execution; a later protocol
version should derive this label from run context.

## Interpretation boundary

Under T4-v2's explicit registered-transport protocol, GLM-5.2 followed the
complete available route for both normal-status and action-required messages,
accepted full-track messages at the target, and preserved both bridge causal
contrasts. The ambiguous control forwarding seen in T4-v1 did not recur.

T4-v2 changed both the protocol wording and the task surfaces, so this is not an
isolated causal estimate of prompt wording alone. It is a seed-0 development
pilot, not a cross-model result, repeat-stability claim or leaderboard score.

The prospective registration retains its original `not_run` state as frozen
pre-execution evidence. This report and `RUN_MANIFEST.yaml` record completion.
