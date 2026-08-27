# T5-v3 sealed fresh-surface and cross-model protocol

This holdout keeps the frozen `gaworld-benchmark-t5-model-v3` Prompt and scorer
while replacing every policy topic, agent identity, group, action and state
surface. The three tasks are not used in any live connectivity or development
calibration before joint registration.

## Matrix

- models: GLM-5.2 and gpt-5.4
- tasks: elevator inspection, food recall and harbor ballast inspection
- states: `absence`, `binding`, `nonbinding`
- residents: four per cell, exactly two scope matches when a notice exists
- seed: 0
- cells: nine per model, eighteen total
- calls: 36 per model, 72 total

The execution order is GLM-5.2 first and gpt-5.4 second. Both models receive
byte-identical prompts for the same task, state and resident. Results from the
first model cannot change the second-model tasks, Prompt, scorer or oracle.

## Claim boundary

This is a development-grade sealed functional holdout and cross-model
replication. It is not a human-validity study or ranking-eligible release.
