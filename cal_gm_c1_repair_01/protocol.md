# CAL-GM-C1-REPAIR-01

复测 AP-C1-B-01 / AP-C1-C-01。不用 C1-01、C1-COMP-01 原题。全新资源名与时段。

## 协调闭环

```text
保存初始方案
→ 平台只返回 duplicate_resource_claim 等违规证据（不给出正确时段）
→ Agent 调用 propose_joint_assignment
→ 系统检查：高优先级是否保留、低优先级是否最早可行空闲、是否仍重复占用
→ 仍冲突则再给一次结构化违规，不得自动修正
→ Scorer 按真实占用计算 ActualFinalConflictFree
```

模型布尔只作 `SelfAssessmentCorrect`，不能作为最终世界事实。

## 预注册门

| 组件 | control | intervention | 必须达到 |
| --- | ---: | ---: | ---: |
| A 初始冲突检测 | 3/3 | 3/3 | 1.0 |
| B 最终方案核验 SelfAssessmentCorrect | 3/3 | 3/3 | StrictPair=1.0 |
| C 冲突后重新分配 | 3/3 | 3/3 | StrictPair=1.0 |
| C ActualFinalConflictFree | 3/3 | 3/3 | 1.0 |
| 未登记修改 | 0 | 0 | 0 |

全部通过才能 `c1_02_allowed: true`。此前 C1 主任务保持停止。不开 L1。
