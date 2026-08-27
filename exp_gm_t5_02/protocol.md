# EXP-GM-T5-02 explicit policy-semantics protocol

T5-v2 is a new experiment. It does not replace, modify or rescore T5-v1.

Each resident receives exactly one registered `policy_state`:

- `absence`: no active notice exists. The resident must report
  `notice_seen=false`, `binding=false` and `action=keep_current`.
- `binding`: an active binding rule exists. The resident must report
  `notice_seen=true` and `binding=true`. An eligible resident uses the state's
  `required_action`; an ineligible resident keeps current.
- `nonbinding`: an active matched notice exists but has no mandatory behavioral
  effect. The resident must report `notice_seen=true`, `binding=false` and
  `action=keep_current`, regardless of eligibility.

Resident group, current state, policy topic and the list of allowed actions are
context, not authorization. Only the explicit registered policy state can
authorize a non-default action.

The `full` track activates the registered notice. `disconnect_policy` stops one
step before activation and is an R0 negative control. Rule and offline-fixture
calibration establish only the platform, prompt wiring and scorer controls;
they do not establish live-model capability or human policy validity.
