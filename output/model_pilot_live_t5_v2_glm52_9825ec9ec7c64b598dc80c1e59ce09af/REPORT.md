# T5-v2 explicit policy semantics: GLM-5.2 seed-0 pilot

## Registration and execution

- preregistration: `T5-EXPLICIT-SEMANTICS-GLM52-v2`
- preregistration commit pushed before execution: `fe5cad4699b4d4d35b85b2c4f5b626f8e61134e6`
- registration SHA-256: `87dc79193f100f6fa1f6b9d672c22ff2c6f3c368ad306b12a04fd04ebdea2113`
- provider/model: `paratera_glm / GLM-5.2`
- settings: `temperature=0`, `thinking=disabled`, `max_tokens=256`
- design: 3 fresh tasks x 3 policy states x 4 residents, seed 0, full track
- actual budget: 36/36 registered model calls
- ranking eligibility: `false`

T5-v1 code and its failed live evidence were not modified. T5-v2 used an
independent task set, prompt protocol and scorer, with explicit `absence`,
`binding` and `nonbinding` semantics.

## Registered outcomes

| Policy state | FullPass | Behavior change | Semantic pass | Response pass | Result |
| --- | ---: | ---: | ---: | ---: | --- |
| absence | 1.0 | 0.0 | 1.0 | 1.0 | pass |
| binding | 0.0 | 1.0 | 1.0 | 0.0 | fail: all residents changed |
| nonbinding | 1.0 | 0.0 | 1.0 | 1.0 | pass |

The registered binding oracle required exactly two eligible residents per task
to change, for a behavior-change rate of 0.5. The observed rate was 1.0 in all
three binding cells. Consequently, the observed contrasts were:

- binding minus absence: `1.0` (registered `0.5`)
- binding minus nonbinding: `1.0` (registered `0.5`)
- nonbinding minus absence: `0.0` (registered `0.0`)

Six of nine cells passed. All three failures had first error
`resident_policy_response_incorrect` and also failed the untargeted-spillover
criterion.

## Failure localization

All 36 responses correctly reported notice presence and binding status. In the
six binding calls for ineligible residents, the resident-specific registered
state explicitly contained `eligible=false` and `required_action=keep_current`.
GLM-5.2 returned the topic's policy action in all six cases. Eligible binding
residents, absence residents and nonbinding residents all received the correct
action.

This pilot therefore resolves the T5-v1 absence/nonbinding ambiguity under the
new explicit protocol, but exposes a narrower eligibility-scope failure that
is consistent across all three tasks: GLM-5.2 follows the global binding policy
topic instead of the resident-specific `required_action` for non-target
residents.

## Audit

- 9 model trace files and 9 cell results were present.
- 36 requests, 36 responses, 36 schema-valid JSON objects and 0 blocked calls.
- policy semantic fields were correct in 36/36 calls.
- returned action matched resident-specific `required_action` in 30/36 calls.
- all 6 mismatches were ineligible residents in binding cells.
- no replacement calls or post-registration prompt changes occurred.
- repository evidence scan found no API key or bearer-token material.

## Claim boundary

This is a preregistered three-task, seed-0 functional diagnostic. It does not
establish repeated-run stability, broad policy-domain generalization, human
validity, real-world policy effects or leaderboard performance.
