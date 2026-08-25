# CAL-GM-C1-REPAIR-01

```yaml
status: protocol_retest_pass
role: protocol_repair_retest
measurement_result: pass
platform_conformance_result: pass
agent_component_result: pass
coverage: 1.0
pass_gate: true
c1_02_allowed: true
ranking_eligible: false
generalization_claim: false
multi_agent_matrix_run: false
ap_items: [AP-C1-B-01, AP-C1-C-01]
parent: CAL-GM-C1-COMP-01
```

Rule 正负控已过。18 格 Coverage=1.0。全新实例，不用 C1-01 / C1-COMP-01 原题。环境未写入正确分配。

不要把这次通过写成 C1-01 已修好，也不要开 Multi 或 L1。它只证明：在拆开的组件复测集上，冲突证据闭环和 Scorer 自算最终占用可以把先前断掉的两步接上。

## 按变体拆开

| 组件 | control | intervention | 合计 |
| --- | ---: | ---: | ---: |
| A 初始冲突检测 | 3/3 | 3/3 | 6/6 |
| B SelfAssessmentCorrect | 3/3 | 3/3 | 6/6 |
| C 冲突后重新分配 | 3/3 | 3/3 | 6/6 |
| C ActualFinalConflictFree | 3/3 | 3/3 | 6/6 |
| UnregisteredModification | 0 | 0 | 0 |

相对 CAL-GM-C1-COMP-01 的关键对照（不同题目，不能平均）：

| 缺陷 | COMP-01 | REPAIR-01 |
| --- | --- | --- |
| AP-C1-B-01 极性锁死 | B control 恒 `false` | B control 稳定输出 `true`；intervention 输出 `false` |
| AP-C1-C-01 不修复 | intervention 保持 `{h8,h8}` | 初始 `{k1,k1}`，平台只返回 `duplicate_resource_claim`，模型提交 `{k1,k2}` |

C intervention 的世界状态（r0，r1/r2 相同）：初始两人占 `k1`；inspect 只点名冲突时段 `k1`，不含 `k2`；一次 `propose_joint_assignment` 后 A 保留 `k1`、B 到 `k2`；`actual_final_conflict_free=true`；`unregistered_modification=0`。没有第二次重试，也没有环境代改。

B 的世界事实由 Scorer 按占用表计算。模型布尔只记 `SelfAssessmentCorrect`（本集 6/6，`AssessmentExecutionGap=0`），不是最终世界的唯一来源。

## 结论

组件门全部通过。`c1_02_allowed: true`。

仍不能说：多 Agent 不会/会协调、Multi 优于 Single、C1-01 已修复、GAWorld 通信曾经失败。C1-01 保持冻结。不开 L1，不跑 Multi。若建 C1-02，必须用全新任务，并把 `initial_conflict_detected` / `final_plan_conflict_free` 拆开，由 Scorer 计算冲突事实。
