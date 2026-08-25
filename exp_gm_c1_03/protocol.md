# EXP-GM-C1-03

完整多智能体重试回归。正式对象是 Full Multi。Direct 只作可做性。不覆盖 C1-02。

## 事件链

```text
A、B提交私有可行集
→ Coordinator生成第一版方案
→ 登记过的优先级与档案保护时段发生修订
→ 第一版方案因此确定性不再满足保护约束
→ Validator返回 priority_preservation_violation
→ Coordinator必须根据新NACK重新提交
→ A、B确认并执行

第一阶段 intervention 中 A 的申报首选与档案保护时段不同，因此即令第一版把双方都放在各自首选，保护修订仍会触发优先级 NACK。不是篡改模型答案。
```

intervention 不是人为篡改模型答案，而是任务中的状态更新，保证工作流自然进入 NACK 路径。

## 轨道

| 轨道 | 定位 |
| --- | --- |
| Direct | 新题可做性校准，非正式结果 |
| Full Multi | 正式评测对象；intervention 必须进入 NACK |
| Drop Protection | 不送达保护修订；intervention 应无法按新优先级修复 |
| Drop Coordinator | 最终联合方案不交付 |

## 新增指标

| 指标 | 含义 |
| --- | --- |
| NackPathCoverage | intervention 是否真的进入 NACK 路径 |
| RetryRecoverySuccess | 收到 NACK 后是否形成完全正确的新方案 |
| ConstraintRegressionRate | 修复优先级时是否重新引入资源冲突 |
| ProtectedAssignmentRetention | 高优先级原分配是否保留 |
| LowPriorityReallocationCorrect | 低优先级是否选最早可行空闲时段 |
| FinalFullPass | 最终世界状态和过程是否全部通过 |

## 预注册门

```yaml
coverage: 1.0
nack_path_coverage_intervention: 1.0
retry_recovery_success: 1.0
constraint_regression_rate: 0.0
environment_auto_repair: 0
```

只有 R0 有效且真模型确实进入过 NACK 路径，结果才有资格关闭 AP-C1-D-01。
