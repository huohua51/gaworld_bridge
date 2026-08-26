# GLM-5.2 minimal T5 causal-chain pilot

## Scope

- Preregistration: `T5-MINIMAL-CAUSAL-GLM52-v1`
- Registration SHA-256: `9a6e7eaa53d60fb00e39514eb08a2647f0173a5706b3d885179259ccb703455a`
- Provider/model: `paratera_glm / GLM-5.2`
- Inference: `temperature=0`, `thinking=disabled`, `max_tokens=256`
- Task: `t5_low_emission_zone`
- Conditions: `no_policy`, `real_policy`, `placebo_policy`
- Population: four residents, including two registered target residents
- Logical calls: 12/12
- Ranking eligible: `false`

The registration and runner were committed and pushed before execution. No
invalid or failed cell was replaced, and the prompt/scorer were not changed
after observing results.

## Registered outcomes

| Condition | FullPass | Behavior change | Changed residents |
| --- | ---: | ---: | --- |
| `no_policy` | 0 | 0% | none; two attempted target actions were denied |
| `real_policy` | 1 | 50% | `lez-car-1`, `lez-car-2` |
| `placebo_policy` | 0 | 50% | `lez-car-1`, `lez-car-2` |

Observed causal contrasts:

- real minus no policy: `0.5`
- real minus placebo: `0.0`
- placebo minus no policy: `0.5`

The preregistered oracle was `0.5 / 0.5 / 0.0`, respectively. Therefore the
registered overall outcome failed even though the real-policy cell passed.

## Failure localization

All 12 model responses satisfied the JSON contract and all three cells were
measurement-valid. The failure is behavioral, not an API or parsing failure.

- `no_policy`: all four residents returned `perceived=true` despite
  `active_policy=null`. The two high-emission residents selected
  `use_park_and_ride`; the policy channel rejected both submissions with
  `action_evidence_not_perceived`, so no state changed and the action set was
  incomplete.
- `real_policy`: exactly the two target residents adopted
  `use_park_and_ride`; non-target residents kept their current behavior.
- `placebo_policy`: the same two target residents treated a
  `matched_nonbinding_notice` as binding and changed behavior, eliminating the
  registered real-versus-placebo contrast.

Audit totals:

- Measurement-valid cells: 3/3
- Structured model responses: 12/12
- FullPass cells: 1/3
- First errors: `none=1`, `resident_policy_response_incorrect=2`
- Transport retry events recorded in model traces: 0
- Critical criteria without evidence: 0
- Credential-like strings found: 0

## Interpretation boundary

In this one-task seed-0 pilot, GLM-5.2 correctly followed a binding policy but
did not ground its decision on policy absence and did not distinguish the
matched nonbinding notice from the real rule. T5 policy-causal discrimination
is therefore not established.

This does not estimate any real-world policy effect or human behavior. It is a
development diagnosis for the model protocol. A future T5-v2 should explicitly
define absence, binding and nonbinding semantics under a new registration;
T5-v1 evidence must remain unchanged.
