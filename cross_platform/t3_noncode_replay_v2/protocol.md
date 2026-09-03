# Shared-review replay protocol v2

## Estimand

在 reviewer 模型输出保持为同一对象时，GAWorld `ReviewChannel` 与 YuLan-OneSim `EventBus` 是否造成载荷送达、采纳或最终状态的差异。

## Unit and denominator

成对单位为同一 task × evidence variant。共 3 个既有非代码任务、2 个证据条件、6 个 reviewer 样本和 12 个平台重放格。平台效应条件分母只包括 reviewer 严格响应有效的成对单位；端到端 joint FullPass 固定分母始终为 6，不删除模型失败。

## Sampling

每个成对单位在平台之外恰好调用 reviewer 一次。注册候选提案和 reviewer 私有核验证据直接来自冻结的 v1 任务，避免 proposer 再采样。有效 reviewer 对象增加平台拥有的确定性 `review_id`，然后以同一对象、同一哈希和同一模型证据 ID 重放到两个平台。

## Replay

GAWorld 使用 `revise` 承载共同语义中的 `reject`，接收端从 evidence 字段恢复原共同对象；YuLan 通过显式 payload event 传递共同对象。两个平台在接收后都调用同一个 Benchmark 冻结的确定性状态转移函数。平台内不再调用模型。

## Outcomes

模型层报告严格结构化有效率和 reviewer Oracle 命中率。平台层报告载荷哈希一致、接收对象完全一致、确定性执行一致和 transport pass。平台差异只在 reviewer 样本有效时评价。joint FullPass 同时要求 reviewer 正确、平台运输正确和最终状态命中 Oracle。

## Stopping and exclusions

两次不计分真实接口校准固定先执行，必须 2/2 严格响应有效、观察到恰好 2 个物理尝试且没有内部重试。任何失败都停止正式采样，不补调用。正式阶段固定 6 次逻辑调用，每次最多一个物理请求；结构失败和 Provider 失败保留在固定分母，不替换。v1 历史输出不重算。
