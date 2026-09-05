# CROSS-PLATFORM-NATIVE-BOUNDARY-PROBES-v1 protocol

## Question and scope

This offline experiment asks a narrow question: what protection and traceability
does each selected native interface provide when it is called directly? It does
not rank GAWorld, YuLan-OneSim, or AgentSociety as complete systems, and it does
not claim that a production gateway could not add authentication or authorization.

The fixed native surfaces are:

- GAWorld: `gaworld.work.review.ReviewChannel`;
- YuLan-OneSim: `onesim.events.Event` and `EventBus` in local mode;
- AgentSociety 2: `agentsociety2.contrib.env.SimpleSocialSpace`.

The benchmark adapter may declare the real logical actor so that an impersonation
attempt is reproducible, but it must not add an access-control decision on behalf
of the platform. Passive recipients may only record whether a native dispatch was
delivered.

## Registered probes

1. **P1 identity impersonation.** The logical Executor invokes a native operation
   while supplying the Reviewer's identifier. Pass only if the selected native
   boundary rejects the operation. A method that accepts only a caller-supplied ID
   and delivers the operation fails this probe.
2. **P2 private data read.** Put a unique marker in Reviewer-owned private storage,
   then let the logical Executor try to read it. Pass only if the native interface
   denies the request without returning the marker. If the selected native surface
   exposes no owner-bound private storage/read primitive, record `not_applicable`;
   do not implement a benchmark-owned mailbox and call its behavior native.
3. **P3 unauthorized final write.** Let the Reviewer attempt to submit the
   Executor-owned final result. Pass only if the selected native surface rejects
   it and no final artifact/delivery is created. A passive sink records delivery
   but makes no authorization decision.
4. **P4 message traceability.** Send one legitimate review message/event. Pass only
   if a native identifier can be linked across the sender-side object/response,
   receiver-side object/response, and native audit/flow surface available in this
   interface. An internal identifier removed from the public boundary does not pass.

## Outcome rules

Each platform/probe cell is `pass`, `fail`, or `not_applicable`. The last value
means the native capability is absent from the fixed surface; it is neither a pass
nor a fail. Because the capability denominators differ, the experiment publishes
no composite score and no overall platform ranking. Per-platform counts are only
descriptive.

All requests are local and deterministic. Model calls are fixed at zero. The
AgentSociety adapter overwrites any inherited LLM key with a sentinel and pins its
base URL to `127.0.0.1:9` before importing the package.

## Interpretation boundary

A failed cell demonstrates that the selected direct interface did not enforce the
registered property. It does not prove exploitation through every deployment.
A passed cell applies only to the tested operation and version. `not_applicable`
documents a missing primitive, not security. Framework maintainers can use these
results to decide whether identity binding, owner-aware reads, role-aware final
writes, or public correlation IDs should be added at this layer or guaranteed by
an explicitly documented outer layer.

