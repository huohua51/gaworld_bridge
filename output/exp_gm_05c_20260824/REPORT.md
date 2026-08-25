# EXP-GM-05c-r0 SEALED measurement_invalid_repeat_0

四个净价值保持 N/A。原始输出全部保留，未手工补 JSON，未删除无效格。

无效格诊断为情况二：存档 `review_action.json` 是 `{}`，没有可唯一恢复的 decision / required_change。原始审核文本当时未被保存，因此不能做确定性 parser repair。

详见 `SEAL.json`。

---

- 模型：GLM-4-Flash，temperature=0
- ranking_eligible：false；n=18
- 共同 v1 初稿分叉；v2 在初稿生成后才发布
- 预注册门：A_r0
- OutcomeMultiAgentNetBenefit：N/A
- WorkflowMultiAgentNetBenefit：N/A
- ReviewDeliveryValue_target：N/A
- ReviewDeliveryValue_full：N/A
- 共同首错：false_positive_revision

| 指标 | Single | Multi | Drop |
| --- | ---: | ---: | ---: |
| Coverage | 0.8333 | 1.0 | 1.0 |
| TargetCorrect | 0.8 | 0.8333 | 0.5 |
| FullPass | 0.4 | 0.6667 | 0.1667 |
| StrictPair | 0.0 | 0.3333 | 0.0 |
| FalsePositiveRevisionRate | 1.0 | 0.6667 | 0.6667 |
| VerifiedPatchAdoptionRate | 1.0 | 1.0 | 0.0 |

| instance | track | variant | valid | TargetCorrect | FullPass | first_error | sha256 |
|---|---|---|---|---|---|---|---|
| gm05b_aid_elig_001_control_single_r0 | single | control | True | False | 0 | false_positive_revision | 8e0c63f6a2ad |
| gm05b_aid_elig_001_control_multi_r0 | multi | control | True | False | 0 | false_positive_revision | 8e0c63f6a2ad |
| gm05b_aid_elig_001_control_drop_r0 | drop | control | True | True | 0 | false_positive_revision | 8e0c63f6a2ad |
| gm05b_aid_elig_001_intervention_single_r0 | single | intervention | False | False | None | true_revision_missed | 8e0c63f6a2ad |
| gm05b_aid_elig_001_intervention_multi_r0 | multi | intervention | True | True | 1 | none | 8e0c63f6a2ad |
| gm05b_aid_elig_001_intervention_drop_r0 | drop | intervention | True | False | 0 | review_not_delivered | 8e0c63f6a2ad |
| gm05b_hours_cert_001_control_single_r0 | single | control | True | True | 0 | false_positive_revision | 43c9f9c5ae67 |
| gm05b_hours_cert_001_control_multi_r0 | multi | control | True | True | 0 | false_positive_revision | 43c9f9c5ae67 |
| gm05b_hours_cert_001_control_drop_r0 | drop | control | True | True | 0 | false_positive_revision | 43c9f9c5ae67 |
| gm05b_hours_cert_001_intervention_single_r0 | single | intervention | True | True | 1 | none | 43c9f9c5ae67 |
| gm05b_hours_cert_001_intervention_multi_r0 | multi | intervention | True | True | 1 | none | 43c9f9c5ae67 |
| gm05b_hours_cert_001_intervention_drop_r0 | drop | intervention | True | False | 0 | review_not_delivered | 43c9f9c5ae67 |
| gm05b_route_closed_001_control_single_r0 | single | control | True | True | 0 | false_positive_revision | 8a9e0fece058 |
| gm05b_route_closed_001_control_multi_r0 | multi | control | True | True | 1 | none | 8a9e0fece058 |
| gm05b_route_closed_001_control_drop_r0 | drop | control | True | True | 1 | none | 8a9e0fece058 |
| gm05b_route_closed_001_intervention_single_r0 | single | intervention | True | True | 1 | none | 01a5ba9de364 |
| gm05b_route_closed_001_intervention_multi_r0 | multi | intervention | True | True | 1 | none | 01a5ba9de364 |
| gm05b_route_closed_001_intervention_drop_r0 | drop | intervention | True | False | 0 | review_not_delivered | 01a5ba9de364 |

repeat 0 测量不完整（A_r0）：援助干预 Single 自检未产出可解析 JSON，`fields_extractable` 失败。净价值不得解释。不补 repeat 1/2，不建留出题，不开 04f。

共同初稿哈希在同一 `(task, variant)` 的三条轨上相同；v2 未进入初稿生成提示。Drop 干预 3/3 `review_not_delivered`。control 假阳性修订在援助题上把 `INCOME_CAP` 改成 100000，破坏了原本能过隐藏测试的草稿；Drop 因未采用该意见，同一份初稿 TargetCorrect 仍为 true。这只是格子级观察，不能在 A_r0 下扩写成 F5 结论。
