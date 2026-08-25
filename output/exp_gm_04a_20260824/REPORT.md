# EXP-GM-04a TASK-W1-lite 基础正控（已冻结）

- 时间：2026-08-24T04:04:08.434594+00:00
- 状态：`calibration` / `positive_control`，不可排名
- `diagnostic_target`：`basic_work_pipeline_integrity`
- 对照：Focused=`direct_adapter` vs Pipeline=`work_pipeline`（同一静态 brief）
- 不是正式机制题；不得与 WorkDiag v0.3 EPG 混排

## 覆盖与主结果

- requested：18
- measurement_valid：18
- coverage：1.0
- FullPass Rate（全部 18 格混合）：1.0

### 分轨

- Focused FullPass Rate：1.0
- E2E FullPass Rate：1.0
- 流程传播损失 EPG：0.0

| task | seed | Focused | E2E | EPG | focused first_error | e2e first_error |
|---|---|---|---|---|---|---|
| w1_wage_gate | 0 | 1 | 1 | 0 | none | none |
| w1_wage_gate | 1 | 1 | 1 | 0 | none | none |
| w1_wage_gate | 2 | 1 | 1 | 0 | none | none |
| w1_return_floor | 0 | 1 | 1 | 0 | none | none |
| w1_return_floor | 1 | 1 | 1 | 0 | none | none |
| w1_return_floor | 2 | 1 | 1 | 0 | none | none |
| w1_budget_remaining | 0 | 1 | 1 | 0 | none | none |
| w1_budget_remaining | 1 | 1 | 1 | 0 | none | none |
| w1_budget_remaining | 2 | 1 | 1 | 0 | none | none |

## 逐格

| instance | valid | FullPass | TaskScore | first_error |
|---|---|---|---|---|
| w1_wage_gate_focused_s0 | True | 1 | 1.0 | none |
| w1_wage_gate_e2e_s0 | True | 1 | 1.0 | none |
| w1_wage_gate_focused_s1 | True | 1 | 1.0 | none |
| w1_wage_gate_e2e_s1 | True | 1 | 1.0 | none |
| w1_wage_gate_focused_s2 | True | 1 | 1.0 | none |
| w1_wage_gate_e2e_s2 | True | 1 | 1.0 | none |
| w1_return_floor_focused_s0 | True | 1 | 1.0 | none |
| w1_return_floor_e2e_s0 | True | 1 | 1.0 | none |
| w1_return_floor_focused_s1 | True | 1 | 1.0 | none |
| w1_return_floor_e2e_s1 | True | 1 | 1.0 | none |
| w1_return_floor_focused_s2 | True | 1 | 1.0 | none |
| w1_return_floor_e2e_s2 | True | 1 | 1.0 | none |
| w1_budget_remaining_focused_s0 | True | 1 | 1.0 | none |
| w1_budget_remaining_e2e_s0 | True | 1 | 1.0 | none |
| w1_budget_remaining_focused_s1 | True | 1 | 1.0 | none |
| w1_budget_remaining_e2e_s1 | True | 1 | 1.0 | none |
| w1_budget_remaining_focused_s2 | True | 1 | 1.0 | none |
| w1_budget_remaining_e2e_s2 | True | 1 | 1.0 | none |

## 冻结说明

TASK-W1-lite / EXP-GM-04a 冻结为工作队列基础正控。以后每次修改工作子系统，可用这 18 格检查有没有回归。它暂时不能升级为正式机制题：没有唯一条件变化、没有必然失败的机制负控、R3 没有机会验证首错定位、EPG=0 只说明短链路无损、三道题都属于明确函数契约。

## 科学结论

EXP-GM-04a 证明 GAWorld 工作队列在单 Agent、静态规格、隐藏测试型微任务上不存在可观察的产物传播损失；该任务已冻结为基础正控。由于实验不包含需求变化、审核或角色依赖，尚未验证动态工作流和多智能体协作。下一步将通过 EXP-GM-04b 注入唯一的需求版本修订，检验最新要求能否沿队列传播并产生可定位的首错节点。

