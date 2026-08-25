# EXP-GM-L1-01b seed0

- status：`development_partial_pass`
- 测量有效；中断恢复结果：未通过
- 功能进度约 85% = 评测建设与机制覆盖，不是 GAWorld 能力得分
- 不补 repeat 1/2；不重跑 L1；不覆盖本题
- 下一步：`CAL-GM-L1-RESUME-01`

## 正式结论

在 seed0 的三道中断任务中，只要检查点和接替消息都正常交付，B 在三个 interruption 实例上都能从正确阶段继续，并完成任务；丢掉任一信息后，三个 interruption 实例全部失败，说明 Checkpoint 与 Handoff 都具有明确的因果作用。但 Full Multi 的一格 control 中，Coordinator 错把续做位置从第二步跳到第三步，因此 StrictPair 只有 2/3，完整中断恢复闭环未通过。

```yaml
status: development_partial_pass
measurement_result: pass
checkpoint_causal_dependency: observed_seed0
handoff_causal_dependency: observed_seed0
full_multi_intervention: pass_3_of_3
full_multi_strict_pair: 2_of_3
workflow_bottleneck: coordinator_resume_point_selection
interruption_recovery_result: not_passed
repeat_1_2_allowed: false
ranking_eligible: false
```

## 变体必须拆开写

| 轨道 | control | interruption |
| --- | --- | --- |
| Full Multi | 2/3 通过 | 3/3 通过 |
| Drop Checkpoint | 3/3 通过 | 3/3 失败 |
| Drop Handoff | 3/3 通过 | 3/3 失败 |

### 检查点：创建 ≠ 交付 ≠ 内容正确

`CheckpointStatePreserved=1.0` 只表示检查点已创建并保存在平台，**不表示 B 收到了它**。Drop Checkpoint 的 intervention 仍是 Created=1、DeliveredToSuccessor=0。

| 指标 | 轨道 | control | intervention |
| --- | --- | ---: | ---: |
| CheckpointCreated | Full Multi | 1.0 | 1.0 |
| CheckpointCreated | Drop Checkpoint | 1.0 | 1.0 |
| CheckpointCreated | Drop Handoff | 1.0 | 1.0 |
| CheckpointDeliveredToSuccessor | Full Multi | 1.0 | 1.0 |
| CheckpointDeliveredToSuccessor | Drop Checkpoint | 1.0 | 0.0 |
| CheckpointDeliveredToSuccessor | Drop Handoff | 1.0 | 1.0 |
| CheckpointContentCorrect | 三轨相同 | 0.6667 | 0.6667 |

离心转子六格的检查点 `outputs` 都写成后续步骤键，`completed_steps` 只有第一步。不改 FullPass。

### 接替送达：禁止报告 0.5 平均值

Drop Handoff 的 `HandoffDelivered=0.5` 是 control=1.0、intervention=0.0 的变体平均，不是一半接替消息被送达。

| 轨道 | control | intervention |
| --- | ---: | ---: |
| Full Multi | 1.0 | 1.0 |
| Drop Checkpoint | 1.0 | 1.0 |
| Drop Handoff | 1.0 | 0.0 |

## 不改分勘误

```yaml
diagnostic_erratum:
  cell: l1_01_centrifuge_rotor_001_control_multi_r0
  recorded_first_error: none
  corrected_diagnostic_first_error: resume_from_wrong_step
  score_changed: false
```

冻结 Scorer 已用 `ResumeFromCorrectStage` 抓住该格；`first_error_node` 枚举不完整。见 `ERRATUM.yaml`。
