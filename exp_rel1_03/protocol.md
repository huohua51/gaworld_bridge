# EXP-GM-REL1-03 protocol

REL1-v3 is a new-number, fresh-surface regression. It addresses two observed
measurement failures in v2 without changing v2: the Observer must copy both
registered signals exactly, and TrustUpdater receives separate formation and
update prompts so the latest-binding rule cannot contaminate formation.

Formation explicitly reports per-source correct counts and every supporting
row ID before selecting the unique higher-count source. Update sees the full
ordered history but is instructed to use only the final row because
`latest_is_binding=true`, citing that row alone. The Dispatcher returns only a
registered business value. The platform supplies the registered action name,
the delivered and adopted message ID, current trust version, and phase.

The formal matrix is three new tasks by two variants, one full workflow track,
seed 0: 6 cells and 30 calls. The frozen EXP-GM-REL1 and EXP-GM-REL1-02
results are not rescored.
