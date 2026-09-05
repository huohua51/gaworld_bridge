# CROSS-PLATFORM-NATIVE-BOUNDARY-PROBES-v1 结果

阶段：`formal`。本实验完全离线，新模型调用数为 **0**。

## 能力矩阵

| 探针 | GAWorld | YuLan-OneSim | AgentSociety2 |
|---|---:|---:|---:|
| P1 身份冒用 | fail | fail | fail |
| P2 私有数据读取 | pass | not_applicable | fail |
| P3 越权最终写入 | pass | fail | fail |
| P4 消息可追溯 | pass | pass | fail |

`pass` 表示被测原生边界满足预注册条件；`fail` 表示该边界接受了越权操作或没有暴露可关联 ID；`not_applicable` 表示固定原生表面没有对应能力，既不算通过也不算失败。

## 主要发现

GAWorld 的私有读取和最终产物写入都按角色拒绝，审核 ID 也能贯穿发送、投递、收件箱和审计；但 `emit_review` 只接收调用方给出的 `reviewer_id`，没有单独的认证调用者上下文，因此直接方法边界不能阻止身份冒用。

YuLan-OneSim 的 EventBus 接受调用方构造的 `from_agent_id`，也会把 Reviewer 声明的最终状态事件送到被动结果接收者；事件 ID 则能在发送对象、接收对象和原生 flow 中关联。EventBus 没有 owner-bound 私有存储读取原语，该格保留为 `not_applicable`。

AgentSociety2 的 SimpleSocialSpace 在所测直接边界允许调用方自报 sender、receiver 和 mailbox agent_id，因此身份冒用、跨角色邮箱读取和 Reviewer 最终提交都被接受。内部 Message 模型虽生成 message_id，但公开 send/receive 响应与工具历史没有暴露它，所以严格可追溯条件未通过。

## 不能推出什么

三者选定表面的抽象层不同，本实验不生成综合分、不做总体排名，也不能证明外部网关或完整部署没有额外认证。结果只定位到锁定提交上的直接原生接口，适合作为修复需求和后续回归基线。
