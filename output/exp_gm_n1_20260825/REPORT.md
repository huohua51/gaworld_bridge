# EXP-GM-N1

- 时间：2026-08-25T01:16:38.094576+00:00
- phase：all；gate：completed_repeats
- ranking_eligible：false
- 冻结：a6ff231b8f49b0280f3f4be63556b4bc6d3aa07c

## 测量门

- Coverage：1.0
- 预算均为 3 次：True
- Drop 隔离且 Relay 实际运行：True
- FullPass Direct / Full / Drop：0.3333 / 0.3333 / 0.5

- first_error：{'false_positive_revision': 18, 'none': 21, 'wrong_revision_value': 6, 'message_not_delivered': 9}

| instance | valid | FullPass | track | first_error |
|---|---|---|---|---|
| n1_bridge_status_001_control_direct_r0 | True | 0 | direct | false_positive_revision |
| n1_bridge_status_001_control_full_r0 | True | 0 | full | false_positive_revision |
| n1_bridge_status_001_control_drop_r0 | True | 1 | drop | none |
| n1_bridge_status_001_intervention_direct_r0 | True | 0 | direct | wrong_revision_value |
| n1_bridge_status_001_intervention_full_r0 | True | 0 | full | wrong_revision_value |
| n1_bridge_status_001_intervention_drop_r0 | True | 0 | drop | message_not_delivered |
| n1_ferry_status_001_control_direct_r0 | True | 0 | direct | false_positive_revision |
| n1_ferry_status_001_control_full_r0 | True | 0 | full | false_positive_revision |
| n1_ferry_status_001_control_drop_r0 | True | 1 | drop | none |
| n1_ferry_status_001_intervention_direct_r0 | True | 1 | direct | none |
| n1_ferry_status_001_intervention_full_r0 | True | 1 | full | none |
| n1_ferry_status_001_intervention_drop_r0 | True | 0 | drop | message_not_delivered |
| n1_warehouse_gate_001_control_direct_r0 | True | 0 | direct | false_positive_revision |
| n1_warehouse_gate_001_control_full_r0 | True | 0 | full | false_positive_revision |
| n1_warehouse_gate_001_control_drop_r0 | True | 1 | drop | none |
| n1_warehouse_gate_001_intervention_direct_r0 | True | 1 | direct | none |
| n1_warehouse_gate_001_intervention_full_r0 | True | 1 | full | none |
| n1_warehouse_gate_001_intervention_drop_r0 | True | 0 | drop | message_not_delivered |
| n1_bridge_status_001_control_direct_r1 | True | 0 | direct | false_positive_revision |
| n1_bridge_status_001_control_full_r1 | True | 0 | full | false_positive_revision |
| n1_bridge_status_001_control_drop_r1 | True | 1 | drop | none |
| n1_bridge_status_001_intervention_direct_r1 | True | 0 | direct | wrong_revision_value |
| n1_bridge_status_001_intervention_full_r1 | True | 0 | full | wrong_revision_value |
| n1_bridge_status_001_intervention_drop_r1 | True | 0 | drop | message_not_delivered |
| n1_ferry_status_001_control_direct_r1 | True | 0 | direct | false_positive_revision |
| n1_ferry_status_001_control_full_r1 | True | 0 | full | false_positive_revision |
| n1_ferry_status_001_control_drop_r1 | True | 1 | drop | none |
| n1_ferry_status_001_intervention_direct_r1 | True | 1 | direct | none |
| n1_ferry_status_001_intervention_full_r1 | True | 1 | full | none |
| n1_ferry_status_001_intervention_drop_r1 | True | 0 | drop | message_not_delivered |
| n1_warehouse_gate_001_control_direct_r1 | True | 0 | direct | false_positive_revision |
| n1_warehouse_gate_001_control_full_r1 | True | 0 | full | false_positive_revision |
| n1_warehouse_gate_001_control_drop_r1 | True | 1 | drop | none |
| n1_warehouse_gate_001_intervention_direct_r1 | True | 1 | direct | none |
| n1_warehouse_gate_001_intervention_full_r1 | True | 1 | full | none |
| n1_warehouse_gate_001_intervention_drop_r1 | True | 0 | drop | message_not_delivered |
| n1_bridge_status_001_control_direct_r2 | True | 0 | direct | false_positive_revision |
| n1_bridge_status_001_control_full_r2 | True | 0 | full | false_positive_revision |
| n1_bridge_status_001_control_drop_r2 | True | 1 | drop | none |
| n1_bridge_status_001_intervention_direct_r2 | True | 0 | direct | wrong_revision_value |
| n1_bridge_status_001_intervention_full_r2 | True | 0 | full | wrong_revision_value |
| n1_bridge_status_001_intervention_drop_r2 | True | 0 | drop | message_not_delivered |
| n1_ferry_status_001_control_direct_r2 | True | 0 | direct | false_positive_revision |
| n1_ferry_status_001_control_full_r2 | True | 0 | full | false_positive_revision |
| n1_ferry_status_001_control_drop_r2 | True | 1 | drop | none |
| n1_ferry_status_001_intervention_direct_r2 | True | 1 | direct | none |
| n1_ferry_status_001_intervention_full_r2 | True | 1 | full | none |
| n1_ferry_status_001_intervention_drop_r2 | True | 0 | drop | message_not_delivered |
| n1_warehouse_gate_001_control_direct_r2 | True | 0 | direct | false_positive_revision |
| n1_warehouse_gate_001_control_full_r2 | True | 0 | full | false_positive_revision |
| n1_warehouse_gate_001_control_drop_r2 | True | 1 | drop | none |
| n1_warehouse_gate_001_intervention_direct_r2 | True | 1 | direct | none |
| n1_warehouse_gate_001_intervention_full_r2 | True | 1 | full | none |
| n1_warehouse_gate_001_intervention_drop_r2 | True | 0 | drop | message_not_delivered |

**分支：** Coverage 通过。不在 seed0 宣布信息传播价值。

**退役：** 2026-08-25 正式退役。Direct/Full 共同地板，构念未测开。分数不改。不建 N1-02。核实传播由 I1 覆盖，最新状态更新由 REL1 覆盖。详见 `RETIRE.yaml`。
