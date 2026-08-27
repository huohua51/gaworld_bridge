# T5-v3 密封新任务与跨模型复测报告

## 结论

T5-v3 eligibility-scope 协议在三个全新任务表面上通过了密封留出，并在 GLM-5.2 与
gpt-5.4 之间得到完全一致的注册结果。两个模型各自 9/9 格 FullPass；72/72 次调用均返回
可解析的严格 JSON。两个模型的行为变化率均严格为：

```text
absence=0.0 / binding=0.5 / nonbinding=0.0
```

9/9 个任务×政策状态组合的 Prompt 字节一致，scope 布尔值、逐居民动作和 FullPass 的
跨模型精确一致率为 1.0。

## 预注册与设计完整性

- 预注册 ID：`T5-V3-SEALED-CROSS-MODEL-v1`
- 预注册文件 SHA-256：`ca781df55b712589a34de677e97ef363d99416d99fb678bebe85693bfff770ce`
- 预注册推送提交：`50e7aebec0010052c5b4ed479aa8d8fa4a21ba29`
- 冻结基线提交：`dede0a7d3bd6bbb6af6b9b066d56c4fed611a686`
- 设计：3 个新任务 × 3 种政策状态 × 2 个模型 × 4 个居民，共 18 格、72 次调用
- 固定条件：seed 0、temperature 0、`ranking_eligible=false`
- 执行顺序：先完成 GLM-5.2 的 9 格，再完成 gpt-5.4 的 9 格

三个任务分别是电梯安全检查、食品召回隔离和船舶压载检查；任务 ID、角色、群体、动作与
状态字段均不复用 T5 开发任务。任务、Prompt 协议、严格 JSON 契约、评分器、分母、预算与
停止规则在任何正式留出调用前共同冻结。GLM-5.2 的结果不能用于调整随后 gpt-5.4 的输入或评分。

模型与网关记录如下：

| 模型 | 运行适配器 | 实际网关/协议 |
| --- | --- | --- |
| GLM-5.2 | `paratera_glm` | Paratera / OpenAI Chat Completions |
| gpt-5.4 | `minimax` | qweapi / Anthropic Messages |

`minimax`是 GAWorld 中复用的适配器别名；本轮登记和观测到的受测模型均为 `gpt-5.4`，
没有把适配器名当作模型名报告。

## 注册结果

| 模型 | FullPass 格 | 严格 JSON | absence / binding / nonbinding 变化率 | scope 语义 | directive | 政策响应 |
| --- | ---: | ---: | --- | ---: | ---: | ---: |
| GLM-5.2 | 9/9 | 36/36 | `0 / 0.5 / 0` | 1.0 | 1.0 | 1.0 |
| gpt-5.4 | 9/9 | 36/36 | `0 / 0.5 / 0` | 1.0 | 1.0 | 1.0 |

两个模型的 `binding-minus-absence` 与 `binding-minus-nonbinding` 均为 0.5，
`nonbinding-minus-absence` 均为 0.0。所有 18 格的首错均为 `none`，没有非目标居民越界变化。

## 独立证据审计

- trace 文件：18 个；请求 72 条；响应 72 条；阻断调用 0 条。
- 严格 JSON、Schema、scope 语义与逐居民 directive：均为 72/72。
- binding 状态中的非授权居民：12/12 保持基线动作。
- nonbinding 状态中的目标居民：12/12 正确识别目标，但保持未授权并执行基线动作。
- Prompt 中出现旧的 `required_action` 键：0 次。
- 输出树中命中 API key 或 secret：0 次。
- 跨模型 Prompt 身份率：1.0；跨模型注册结果精确一致率：1.0。

机器可读总表见 [`JOINT_MANIFEST.yaml`](JOINT_MANIFEST.yaml)，逐格摘要见
[`cell_table.json`](cell_table.json)，原始请求、响应和政策轨迹保存在 `runs/` 下。

## 结论边界

该结果支持“冻结的 T5-v3 协议能在三个未见过的任务表面上迁移，并在这两个模型、seed 0
条件下产生相同注册结果”。它不证明真人决策效度、现实政策效果、更多任务或更多模型上的
普遍泛化，也不是排行榜成绩。下一步仍需扩大密封任务数、增加模型与重复种子，并接入 Human Reference。
