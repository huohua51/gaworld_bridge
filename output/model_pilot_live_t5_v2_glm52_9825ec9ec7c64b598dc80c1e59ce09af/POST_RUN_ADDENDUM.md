# T5-v2 post-run protocol addendum

This addendum was created after the frozen T5-v3 eligibility-scope repair. It
does not change T5-v2 prompts, raw traces, cell scores or the original report.

The v2 binding prompts for non-target residents contained two fields with the
same name but different values:

- `registered_policy_state.required_action=keep_current`
- `registered_policy_state.notice.required_action=<global policy action>`

GLM-5.2 selected the nested global policy action in all six such seed-0 calls.
The original scorer correctly recorded the resulting actions and spillover, but
the evidence should be interpreted as a protocol field-collision failure rather
than a clean test of resident eligibility compliance.

T5-v3 preserves all v2 evidence, renames the global field to `policy_action`,
removes every `required_action` key and makes `resident_directive.action` the
sole action authority. Its prospective repeat 1/2 result is recorded in
`../model_pilot_live_t5_v3_repeats_glm52_e052783444814bafa16c26c21ebad5c6/REPORT.md`.
