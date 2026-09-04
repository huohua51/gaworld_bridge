# EXP-GM-REL1-04 运行报告

## 结论

本轮完成6格、30/30逻辑调用，Gate为`measurement_invalid`：5格可测、1格因TLS
SSL EOF无效；可测格中3格FullPass，2格在latest-only更新选择上失败。

| 指标 | 结果 |
|---|---:|
| coverage | 5/6 = 0.8333 |
| 可测格FullPass | 3/5 = 0.6 |
| Observer原样转发 | 5/5 |
| formation完整计数 | 5/5 |
| formation来源选择 | 5/5 |
| formation动作复合正确 | 5/5 |
| latest-only更新来源 | 3/5 |
| update动作复合正确 | 3/5 |
| 物理尝试 / 重试 | 30 / 0 |

失败的ferry intervention与museum intervention都有同一首错：模型正确把
`evidence_row_ids`限制为最新一行，却仍保留形成阶段的旧可信来源和旧状态。也就是说，
它识别了“证据窗口变成最后一行”，但没有用该行的`reports[source] == outcome`
重新选择来源。

平台仍把两个错误业务选择绑定到了各自已采用的v2 trust message：动作中的
`evidence_message_id`、`adopted_trust_version=v2`、round和平台动作名均存在且匹配。
Manifest中的`update_action_bound=0.6`是一个复合Oracle指标，还同时要求业务值正确；
它不表示另外2格缺少证据ID。由此可区分：核心`submit_bound_action`修复在可测格中
机械生效，端到端失败位于模型的latest-only语义更新。

因此REL1核心绑定问题可视为“实现证据已得到支持”，但REL1整体能力Gate不能关闭。
