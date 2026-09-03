# T3 非代码独立审核：GAWorld / YuLan-OneSim 同面实验

- 阶段：`offline_fixture_calibration`
- 门禁：`offline_runner_calibration_pass`
- 模型：`offline-t3-noncode-oracle-fixture / offline-t3-noncode-oracle-fixture-v1`
- 单元：12；调用：36/36
- GAWorld FullPass：1.0
- YuLan-OneSim FullPass：1.0
- 跨平台提示词逐角色完全一致：6/6
- 跨平台三角色输出完全一致：6/6

## 结果边界

这是三类新非代码任务、两种证据条件和单一模型的一轮协议同面对照。它测量提案—独立审核—采纳/拒绝—状态更新链，不代表全部 T3，更不构成平台总排名。
GAWorld 的原生审核通道只接受 approve/revise；本适配器把共同语义中的 reject 作为 revise 载体传递，并在执行者提示前还原为 reject。YuLan 使用锁定提交的原生 EventBus，任务语义与判分规则均由 Benchmark 冻结。
