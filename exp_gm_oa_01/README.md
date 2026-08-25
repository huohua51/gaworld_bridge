# EXP-GM-OA-01 Over-adaptation gate（已冻结）

状态：`development_pilot`。任务、结果和 Scorer 冻结，不要改历史分数，也不要把 `keep` 的 `target="assignee_id"` 事后改成通过。

OA-01 **没有证明** GM-01/02 的过度适应已经解决，也**不能证明**它仍然存在；它只证明增加 `need_change` 布尔字段没有改善严格路径分。新任务中，模型的语义判断全部正确，唯一失败来自 `keep` 动作仍被要求填写无意义的 `target/value` 占位符。

登记：

- coverage: 1.0
- improvement_gate: fail
- need_change_gate_result: no_gain
- semantic_decision_result: pass
- remaining_failure: keep_placeholder_contract
- over_adaptation_mechanism: unresolved
- ranking_eligible: false

报告：`output/exp_gm_oa_01_20260824/REPORT.md`。后续改动作接口见 `exp_gm_oa_02/`。
