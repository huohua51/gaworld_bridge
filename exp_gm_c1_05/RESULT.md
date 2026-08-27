# EXP-GM-C1-05 registered result

- Model/calls: GLM-5.2, 36/36
- Coverage and strict JSON: 6/6 cells, 36/36 responses
- FullPass: 4/6
- Intervention priority NACK: 3/3
- Intervention retry recovery: 3/3
- Control priority NACK: 0/3
- Platform identifier ownership: 5/6
- Registered gate: `platform_binding_failed`

The semantic intervention targeted by C1-05 worked in all three fresh tasks.
The two strict failures were elsewhere: a control post-revision proposal put
both agents in `ca501`, and an intervention phase-1 proposal selected `lt602`
instead of Agent A's available preferred `lt603`; that intervention later
recovered to the correct current-spec final plan.

This supports “the authoritative-current-spec wording repaired the observed
NACK retry pattern in this batch,” but not “the entire C1 workflow passed.”
Under the preregistered stopping rule AP-C1-D-01 and AP-C1-F-01 remain open.
C1-02 through C1-04 remain unchanged.
