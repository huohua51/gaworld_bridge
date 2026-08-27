# EXP-GM-C1-04 protocol

C1-04 is a fresh-surface repair regression. It preserves C1-03 and tests two
separate failure classes found there: semantic recovery after a registered
protection NACK, and ownership of plan/spec identifiers.

Each formal cell makes six calls in fixed order: Agent A report, Agent B
report, Coordinator phase-1 proposal, Coordinator post-revision proposal,
Agent A confirmation, Agent B confirmation. The model may output assignments
and confirmations only. The platform validates proposals, advances the spec
version when the protection record is registered, stamps accepted plans, and
binds both confirmations to the delivered plan.

The intervention changes phase-1 priority so that the correct phase-1 plan
becomes invalid after the protection record arrives. The public NACK identifies
the violated rule but does not name the low-priority repair slot. The control
receives the same platform revision mechanism but its phase-1 assignments
already satisfy the protected state, so no violation is expected.

The preregistered seed-0 matrix has three unused task surfaces, two variants,
one full workflow track, and 36 total calls. Negative delivery behavior and
rejected-plan stamping are covered by deterministic platform tests rather than
extra paid model cells. A pass can close the two C1-03 repair action items but
does not rewrite the historical C1-02 or C1-03 scores and is not a broad model
generalization claim.
