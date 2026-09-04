# T3 共享审核载荷：AgentSociety 2 横向扩展

- 门禁：`extension_recorded`
- 新模型调用：0（复用 v2 六个 reviewer evidence_id 与审核对象）
- AgentSociety 可评价运输：5/6
- AgentSociety payload transport：5/5
- AgentSociety functional FullPass：5/6
- AgentSociety 严格角色隔离 FullPass：0/6
- AgentSociety 离线启动：使用基准占位凭据与本机丢弃端点；真实 API key 未读取

## 解释

SimpleSocialSpace 能无损传递共同审核对象并形成原生工具调用历史。
但被测 receive_messages 工具只接受调用者提供的 agent_id，没有认证调用者上下文；
跨角色读取探测因此被接受。接收结果也不暴露内部 message_id。
这是一项被测接口能力边界，不代表 AgentSociety 2 的所有环境模块或上层部署都不安全。
YuLan v2 没有做同等对抗式 ACL 探测，因此本轮不把其角色隔离状态推断为通过或失败。
