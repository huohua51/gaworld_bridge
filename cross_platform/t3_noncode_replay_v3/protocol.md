# AgentSociety 2 shared-review extension protocol

## Question

When the six reviewer objects and their evidence IDs from the frozen T3 v2 run
are replayed without any new model sampling, does AgentSociety 2's native
`SimpleSocialSpace` mailbox preserve the payload and deterministic transition?

## Unit and denominator

The unit is one existing task × evidence variant reviewer sample. There are six
fixed units. Five contain valid reviewer JSON and are evaluable for platform
transport. The invalid sixth sample remains in the six-unit functional
denominator and is not attributed to AgentSociety.

## Outcomes

Payload transport and deterministic execution are scored separately from native
identity enforcement. The transport outcome requires exact review equality,
canonical hash equality, native sender/receiver observations, final delivery and
the frozen executor transition. A separate adversarial capability probe asks
whether the tested mailbox read boundary binds a caller identity rather than
trusting a supplied `agent_id`.

The probe result is reported, not repaired in the adapter. An adapter-added ACL
would test benchmark code rather than AgentSociety's native surface.

AgentSociety 2 validates an API key and base URL while importing its top-level
package, even for this local-only surface. The adapter therefore overwrites both
values inside its own process with a benchmark sentinel and the loopback discard
endpoint `http://127.0.0.1:9`. No user credential is read and no model call is
made.

## Limits

This is a one-surface mechanism comparison. It is not a platform-wide ranking,
does not test AgentSociety's city/economy/mobility subsystems, and does not
establish H1–H7 human validity. The earlier YuLan v2 path had no equivalent
adversarial identity probe, so its ACL status remains untested in this extension.
