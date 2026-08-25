# EXP-HF-H1-01 第一版

H 轴与 F 轴分开。本实验不报功能 FullPass，不进入排名。

## 要回答的问题

在机制正常工作的情况下，GAWorld 的团队互动过程是否像真人？

第一版只用完整工作流：T3 Full Multi、I1 Full、L1 Full Multi。不用 Single、Drop、NoVerify。评价者看到信息缺失导致的失败，会把拟人化和机制损坏缠在一起。

## 刺激

```text
3 类任务 × 2 变体 × 3 条 Agent 轨迹 = 18
3 类任务 × 2 变体 × 3 条 Human 轨迹 = 18（尚未采集）
合计 36
```

Agent 来源：HO-GM-T3-01 / HO-GM-I1-01 / HO-GM-L1-01 的 seed0 Full 轨，按 task/variant 机械抽取。禁止挑满分或挑好看的。

```yaml
functional_role: sealed_holdout_result
H1_role: development_stimulus
```

它们不能冒充未来 H1 密封留出。正式泛化要另备未参与 Rubric 和网页修改的新刺激。

## 报告能写 / 不能写

能写：三项密封留出在 seed0 上复现了开发集的同类正负控模式。

不能写：已经证明跨任务泛化；多智能体价值已经正式估计；留出通过等于正式 Benchmark 完成；一个 seed 等于稳定复现。

## 匿名展示

评委只看到角色、可见信息、结构化动作和时间顺序。不显示模型名、实验号、FullPass、Human/Agent 标签。变体只标 A/B。

## 顺序

```text
冻结抽样规则
→ 真人任务协议
→ 真人执行网页，保存 Human Trace
→ 统一匿名展示
→ 12 项 Rubric
→ 5–8 人认知访谈（未开始）
→ 15–20 人内部 Pilot（未开始）
→ 冻结刺激、Rubric、排除规则和分析方案
→ 约 60 名独立盲评
→ 自然性、Agency、社会回应性、角色连续性差距
```

C1 不进第一版。平台版本通道迁移是独立 Backlog。
