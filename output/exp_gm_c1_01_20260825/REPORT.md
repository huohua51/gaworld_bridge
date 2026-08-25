# EXP-GM-C1-01 Direct 诊断（已冻结，不进矩阵）

```yaml
status: stopped_at_direct_gate
role: frozen_direct_diagnostic
measurement_result: pass
direct_coverage: 1.0
direct_fullpass: 0.1667
allocation_accuracy: 0.8333
multi_agent_matrix_run: false
multi_agent_value:
  value: N/A
  reason: direct_solvability_gate_failed
ranking_eligible: false
generalization_claim: false
primary_failure: conflict_detection_or_semantic_binding
```

测量有效，但没有通过 Direct 可做性门。不能进入多智能体矩阵，也不能解释协调能力。不能概括成“模型不会做集体协调”。

| 指标 | 结果 | 含义 |
| --- | ---: | --- |
| 唯一分配正确率 | 5/6 | 模型大多数时候能算出正确安排 |
| FullPass | 1/6 | 加上冲突判断、过程和结果条件后，大多数格失败 |
| 真实分配错误 | 1 格 | 设备预约 control 把 B 分到 `slot-3` |
| 多智能体价值 | N/A | 没有运行 Multi，不能讨论 |

5/6 格时段分配命中唯一 Oracle。4 格把 `conflict` 标反。当前更准确的问题是：模型大多能给出正确分配，但没有稳定区分“初始方案是否发生冲突”和“调整后的最终方案是否仍有冲突”。这可能是冲突检测能力问题，也可能是字段语义在完整上下文中被理解反了。

不回头修改 C1-01 冻结协议。组件拆解见 CAL-GM-C1-COMP-01。
