# EXP-GM-T3-01 seed0 失败审计

只读分析。未修改 T3-01 Task Card / Oracle / 提示 / Scorer / 动作契约，未调用模型，未补 Seed。

## 正式口径

三轨初稿、预算和信息隔离满足公平性要求，但 Single 自检轨有 4 格无法提取审核动作，Coverage 只有 0.7778，因此完整工作流的多 Agent 净收益不可估计。

不能比较那 14 个有效格，也不能用 FullPass 为 0 说明共同地板。

```yaml
experiment_id: EXP-GM-T3-01
status: stopped_at_seed0
role: full_workflow_development_pilot
gate: A_r0
coverage: 0.7778
invalid_cells: 4
invalid_scope: single_self_review
failure_reason: fields_not_extractable
draft_fairness: pass
budget_parity: pass
drop_isolation: pass
multi_agent_net_benefit: N/A
review_delivery_value: N/A
ranking_eligible: false
repeat_1_2: not_run
holdout_status: not_created
```

## 4 格无效清单

| instance | variant | expected_action | extractor_error | first_error_node |
|---|---|---|---|---|
| t3_parking_threshold_001_control_single_r0 | control | approve_draft | empty | fields_not_extractable |
| t3_parking_threshold_001_intervention_single_r0 | intervention | request_revision | empty | fields_not_extractable |
| t3_deposit_ratio_001_control_single_r0 | control | approve_draft | empty | fields_not_extractable |
| t3_queue_cap_001_control_single_r0 | control | approve_draft | empty | fields_not_extractable |

Single 共 6 格，无效 4/6。另外两格 `deposit_ratio` / `queue_cap` 的 intervention Single 可以提取 `request_revision`，证明同一提取器和同一动作 Schema 在 Single 上并非一律失效。

## Schema 是否逐字一致

对 4 对 Single/Multi **最终渲染后的 Prompt** 做了 diff，并单独抽出动作定义行。

动作定义（4 行）在全部 4 对上 **字节级相同**，SHA256 均为：

`cbb0238423bb7df7fca1442db903294961aed199263446000b852898fef4329d`

```text
只输出一个 JSON 对象。动作必须是下面两个之一，不能混用字段。
批准：{"action": "approve_draft", "evidence_id": "<登记 evidence_id>"}。批准时不要输出 target 或 required_value。
要求修改：{"action": "request_revision", "target": "<登记 target>", "required_value": <要求值>, "evidence_id": "<登记 evidence_id>"}}。
不要输出 decision、mismatches、required_change，不要使用 NONE。
```

完整 Prompt 的差异只有设计内角色包装：

| 位置 | Single | Multi |
|---|---|---|
| 角色句 | 你正在自检刚才写的代码…【当前验收要求】 | 你是代码审核员…【审查标准】 |
| 私有标准 JSON | 与同任务同变体 Multi 相同 | 与 Single 相同 |
| 草稿 | 共享初稿，内容相同 | 共享初稿，内容相同 |

因此 **不是 Harness 给 Single 发了另一套动作 Schema**。不能登记为 harness/protocol_failure。

`request_revision` 示例末尾多了一个 `}`，Single 与 Multi 都有。Multi 四格对照都能抽出 JSON，所以这个共享笔误不能解释 Single 独有的提取失败。

## 提取器是否有差异

四格走同一条路径：`parse_json_object` → `action_contract`。

- 4 格 Single 持久化的 `review_raw.json` 都是 `{}`，`action_contract` 返回 `empty`，Scorer 记 `fields_not_extractable`。
- 4 格 Multi 对照都能抽出带 `action` 的对象；同一提取器复放 Multi 原文可通过。
- 2 格有效 Single 同样抽出 `request_revision`，`contract_error=ok`。

因此 **不是 scorer/extractor_failure**。

## 4 格属于哪一类错误

Harness **没有保存审核调用的逐字模型输出**，只保存了 `parse_json_object(text) or {}`。`call_log.json` 也只有 prompt，没有 response。逐字原文不可恢复。

在这个限制下，四格可以排除、不能细分的类型如下：

| 类型 | 结论 |
|---|---|
| Harness 差异（Schema 不同） | 排除。动作定义逐字一致。 |
| 提取器差异 | 排除。同一提取器对 Multi 和 2 格有效 Single 成功。 |
| 包装错误 / 键名错误 / 动作错误 / 多段 JSON | **无法互斥判定**。持久化结果是空对象，说明原文未能解析成 JSON 对象，但不能看见原文是解释文本、错误键、没输出动作，还是多段冲突 JSON。 |

总归因：**model_contract_failure**。模型在相同动作契约下，Single 自检 4/6 没有留下可提取对象。这不是台子给错 Schema，也不是提取器只对 Single 失效。

无法确认“模型根本没做审核动作”。在看不到原文时，不应靠放宽 Parser 去修 T3-01。

## 协议缺口

登记 `AP-T3-01-01-single-self-review-fields-not-extractable`。

```yaml
experiment: EXP-GM-T3-01
scope: single_self_review
rule_baseline: pass
model_cells_invalid: 4/6
effect: full_workflow_comparison_unidentifiable
classification: agent_platform_contract_incompatibility
historical_results_changed: false
same_task_rerun_allowed: false
```

T3-01 永不重跑。暂不开 T3-02。下一步若要做，只能是新编号的「Single 自检动作契约校准」，只校准动作接口，不重开完整工作流。

## 不做的事

- 不比较 14 个有效格的 FullPass
- 不把 FullPass=0 说成共同地板
- 不报告 Single/Multi/Drop 差值
- 不建 T3 / N1 / OA-02 留出题
- 不修改冻结实验
