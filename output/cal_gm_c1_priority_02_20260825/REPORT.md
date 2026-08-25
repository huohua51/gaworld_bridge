# CAL-GM-C1-PRIORITY-02

- 时间：2026-08-25T07:35:19.466237+00:00
- phase：all
- 不覆盖 C1-02 / PRIORITY-01。不开 L1。不建留出。
- 冻结：a6ff231b8f49b0280f3f4be63556b4bc6d3aa07c

| PriorityPreserved | 1.0 |
| EarliestIdleLow | 1.0 |
| ActualFinalConflictFree | 1.0 |
| JointConstraintSatisfaction | 1.0 |
| PolicyConstrainedPlan | 1.0 |
| FullPass control | 1.0 |
| FullPass intervention | 1.0 |
| Coverage | 1.0 |

- 解释：第一次提案路径与 Rule 重试路径通过。真模型 NACK 重试次数为 0（18 格 calls 均为 1），不能写成 LLM 重试缺陷已完整验证。不覆盖 C1-02 / PRIORITY-01。不开 L1，不建留出。
- llm_retry_path：not_exercised
- first_error：{'none': 18}

**结论：** 新协议的正常提案路径和 Rule 重试路径已经校准通过；真模型的重试路径尚未被触发，需在 C1-03 完整多智能体回归中验证。不能说真模型 NACK 重试已 18/18 通过，也不能关闭 AP-C1-D-01。C1-02 维持原分。不开 L1，不建留出。

| instance | variant | valid | FullPass | first_error |
|---|---|---|---|---|
| c1prio2_hplc_001_control_r0 | control | True | 1 | none |
| c1prio2_hplc_001_intervention_r0 | intervention | True | 1 | none |
| c1prio2_gown_001_control_r0 | control | True | 1 | none |
| c1prio2_gown_001_intervention_r0 | intervention | True | 1 | none |
| c1prio2_vivarium_001_control_r0 | control | True | 1 | none |
| c1prio2_vivarium_001_intervention_r0 | intervention | True | 1 | none |
| c1prio2_hplc_001_control_r1 | control | True | 1 | none |
| c1prio2_hplc_001_intervention_r1 | intervention | True | 1 | none |
| c1prio2_gown_001_control_r1 | control | True | 1 | none |
| c1prio2_gown_001_intervention_r1 | intervention | True | 1 | none |
| c1prio2_vivarium_001_control_r1 | control | True | 1 | none |
| c1prio2_vivarium_001_intervention_r1 | intervention | True | 1 | none |
| c1prio2_hplc_001_control_r2 | control | True | 1 | none |
| c1prio2_hplc_001_intervention_r2 | intervention | True | 1 | none |
| c1prio2_gown_001_control_r2 | control | True | 1 | none |
| c1prio2_gown_001_intervention_r2 | intervention | True | 1 | none |
| c1prio2_vivarium_001_control_r2 | control | True | 1 | none |
| c1prio2_vivarium_001_intervention_r2 | intervention | True | 1 | none |
