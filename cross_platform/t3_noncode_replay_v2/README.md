# T3 非代码共享审核载荷双平台重放 v2

本实验是 v1 失败后的机制隔离实验，不是新任务留出。v1 在 GAWorld 和 YuLan-OneSim 中分别调用 proposer、reviewer、executor，模型采样差异会沿链路放大，因而不能把最终差异单独归因于平台。

v2 把模型移到平台比较之前：每个任务 × 证据条件只调用一次 GLM-5.2 reviewer，生成一个带证据 ID 和 SHA-256 的共同审核对象。完全相同的对象随后分别进入 GAWorld `ReviewChannel` 和 YuLan-OneSim `EventBus`，两个平台使用同一个确定性执行规则。模型审核正确性与平台运输正确性分别报告。

固定设置：

- 模型：`GLM-5.2`
- Thinking：`disabled`
- 温度：`0`
- 单次上限：`256 tokens`
- 原生格式：`{"type":"json_object"}`
- JSON 解析：`strict`
- 每个逻辑调用最多 `1` 个物理请求
- 不计分接口校准：固定 2 次调用
- 正式 reviewer 采样：6 次调用

执行顺序：先跑 6 格离线 Oracle fixture；提交并推送预注册；再跑两次不计分真实接口校准。只有两次都得到严格 JSON、每次恰好一个物理尝试且没有内部重试，才允许启动 6 次正式 reviewer 采样。校准的语义正确性只记录，不作为选择性放行门。

离线校准：

```powershell
F:\proj\.venv_yulan_onesim_eval\Scripts\python.exe `
  -m cross_platform.t3_noncode_replay_v2.run `
  --fixture-oracle `
  --out output\cross_platform_t3_noncode_replay_v2_fixture_20260904
```

不计分真实接口校准：

```powershell
F:\proj\.venv_yulan_onesim_eval\Scripts\python.exe `
  -m cross_platform.t3_noncode_replay_v2.run `
  --live-calibration --provider paratera_glm --allow-live-model `
  --out output\cross_platform_t3_noncode_replay_v2_calibration_20260904
```

通过后正式重放：

```powershell
F:\proj\.venv_yulan_onesim_eval\Scripts\python.exe `
  -m cross_platform.t3_noncode_replay_v2.run `
  --live-replay --provider paratera_glm --allow-live-model `
  --calibration-manifest output\cross_platform_t3_noncode_replay_v2_calibration_20260904\RUN_MANIFEST.yaml `
  --out output\cross_platform_t3_noncode_replay_v2_glm52_20260904
```

本实验可以判断当前两个适配路径是否改变同一审核载荷，不能证明两个平台总体等效，也不能扩展为 H1–H7 人类效度结论。
