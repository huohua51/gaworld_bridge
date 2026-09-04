# EXP-GM-C1-06 协议

本轮固定复用 C1-05 的 `gaworld-benchmark-c1-authoritative-current-spec-v5`
提示协议和 v5 判分含义，只替换为三个新任务表面。每个表面各跑 control 与
intervention，一共 6 格；每格严格 6 个逻辑模型调用，总分母 36。

control 中保护登记不得制造 NACK；intervention 中旧方案必须因保护约束被拒绝，
旧 plan 的确认必须因 spec 过期被拒绝，重提案必须服从唯一权威 current spec，
由平台签发 plan/spec 标识，再由两个 Agent 确认并写入世界状态。

模型只输出注册业务字段。`plan_id`、`spec_version` 和实际写入权属于平台。
严格 JSON，不做 Markdown 清洗，不补跑失败格，Provider 的一次物理尝试即为一次
注册逻辑调用。
