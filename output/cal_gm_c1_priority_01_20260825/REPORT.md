# CAL-GM-C1-PRIORITY-01

- 时间：2026-08-25T07:24:49.405270+00:00
- phase：all
- 不覆盖 C1-02。不开 L1。不建留出。
- 冻结：a6ff231b8f49b0280f3f4be63556b4bc6d3aa07c

| PriorityPreserved | 1.0 |
| EarliestIdleLow | 0.9444 |
| ActualFinalConflictFree | 0.9444 |
| JointConstraintSatisfaction | 1.0 |
| PolicyConstrainedPlan | 0.9444 |
| FullPass control | 1.0 |
| FullPass intervention | 0.8889 |
| Coverage | 1.0 |

- 解释：优先级组件门未过。split={'control': 1.0, 'intervention': 0.8889}。不开 L1，不覆盖 C1-02，不建留出。
- first_error：{'none': 17, 'final_state_conflict': 1}

**结论：** 优先级组件门未过。split={'control': 1.0, 'intervention': 0.8889}。不开 L1，不覆盖 C1-02，不建留出。

| instance | variant | valid | FullPass | first_error |
|---|---|---|---|---|
| c1prio_autoclave_001_control_r0 | control | True | 1 | none |
| c1prio_autoclave_001_intervention_r0 | intervention | True | 1 | none |
| c1prio_darkroom_001_control_r0 | control | True | 1 | none |
| c1prio_darkroom_001_intervention_r0 | intervention | True | 1 | none |
| c1prio_mass_spec_001_control_r0 | control | True | 1 | none |
| c1prio_mass_spec_001_intervention_r0 | intervention | True | 1 | none |
| c1prio_autoclave_001_control_r1 | control | True | 1 | none |
| c1prio_autoclave_001_intervention_r1 | intervention | True | 1 | none |
| c1prio_darkroom_001_control_r1 | control | True | 1 | none |
| c1prio_darkroom_001_intervention_r1 | intervention | True | 1 | none |
| c1prio_mass_spec_001_control_r1 | control | True | 1 | none |
| c1prio_mass_spec_001_intervention_r1 | intervention | True | 1 | none |
| c1prio_autoclave_001_control_r2 | control | True | 1 | none |
| c1prio_autoclave_001_intervention_r2 | intervention | True | 1 | none |
| c1prio_darkroom_001_control_r2 | control | True | 1 | none |
| c1prio_darkroom_001_intervention_r2 | intervention | True | 1 | none |
| c1prio_mass_spec_001_control_r2 | control | True | 1 | none |
| c1prio_mass_spec_001_intervention_r2 | intervention | True | 0 | final_state_conflict |
