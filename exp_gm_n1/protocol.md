# N1 信息送达

问题：信息经过 Source 和 Relay 后，是否送到 DecisionMaker，并改变最终行动？

```text
Source：掌握真实状态（私有）
Relay：核验并转发
DecisionMaker：只根据收件箱提交动作
```

三轨，每格三次调用：

| 调用 | Direct | Full | Drop |
| --- | --- | --- | --- |
| 1 Source | 根据私有状态发出报告 | 同左 | 同左 |
| 2 Relay | 核验，但 DecisionMaker 不读这条转发 | 核验并送达 | 核验后丢弃 |
| 3 DecisionMaker | 环境注入核实状态 | 读取 Relay 送达 | 收件箱为空 |

DecisionMaker 互斥动作：

```json
{"action": "keep_current_plan", "evidence_message_id": "..."}
{"action": "revise_plan", "target": "...", "value": "...", "evidence_message_id": "..."}
```

平台 `RelayChannel` 负责私有隔离和丢弃。隐藏 Oracle 不进入任何提示。环境不改动作。审核调用必须保存逐字模型输出。
