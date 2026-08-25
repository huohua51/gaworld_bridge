# CAL-GM-C1-COMP-01

- 时间：2026-08-25T06:01:02.977166+00:00
- phase：seed0
- ranking_eligible：false
- 不用 C1-01 冻结题。不开 L1。不改 C1-01。
- 冻结：a6ff231b8f49b0280f3f4be63556b4bc6d3aa07c

| 组件 | FullPass | 含义 |
| --- | ---: | --- |
| A 初始冲突检测 | 1.0 | 调整前的初始方案是否冲突 |
| B 最终方案核验 | 0.5 | 最终分配是否无重复占用 |
| C 冲突后重新分配 | 0.5 | 只交差，不交冲突布尔 |
| Coverage | 1.0 | |

- 解释：检测A=1.0 核验B=0.5 分配C=0.5。按组件分别解释，不合并成分。
- first_error：{'none': 4, 'final_conflict_free_incorrect': 1, 'allocation_incorrect': 1}

**结论：** 检测A=1.0 核验B=0.5 分配C=0.5。按组件分别解释，不合并成分。 不改 C1-01，不开 L1。

| instance | component | variant | valid | FullPass | first_error |
|---|---|---|---|---|---|
| c1comp_initial_conflict_001_control_r0 | A | control | True | 1 | none |
| c1comp_initial_conflict_001_intervention_r0 | A | intervention | True | 1 | none |
| c1comp_final_free_001_control_r0 | B | control | True | 0 | final_conflict_free_incorrect |
| c1comp_final_free_001_intervention_r0 | B | intervention | True | 1 | none |
| c1comp_reallocate_001_control_r0 | C | control | True | 1 | none |
| c1comp_reallocate_001_intervention_r0 | C | intervention | True | 0 | allocation_incorrect |
