# EXP-GM-C1-06 运行报告

## 结论

本轮不能作为完整C1回归：注册要求6格、36次调用，但托管前台会话在第4格第3次
请求期间被外部终止。目录永久保留，不续写、不补跑，Gate记为
`operator_session_interrupted`。

终止前写入21个请求、20个响应和20条物理尝试记录，完成3格：

| 格 | 可测 | FullPass | 首错 |
|---|---:|---:|---|
| floodgate control | 是 | 1 | none |
| floodgate intervention | 是 | 0 | retry_assignment_incorrect |
| vaccine coldroom control | 否 | N/A | model_response_invalid（TLS EOF） |

floodgate intervention 是有效的失败证据。初始方案正确触发保护NACK，平台把spec从
`spec-001`推进到`spec-002`，并拒绝旧plan确认；但模型重提案把Agent B分到
`fg712`，而注册规则要求从B的可行列表选择第一个未占用项`fg713`。平台没有接受
错误重提案，也没有签发当前plan或写入世界。这说明核心修复在这条失败路径上确实
阻止了错误方案，端到端失败发生在模型的重规划决策。

随后按新的事前注册和全新表面运行C1-07；C1-06证据不进入C1-07分母。
