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
