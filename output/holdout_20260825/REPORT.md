# 密封留出 seed0（T3 / I1 / L1）

- 时间：2026-08-25
- 模型：GLM-4-Flash，temperature=0
- ranking_eligible：false
- 只跑 Direct（L1/T3）+ seed0 一次，不补 repeat 1/2
- 不得回头调协议再跑同一批
- 不覆盖开发集分数（含 L1-01b StrictPair 2/3）

两个测量/平台缺口已落地，但不改历史冻结分：

1. `compose()`：FullPass=0 时 `first_error` 不得再记 `none`，改为 `unexplained_failure`
2. `JointAssignmentChannel`：平台盖章 `plan_id`/`spec_version`；模型不得提交版本号。C1 评测通道未切换，AP-C1-F-01 仍开

## 留出结果（与开发集分开）

| 实验 | 覆盖 | seed0 主结果 | 与开发集 | 正式价值/排名 |
|---|---|---|---|---|
| HO-GM-T3-01 | 1.0 | Multi=1.0，Single=0.5，Drop=0.5 | 同一方向与首错 | 否（未补 54 格） |
| HO-GM-I1-01 | 1.0 | Full=1.0，Drop=0，NoVerify=0 | 同一正负控 | 否 |
| HO-GM-L1-01 | 1.0 | Full Multi 3/3+3/3+3/3；两种 Drop 中断 0/3 | 同一预注册门 | 否 |

T3 留出：Single 干预格首错均为 `review_decision_incorrect`；Drop 干预格均为 `review_payload_not_delivered`。GATE 模板里若仍出现「补 repeat 后再报告」，以预注册「只跑一次」为准，不补。

I1 留出：未经授权读取率 0；CommunicationValue=1.0，VerificationValue=1.0。`focused` 对外叫 `direct_verified_state`。

L1 留出：Drop Checkpoint 中断格首错 `checkpoint_not_delivered`；Drop Handoff 中断格 `handoff_not_delivered`。L1-01b 的 2/3 不改。

## 仍不能说的话

- 不能说正式 Benchmark 已完成
- 不能说跨任务泛化已证明
- 不能说跨模型稳健
- 不能进入排名
- 不能把开发集约 85% 理解成能力得分

路径：`output/holdout_t3_20260825`、`output/holdout_i1_20260825`、`output/holdout_l1_20260825`。
