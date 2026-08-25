# EXP-GM-05c-r1 Equal-budget full workflow (repeat 0, review contract)

- 模型：GLM-4-Flash，temperature=0
- ranking_eligible：false；n=18
- 共同 v1 初稿分叉；v2 在初稿生成后才发布
- 预注册门：A_r0_again
- OutcomeMultiAgentNetBenefit：N/A
- WorkflowMultiAgentNetBenefit：N/A
- ReviewDeliveryValue_target：N/A
- ReviewDeliveryValue_full：N/A
- 共同首错：model_contract_failure

| 指标 | Single | Multi | Drop |
| --- | ---: | ---: | ---: |
| Coverage | 0.0 | 0.1667 | 0.1667 |
| TargetCorrect | None | 1.0 | 1.0 |
| FullPass | None | 1.0 | 1.0 |
| StrictPair | None | None | None |
| FalsePositiveRevisionRate | None | 0.0 | 0.0 |
| VerifiedPatchAdoptionRate | None | None | None |

| instance | track | variant | valid | TargetCorrect | FullPass | first_error | sha256 |
|---|---|---|---|---|---|---|---|
| gm05b_aid_elig_001_control_single_r0 | single | control | False | True | None | model_contract_failure | 8e0c63f6a2ad |
| gm05b_aid_elig_001_control_multi_r0 | multi | control | False | True | None | model_contract_failure | 8e0c63f6a2ad |
| gm05b_aid_elig_001_control_drop_r0 | drop | control | False | True | None | model_contract_failure | 8e0c63f6a2ad |
| gm05b_aid_elig_001_intervention_single_r0 | single | intervention | False | False | None | model_contract_failure | 8e0c63f6a2ad |
| gm05b_aid_elig_001_intervention_multi_r0 | multi | intervention | False | False | None | model_contract_failure | 8e0c63f6a2ad |
| gm05b_aid_elig_001_intervention_drop_r0 | drop | intervention | False | False | None | model_contract_failure | 8e0c63f6a2ad |
| gm05b_hours_cert_001_control_single_r0 | single | control | False | True | None | model_contract_failure | 43c9f9c5ae67 |
| gm05b_hours_cert_001_control_multi_r0 | multi | control | False | True | None | model_contract_failure | 43c9f9c5ae67 |
| gm05b_hours_cert_001_control_drop_r0 | drop | control | False | True | None | model_contract_failure | 43c9f9c5ae67 |
| gm05b_hours_cert_001_intervention_single_r0 | single | intervention | False | False | None | model_contract_failure | 43c9f9c5ae67 |
| gm05b_hours_cert_001_intervention_multi_r0 | multi | intervention | False | False | None | model_contract_failure | 43c9f9c5ae67 |
| gm05b_hours_cert_001_intervention_drop_r0 | drop | intervention | False | False | None | model_contract_failure | 43c9f9c5ae67 |
| gm05b_route_closed_001_control_single_r0 | single | control | False | True | None | model_contract_failure | 01a5ba9de364 |
| gm05b_route_closed_001_control_multi_r0 | multi | control | True | True | 1 | none | 01a5ba9de364 |
| gm05b_route_closed_001_control_drop_r0 | drop | control | True | True | 1 | none | 01a5ba9de364 |
| gm05b_route_closed_001_intervention_single_r0 | single | intervention | False | False | None | model_contract_failure | 01a5ba9de364 |
| gm05b_route_closed_001_intervention_multi_r0 | multi | intervention | False | False | None | model_contract_failure | 01a5ba9de364 |
| gm05b_route_closed_001_intervention_drop_r0 | drop | intervention | False | False | None | model_contract_failure | 01a5ba9de364 |

Coverage 仍低于 100%。四个净价值 N/A。停止反复调提示，输出契约登记为平台缺口。

## 诊断（不改变分数）

16/18 格 `model_contract_failure`。第一次回复往往已有唯一结构化字段，但键名不是登记 schema：

- 用 `old_value`/`new_value`，缺顶层 `required_change`
- 或 `required_change` 有了，但缺 `mismatches`

格式重试不能提示正确决定或常量，模型第二次常改成无效包装，例如 `{"review_action":{"required_change":"Yes"}}`。

仅路由 control 的 Multi / Drop 两格产出合法 `approve`。Single 0/6 可提取。

r0 格子级现象仍只作诊断：自我审核曾把正确初稿改坏；不得在 A_r0_again 下估计完整工作流多 Agent 净收益。

下一步不是补 Seed、不是 04f、不是再调提示重跑 05c。GM-05 系列在完整工作流上停在测量缺口。
