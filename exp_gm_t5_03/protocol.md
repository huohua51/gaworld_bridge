# T5-v3 resident eligibility-scope protocol

T5-v3 separates a global policy notice from a resident-specific executable
directive. It reuses the three frozen T5-v2 task surfaces solely to isolate the
protocol repair; it does not combine v2 seed 0 with v3 repeats.

## Registered semantics

- `absence`: no notice; `target_match=false`, `authorized=false`, and
  `action=keep_current`.
- `binding`: a notice exists. Scope-matched residents have `authorized=true`
  and take the global `policy_action`; all others have `authorized=false` and
  `action=keep_current`.
- `nonbinding`: a notice exists and target scope is observable, but every
  resident has `authorized=false` and `action=keep_current`.

The global notice uses `policy_action`. The only executable field is
`resident_directive.action`; no prompt field is named `required_action`.
Global binding status, policy topic, target-group match, resident state and
candidate-action membership cannot override a resident directive.

## Repeats

Repeat IDs 1 and 2 use byte-identical prompts for each task, policy state and
resident. They are two prospective v3 repetitions, not stability evidence
combined with the post-diagnostic v2 seed-0 run.
