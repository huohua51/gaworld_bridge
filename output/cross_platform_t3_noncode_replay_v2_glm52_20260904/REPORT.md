# T3 非代码共享审核载荷双平台重放 v2

- 阶段：`live_shared_review_replay`
- 门禁：`live_replay_recorded`
- 模型：`paratera_glm / GLM-5.2`
- reviewer 逻辑调用：6/6
- reviewer 严格结构化有效：5/6
- reviewer Oracle 命中：5/6
- 平台效应可评价对：5/6
- 平台差异对：0

## 平台运输结果

- GAWorld：transport 5/5；joint FullPass 5/6
- YuLan-OneSim：transport 5/5；joint FullPass 5/6

## 解释边界

每个任务条件只在平台外采样一次 reviewer；两个平台收到相同 evidence_id 和审核对象。
平台比较只使用 reviewer 响应有效的条件，固定分母的 joint FullPass 仍保留所有无效响应。
该实验隔离当前适配器的载荷运输差异，不构成两个平台的总体能力排名。
