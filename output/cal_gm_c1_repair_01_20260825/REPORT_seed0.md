# CAL-GM-C1-REPAIR-01

- 时间：2026-08-25T06:17:06.830173+00:00
- phase：seed0
- c1_02_allowed：true
- ranking_eligible：false
- 不用 C1-01 / C1-COMP-01 原题。不开 L1。不改 C1-01。
- 冻结：a6ff231b8f49b0280f3f4be63556b4bc6d3aa07c

| 组件 | control | intervention | 合计 |
| --- | ---: | ---: | ---: |
| A 初始冲突检测 | 1.0 | 1.0 | 1.0 |
| B SelfAssessmentCorrect | 1.0 | 1.0 | 1.0 |
| C 重新分配 | 1.0 | 1.0 | 1.0 |
| C ActualFinalConflictFree |  |  | 1.0 |
| UnregisteredModification |  |  | 0.0 |
| Coverage |  |  | 1.0 |

- 解释：组件复测全部通过。c1_02_allowed=true。仍不开 L1，不改 C1-01。
- first_error：{'none': 6}

**结论：** 组件复测全部通过。c1_02_allowed=true。仍不开 L1，不改 C1-01。

| instance | component | variant | valid | FullPass | first_error |
|---|---|---|---|---|---|
| c1repair_initial_conflict_001_control_r0 | A | control | True | 1 | none |
| c1repair_initial_conflict_001_intervention_r0 | A | intervention | True | 1 | none |
| c1repair_final_free_001_control_r0 | B | control | True | 1 | none |
| c1repair_final_free_001_intervention_r0 | B | intervention | True | 1 | none |
| c1repair_reallocate_001_control_r0 | C | control | True | 1 | none |
| c1repair_reallocate_001_intervention_r0 | C | intervention | True | 1 | none |
