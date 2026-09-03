# YuLan-OneSim 横向评测适配器

本目录用于把 GAWorld Benchmark 的功能指标落到 YuLan-OneSim，而不是把两个
项目各自 README 中的数字直接并排。公平比较分成两层：

1. **协议同面比较**：相同任务、提示词、模型、温度、调用上限和评分器，只替换
   平台的消息传递与 Agent 执行机制。这一层才适合做平台能力横向结论。
2. **原生场景覆盖审计**：检查 YuLan-OneSim 自带场景能否表达 T3/T4/T5 等构念。
   因任务不同，只作描述性证据，不进入胜负排名。

## R0：零费用事件证据校准

R0 使用 YuLan-OneSim 的真实 `EventBus` 和确定性规则 Agent，不调用任何模型。
由于 `EventBus` 导入时会连带导入未使用的 `pyvis/IPython` 可视化组件，R0 在进程内
只替代这个可选导入符号；事件类、队列、路由、跟踪与导出代码仍全部来自锁定的
YuLan-OneSim 提交。
它分别运行完整链路、桥接点不转发、未知目标三种情况，并同时保存：

- EventBus 记录的“尝试处理”序列；
- 接收者 `add_event` 实际收到的事件；
- 原生 event-flow 导出；
- 原始与导出的父事件关系。

运行：

```powershell
F:\proj\.venv_yulan_onesim_eval\Scripts\python.exe `
  -m cross_platform.yulan_onesim.run_r0 `
  --out output\cross_platform_yulan_r0_20260903
```

必须从 `F:\proj\gaworld_eval_bridge` 运行。R0 通过只说明确定性正负对照正常，
不代表真实模型已完成横评。只有确认原生导出足够，或适配器明确补充了接收回执，
才进入冻结后的 GLM-5.2 小规模 T4 同面实验。

## 当前进度（2026-09-03）

- 官方仓库已锁定到 `9829d722b528b733f8c8317315637071fa23b206`；
- R0 三个确定性用例完成，发现原生 flow 不足以独立证明未知目标失败和全局终止；
- 18 格规则校准完成，60 个提示与 GAWorld 参考哈希一致；
- GLM-5.2 横评完成 17 个完整格，57/57 响应结构有效；
- 1 个格因外部进程中断按注册规则记为失败且未补跑；
- 完整格 FullPass 向量与 GAWorld 一致 17/17；固定 18 格口径为 GAWorld 12/18、YuLan 11/18。

T5-v3 eligibility-scope 同面先导也已完成：

- 第一轮零费用校准发现基础 `Event` 不会保留任意政策载荷，失败证据保留；
- 显式事件子类修正后的 v2 离线校准为 9/9 格、36/36 次规则调用通过；
- GLM-5.2 真实运行 9/9 格 FullPass，36/36 个结构化响应有效；
- 24 个政策通知和 12 个 absence 决策触发均有居民接收端回执；
- 与 GAWorld repeat 1 相比，36/36 个提示哈希、36/36 个 scope 输出、9/9 格动作与 FullPass 精确一致；
- 自由文本理由仍混淆 absence 与 nonbinding，该项不在冻结分数内，且 GAWorld 参考也出现。

详细论证见
`output/cross_platform_yulan_t4_combined_20260903/REPORT.md`，原生场景的构念对应边界见
`NATIVE_SCENARIO_COVERAGE.md`。

T5 的完整结果与声明边界见
`output/cross_platform_yulan_t5_glm52_20260903/REPORT.md`。
