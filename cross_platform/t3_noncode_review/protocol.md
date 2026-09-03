# T3 非代码提案—审核—采纳协议

三个角色依次工作：

1. **Proposer** 只能看到公开简报、基线状态和登记候选方案，提交候选方案；
2. **Reviewer** 额外持有独立核验材料，逐条判断硬约束并输出 `approve/reject`；
3. **Executor** 只能看到公开信息和已送达的结构化审核。`approve` 时采用候选状态，
   `reject` 时保持基线，不得读取 Reviewer 的私有原始数值。

`verified_support` 中所有约束满足；`verified_conflict` 中恰有一个硬约束失败。
Reviewer 的 `reason_code` 和 Executor 的 `disposition/reason_code` 使用封闭枚举，避免
出现 T5 中“结构字段正确但自由文本理由混淆”的不可评分灰区。

GAWorld 使用其真实 `ReviewChannel`；YuLan-OneSim 使用真实 `EventBus` 和显式载荷
事件子类。任务、提示、模型、调用顺序、评分器和状态效果均相同。两边只运行完整链，
传输丢弃因果负控已经由 T4 覆盖，本轮重点是独立审核与条件采纳。
