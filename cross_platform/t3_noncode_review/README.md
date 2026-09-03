# T3 非代码独立审核同面实验

这组任务检查一条具体的功能因果链：提案者提交候选方案，独立审核者依据只有自己可见的核验材料批准或拒绝，执行者只根据已交付的审核更新状态。它把原来 T3 的代码阈值题扩展到诊所、图书馆和食物银行三个非代码场景。

矩阵为 3 个任务 × 2 种证据条件 × 2 个平台，共 12 格。每格固定调用 proposer、reviewer、executor 三次，所以总预算是 36 次 GLM-5.2 调用。`verified_support` 应批准并采用候选状态；`verified_conflict` 应拒绝并保留基线状态。

GAWorld 使用真实 `ReviewChannel`。由于该通道的原生决策枚举是 `approve/revise`，共同协议中的 `reject` 以 `revise` 作为传输载体，并在执行者看到前恢复成 `reject`。YuLan-OneSim 使用锁定提交的真实 `EventBus` 和显式载荷事件子类。任务、证据、提示词、状态转移和评分规则由 Benchmark 统一冻结，不声称这些现实任务是任一平台的原生场景。

离线校准：

```powershell
F:\proj\.venv_yulan_onesim_eval\Scripts\python.exe `
  -m cross_platform.t3_noncode_review.run `
  --fixture-oracle `
  --out output\cross_platform_t3_noncode_fixture_<run_id>
```

真实调用必须在离线全矩阵通过并提交预注册后执行：

```powershell
F:\proj\.venv_yulan_onesim_eval\Scripts\python.exe `
  -m cross_platform.t3_noncode_review.run `
  --provider paratera_glm `
  --allow-live-model `
  --out output\cross_platform_t3_noncode_glm52_<run_id>
```

输出保留每个角色的模型请求与响应、平台原生/接收端事件证据、逐格评分、成对一致性和汇总报告。这个单模型、小样本同面实验不具备平台总排名资格，也不替代 H1–H7 的真人效度实验。
