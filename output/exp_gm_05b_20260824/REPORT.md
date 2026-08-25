# EXP-GM-05b 任务难度与 F5 可识别性校准

- 时间：2026-08-24
- 模型：GLM-4-Flash，temperature=0，`paratera_glm`
- ranking_eligible：false
- 这不是正式 F5 排名分，也不是完整工作流的 `MultiAgentNetBenefit`
- L2 三题冻结未改；未使用 typed-patch、04e 开发题或原留出题
- 重复为 repeat_id=0/1/2，temperature=0，不声称独立随机抽样

## 先登记的 GM-05（L2）

```yaml
status: stopped_at_repeat_0
gate_result: C_floor
estimands.multi_agent_net_benefit: N/A  # 不是零效应
estimands.review_causal_value: N/A
```

Coverage 100%，Rule 正负控通过，Drop 干预 3/3 失败。共同能力地板，F5 无法识别。

## 第一阶段：direct_final_spec（6 格）

无 Reviewer、无版本传播。control 直接看 v1，intervention 直接看 v2。每格 1 次调用。

- TargetCorrect：**6/6**
- 门：`maybe_too_easy`（仍允许进入审核实验）
- 解释：没有通信和审核时，模型本身能实现这三道两规则 L1 题。
- 因此 GM-05 的共同失败不是“基础 Python 生成完全不会”，而是复合任务过难。

| instance | variant | TargetCorrect | first_error |
|---|---|---|---|
| gm05b_aid_elig_001_control_direct_r0 | control | True | none |
| gm05b_aid_elig_001_intervention_direct_r0 | intervention | True | none |
| gm05b_hours_cert_001_control_direct_r0 | control | True | none |
| gm05b_hours_cert_001_intervention_direct_r0 | intervention | True | none |
| gm05b_route_closed_001_control_direct_r0 | control | True | none |
| gm05b_route_closed_001_intervention_direct_r0 | intervention | True | none |

## 第二阶段：固定 v1 初稿审核（54 格）

Rule 生成确定性 v1 初稿。Single / Multi / Drop 各 2 次调用。coverage=1.0，R0 全部有效。

| 轨 | TargetCorrect | OracleConditionedFullPass | FalsePositiveRevisionRate | VerifiedPatchAdoptionRate |
|---|---:|---:|---:|---:|
| Single | 1.0 | 0.5 | 1.0 | 1.0 |
| Multi | 1.0 | 1.0 | 0.0 | 1.0 |
| Drop | 0.5 | 0.5 | 0.0 | 0.0 |

FalsePositiveRevisionRate 只在 control 上计算；VerifiedPatchAdoptionRate 只在 intervention 上计算。Drop 干预的采用率为 0 是设计：消息被丢弃，终稿停在 v1。Single 的 TargetCorrect 仍是 1.0，说明假阳性修订没有把产物改错，只是协议 FullPass 失败。

### 估计值

- ReviewStageMultiAgentBenefit = FullPass_Multi − FullPass_SelfReview = **0.5**
- ReviewDeliveryValue = FullPass_Multi − FullPass_Drop = **0.5**

这两项不是地板上的 N/A。Direct 已证明任务可做，三轨结果分离。

价值来源拆开看：

- control：Multi=1，Single=0 → 独立 Reviewer 避免自检假阳性
- intervention：Multi=1，Drop=0 → 审核消息对改 v2 有因果作用

### 诊断

| 指标 | 值 | 说明 |
|---|---:|---|
| FalsePositiveRevisionRate | 0.3333 | 全部来自 Single control（9/9）；Multi/Drop control 均为 approve |
| TrueRevisionRate | 1.0 | 干预格审核意见字段正确 |
| VerifiedPatchAdoptionRate（含 Drop） | 0.6667 | Drop 干预收不到意见，终稿仍是 v1，属设计 |
| VerifiedPatchAdoptionRate（Multi 干预） | 1.0 | 审核送达后真实文件常量已改 |
| DeclaredPatchAdoptionRate | 0.0 | 没有写 APPLIED_PATCH_IDS 充数 |
| AcknowledgementExecutionGap | 0.0 | 没有“只声明不改文件” |

### 首错

| first_error | n | 含义 |
|---|---:|---|
| false_positive_revision | 9 | Single control：草稿已是 v1，自检仍 `revise` |
| review_not_delivered | 9 | Drop 干预，设计如此 |
| none | 36 | 其余格子 |

Single control 的典型输出：`decision=revise`，`required_change` 却仍是当前 v1 值（例如 `income_cap: 50000`）。同一份初稿上，独立 Reviewer 输出 `approve` 且 `required_change` 为空。

## 预注册门

`review_has_value_fill_repeats`：任务可做，审核信息有因果价值。已补 repeat 1/2 至 54 格，三轮模式相同。

不满足 04f 条件：Direct 能做 L1，Reviewer 意见正确，且 Executor 在收到意见后改对了文件。失败不在“位置+旧值+新值”落地。

## 不扩展的结论

- 不能把 GM-05 的原始 0 当成“多 Agent 没价值”。那是 L2 地板。
- 不能把 05b 的 0.5 当成完整 E2E 的 `MultiAgentNetBenefit`。生成阶段被刻意拆掉了。
- 不能说 L1 对生成仍太难。Direct 是天花板。
- 不能说 L1 对审核没有区分度。自检假阳性 vs 独立审核 vs 丢消息，三条轨分开了。
- 不要开 04f。
- 不要改 L2 三题，不要补 L2 Seed。

## 封存

L1 三题与 05b 协议冻结，不再修改。完整工作流收益改由 EXP-GM-05c 在共同初稿分叉上估计。留出题仍未创建。

证据：

- Direct：`output/exp_gm_05b_direct_20260824/`
- Review：`output/exp_gm_05b_review_20260824/`
- Freeze：`output/exp_gm_05b_freeze_20260824/FREEZE.json`
