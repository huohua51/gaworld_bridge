# EXP-GM-T4-02 registered-transport protocol

T4-v2 measures compliance with an explicit registered transport rule. It is a
new experiment and does not replace or rescore T4-v1 evidence.

Every task has a four-node registered path and one registered bridge edge. A
valid `registered_status_update` must be transported independently of whether
the payload requests a target action:

1. The source forwards the injected message to `next_registered_node`.
2. An intermediate node that receives the message accepts it and forwards the
   same immutable message to `next_registered_node`.
3. The target accepts a received message. It submits the payload's registered
   `target_action`; a normal-status control therefore submits `keep_current`.
4. A target that receives no message must not infer its contents. It submits
   `keep_current` without message evidence.

`action_required` controls only the target action. It never changes whether a
valid registered message should be accepted or forwarded.

Tracks:

- `full`: the complete path is available. Both variants must reach and be
  accepted by the target; complete-path evidence is critical.
- `remove_bridge`: the bridge edge is removed before injection. The control
  still has the correct baseline action, while the intervention cannot cause
  its registered action.
- `drop_bridge`: the bridge edge remains registered, but the current delivery
  is explicitly dropped. The same positive/negative action contrast applies.

Rule and offline-fixture calibration validate the channel, scorer, prompt
wiring and positive/negative controls only. They do not establish live-model
capability or ranking eligibility.
