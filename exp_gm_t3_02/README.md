# EXP-GM-T3-02

组件集成正控。把已校准的 CHANGE-01 判断契约和 APPLY-01 落实契约接回 T3-01 三道开发题。

- status: `calibration_pass`
- role: `component_integration_positive_control`
- ranking_eligible / generalization_claim / multi_agent_value_estimable: 均为 false
- 不补 54 格。Single 与 Multi 都在天花板，增加重复不能回答多智能体是否优于单智能体。
- 今后用途：每次修改通信、审核或执行协议后，用它检查组件重新接起来会不会退化。

## 口径

- Drop 的 PayloadIntegrity 写成「有传输时完整性为 1.0」。Drop 干预没有交付，不能读成成功传输。
- Drop 的 CompleteChangeAdoptionRate=0.5 应拆成 control=1.0、intervention=0.0。这是两种变体平均，不表示部分采用。

报告：`output/exp_gm_t3_02_20260825/REPORT.md`
