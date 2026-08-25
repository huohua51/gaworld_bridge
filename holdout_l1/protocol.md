# HO-GM-L1-01

中断恢复与角色接替。正式对象是 Full Multi。Direct 只作可做性。不覆盖 C1。

## 事件链

```text
Worker A 执行第一步，世界状态真实变化
→ A 提交已完成工作，平台盖检查点版本 ckpt-001
→ Coordinator 读取检查点并确认
→ control：A 仍在岗，从下一步继续完成
→ intervention：A 在第一里程碑后不可用
→ Coordinator 向 B 发出接替指令（不含剩余步骤的正确答案）
→ B 读取同一版本检查点，从正确步骤继续
→ B 完成剩余步骤，已完成工作不得覆盖，不得重复第一步
```

唯一 manipulation：Worker A 是否中断。不叠加需求修订、过期记忆或环境冲击。第三题只沿用已接收 ID 做核验和入库，不计算 checksum。Coordinator 必须根据 completed_steps 选择第一个尚未完成的步骤，不能根据 outputs 键跳步。

## 轨道

| 轨道 | 定位 |
| --- | --- |
| Direct | 新题可做性校准，非正式结果。control 输出三步；intervention 第一步视为已发生，只需输出剩余步骤 |
| Full Multi | 正式评测对象；检查点正常传递，intervention 由 B 接替 |
| Drop Checkpoint | A 产生检查点，B 的检查点副本被丢弃，B 仍运行 |
| Drop Handoff | Coordinator 运行，接替指令不送达 B |

## 指标

| 指标 | 检查 |
| --- | --- |
| CheckpointCreated | A 退出前是否形成平台盖章的有效检查点 |
| CheckpointDelivered | B 是否收到同一版本检查点 |
| ResumePositionCorrect | 接替者是否从正确步骤继续 |
| CompletedWorkPreserved | 已完成状态是否保留 |
| DuplicateActionRate | 是否重复已完成步骤 |
| HandoffCompleted | Coordinator 到接替者的指令是否闭环 |
| WorkflowComplete | 最终三步是否全部完成且输出正确 |
| RecoveryLatency | 从中断到 B 首次成功执行的事件数 |
| FullPass | 必要条件同时满足 |
| StrictPair | control 与 intervention 都通过 |

## 首错

```text
checkpoint_not_created
checkpoint_not_delivered
stale_checkpoint_used
handoff_not_delivered
resume_from_wrong_step
completed_work_overwritten
duplicate_action
remaining_step_skipped
workflow_not_completed
environment_fallback
completed_stage_output_not_consumed
invented_ids
```

## 运行顺序

```text
Task Card + Oracle + 事件链
→ Rule 正负控
→ 冻结哈希
→ Direct 6 格
→ Direct 过门
→ seed0：3 题 × 2 变体 × 3 轨 = 18 格
→ 停止。不补 repeat 1/2。失败不得回头调协议。
```
