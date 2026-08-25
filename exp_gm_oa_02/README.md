# EXP-GM-OA-02 Exclusive keep / revise

冻结 OA-01 的任务、结果和 Scorer。本实验不再增加 `need_change`，也不使用 `NONE` 占位符。

两个互斥动作：

- `keep_current_plan(evidence_event_id)`：不允许出现 `target` / `value`
- `revise_plan(target, value, evidence_event_id)`：必须包含修改字段

只在 OA-01 三道开发题上跑新协议 18 格。旧协议基线读取冻结的 OA-01 `need_change_gate` 18 格，不重跑。暂不建留出题，不改 GM-01/02，不开 GM-03。

## 结果

协议校准完成（`role: action_contract_calibration`，`protocol_result: pass`）。
`holdout_status: not_created`，`generalization_status: untested`。
留出题等 T3 repeat 0 与 N1 development pilot 之后交叉出题。

开发集预注册门通过：Coverage / ControlStabilityRate / AdaptationRate = 1.0，ContractFailureRate = 0。责任安排对照输出 `keep_current_plan`，不再带 `target`/`value`。只能说消除了开发集中的无意义占位符失败。报告：`output/exp_gm_oa_02_20260824/REPORT.md`。
