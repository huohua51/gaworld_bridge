# EXP-GM-05 Equal-budget multi-agent value

- 时间：2026-08-24T08:36:11.278551+00:00
- 阶段：repeat_0（18 格）。预注册门 **C_floor**，不补 repeat 1/2
- 模型：GLM-4-Flash，temperature=0，每格固定 3 次调用
- ranking_eligible：false
- 不使用 typed-patch，不使用 04e 开发题或原留出题
- 报告写 `repeat_id=0`，不声称 token 级种子复现

## 主结果

- requested：18，measurement_valid：18，coverage：1.0
- OracleConditionedFullPass：Single 0，Multi 0，Drop 0
- MultiAgentNetBenefit：**N/A**（原始算术 0.0，共同能力地板，不能记为零效应）
- ReviewCausalValue：**N/A**（处理组与对照组都在地板上）
- 正式结论：当前三道复合任务对固定模型形成共同能力地板，因此 F5 多 Agent 净价值无法识别。
- TargetCorrect：全部为 false
- 干预格 VerifiedPatchAdoptionRate：0.6667（常量改对了，隐藏测试仍失败）
- 干预格 TrueRevisionRate：1.0（意见字段常能写对）
- control 错误修改：6/9（援助、排班的三条轨都 `revise`）
- Drop intervention 3/3 `review_not_delivered` 且 FullPass=0，负控有效

## 预注册门

情况 C：Single 与 Multi 全部很低，R0 有效。这三道 L2 复合题冻结为难度上界，不修改、不补重复。Drop 干预失败只能说明没有明显要求泄漏，不能证明 Reviewer 有价值，因为正常 Multi 也全部失败。

## 首错

| first_error | n | 含义 |
|---|---:|---|
| false_positive_revision | 6 | 援助/排班 control：草稿已是 v1，仍编造理由要求修改 |
| hidden_test_failed | 9 | 路由 control 批准了阈值但仍写错 schema；干预格常改对常量但其余逻辑不对 |
| review_not_delivered | 3 | Drop 干预，设计如此 |

援助干预 Multi 的 Reviewer 写出了正确的 `required_change: {income_cap: 45000}`，终稿 `INCOME_CAP = 45000`，但 `eligible` 把 `'proof' in applicant` 当成证明材料，`allocate` 使用 `name`/`budget_request`，隐藏测试失败。这不是“只填 APPLIED_PATCH_IDS”：声明字段未出现，真实常量改了，复合约束没写对。

路由 control Multi 正确 `approve` 且 `HIGH_PRIORITY_THRESHOLD = 7`，但中心字段写成 `coverage`/`name`，与任务约定的 `region`/`id` 不一致。

## 不扩展的结论

- 不能说多 Agent 没有价值，也不能说有价值。两条轨都在地板上。
- 不能说 Executor 不会改文件。干预格多数改了登记常量。
- Drop 干预仍失败，没有把审核意见泄漏给第三次调用。
- Rule 正负控已通过，问题在 Agent 协议与复合产物实现，不是评分器。

## 下一步

L2 三题冻结。不修改、不补 Seed。正式净价值记 N/A。下一步是 EXP-GM-05b：L1 中等难度校准，先跑 `direct_final_spec`，不过门不得比较多 Agent。04f 与 GM-05c 均未开。

| instance | track | variant | valid | FullPass | first_error |
|---|---|---|---|---|---|
| gm05_aid_allocation_001_control_single_r0 | single | control | True | 0 | false_positive_revision |
| gm05_aid_allocation_001_control_multi_r0 | multi | control | True | 0 | false_positive_revision |
| gm05_aid_allocation_001_control_drop_r0 | drop | control | True | 0 | false_positive_revision |
| gm05_aid_allocation_001_intervention_single_r0 | single | intervention | True | 0 | hidden_test_failed |
| gm05_aid_allocation_001_intervention_multi_r0 | multi | intervention | True | 0 | hidden_test_failed |
| gm05_aid_allocation_001_intervention_drop_r0 | drop | intervention | True | 0 | review_not_delivered |
| gm05_shift_roster_001_control_single_r0 | single | control | True | 0 | false_positive_revision |
| gm05_shift_roster_001_control_multi_r0 | multi | control | True | 0 | false_positive_revision |
| gm05_shift_roster_001_control_drop_r0 | drop | control | True | 0 | false_positive_revision |
| gm05_shift_roster_001_intervention_single_r0 | single | intervention | True | 0 | hidden_test_failed |
| gm05_shift_roster_001_intervention_multi_r0 | multi | intervention | True | 0 | hidden_test_failed |
| gm05_shift_roster_001_intervention_drop_r0 | drop | intervention | True | 0 | review_not_delivered |
| gm05_incident_routing_001_control_single_r0 | single | control | True | 0 | hidden_test_failed |
| gm05_incident_routing_001_control_multi_r0 | multi | control | True | 0 | hidden_test_failed |
| gm05_incident_routing_001_control_drop_r0 | drop | control | True | 0 | hidden_test_failed |
| gm05_incident_routing_001_intervention_single_r0 | single | intervention | True | 0 | hidden_test_failed |
| gm05_incident_routing_001_intervention_multi_r0 | multi | intervention | True | 0 | hidden_test_failed |
| gm05_incident_routing_001_intervention_drop_r0 | drop | intervention | True | 0 | review_not_delivered |
