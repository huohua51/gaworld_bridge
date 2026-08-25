# EXP-GM-T3-03

独立 Reviewer 私有信息的区分度实验。新题，不使用 T3-01/T3-02 三道开发题。保留 T3-02 已验证契约。

## 结果

`output/exp_gm_t3_03_20260825/`

- Direct FullPass=1.0（新题可做）
- 54 格 Coverage=1.0；gate=`off_floor`
- FullPass：Single=0.5，Multi=1.0，Drop=0.5
- Single intervention 首错：`review_decision_incorrect`（自检无私有核验信息）
- Drop intervention 首错：`review_payload_not_delivered`（丢弃后优势消失）
- ranking_eligible / generalization_claim：false
- multi_agent_value_estimable：true（仅本开发集）

Single/Drop 的 0.5 都是 control=1.0 与 intervention=0.0 的平均，不表示部分采用。
