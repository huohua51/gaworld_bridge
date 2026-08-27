# T5-v3 expanded sealed three-model repeat protocol

This holdout retains the frozen `gaworld-benchmark-t5-model-v3` Prompt and
scorer while introducing four new policy topics, actor sets, groups, actions
and state surfaces. No candidate model receives these tasks before the joint
registration is committed and pushed.

## Matrix

- models: GLM-5.2, gpt-5.4 and qwen3.7-plus
- tasks: medicine cold-chain isolation, smoke sheltering, plant quarantine and bridge weight detour
- states: `absence`, `binding`, `nonbinding`
- residents: four per cell, exactly two target matches when a notice exists
- repeat IDs: seed 0 and seed 1
- cells: twenty-four per model, seventy-two total
- calls: 96 per model, 288 total

Seed 0 and seed 1 are registered independent repeats of byte-identical inputs;
the provider adapters do not expose a provider-side random-seed parameter.
The execution order is model, then seed, task, policy state and resident.
Earlier results cannot alter later tasks, prompts, scorer, denominator or oracle.

## Claim boundary

This is a development-grade sealed functional holdout with three-model and
within-model repeat evidence. It is not a human-validity study, broad model
generalization claim or ranking-eligible release.
