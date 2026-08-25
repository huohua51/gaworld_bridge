# EXP-HF-H1-01 基础设施

- 时间：2026-08-25
- ranking_eligible：false
- h1_formal_score：N/A
- 真人参照：未采集（0/18）
- Agent 刺激：18/18，来自功能留出 seed0 的 Full 轨

## 本轮能说明什么

三项密封留出在 seed0 上复现了开发集的同类正负控模式。这些 Full 轨迹可以制作 H1 刺激。

不能写：已经证明跨任务泛化；多智能体价值已经正式估计；留出通过等于正式 Benchmark 完成；一个 seed 等于稳定复现。

## 刺激抽样

机械抽取，禁止挑满分：

| 构念 | 轨道 | 来源 | 条数 |
|---|---|---|---|
| T3 | Full Multi | HO-GM-T3-01 seed0 | 6 |
| I1 | Full | HO-GM-I1-01 seed0 | 6 |
| L1 | Full Multi | HO-GM-L1-01 seed0 | 6 |

不用 Single / Drop / NoVerify / C1。功能角色是 sealed_holdout_result，H1 角色是 development_stimulus，不能冒充未来 H1 密封留出。

## 已完成 / 未开始

已完成：抽样冻结、18 条匿名 Agent 轨迹、三套真人协议、统一渲染、12 项 Rubric、真人执行页、盲评页。

未开始：真人采集、认知访谈、内部 Pilot、60 人盲评、四维差距计算。

C1 版本通道迁移为独立 Backlog，不阻塞本版。
