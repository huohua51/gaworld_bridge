# CAL-GM-C1-PRIORITY-01

窄组件校准 AP-C1-D-01。不覆盖 C1-02。不开 L1。不建留出。

## 只检查三件事

1. 冲突发生时，高优先级 Agent 的原分配是否保持不变；
2. 低优先级 Agent 是否选择最早可行空闲时段；
3. 最终方案是否同时无冲突、满足私有约束和优先级规则。

## 平台

```text
propose_joint_assignment
→ 检查资源冲突
→ 检查私有可行集合
→ 检查 priority_preservation
→ 返回违规类型
→ Coordinator 重试一次
```

违反优先级时只返回：

```json
{"violation": "priority_preservation_violation", "agent": "A"}
```

不得告诉模型 B 应该改到哪个时段。环境不得代做。
