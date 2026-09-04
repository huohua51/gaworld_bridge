# T3 AgentSociety 2 横向扩展

本目录把已经冻结的 T3 v2 六个 reviewer 对象重放到 AgentSociety 2，模型
调用数为零。它避免重新采样模型导致的平台比较混杂。

固定平台：AgentSociety 2 Git 提交
`13e28b5e67a2a8f2f43d640ebf27859126da622e`，包版本 2.8.4，执行面为
`SimpleSocialSpace.send_message/receive_messages`。

AgentSociety 2 顶层导入即校验 API key 和 base URL，即使本实验只调用本地邮箱。
适配器会在自身进程中覆盖为基准占位凭据和本机丢弃端点
`http://127.0.0.1:9`，不会读取真实 key，也不会发起模型调用。

离线 Oracle 校准：

```powershell
$env:PYTHONPATH = 'F:\proj\gaworld_eval_bridge'
F:\proj\.venv_agentsociety_eval\Scripts\python.exe `
  -m cross_platform.t3_noncode_replay_v3.run `
  --fixture-oracle `
  --out output\cross_platform_t3_noncode_replay_v3_fixture_20260905
```

注册并推送冻结输入后，才允许运行历史共享载荷扩展：

```powershell
$env:PYTHONPATH = 'F:\proj\gaworld_eval_bridge'
F:\proj\.venv_agentsociety_eval\Scripts\python.exe `
  -m cross_platform.t3_noncode_replay_v3.run `
  --historical-replay `
  --out output\cross_platform_t3_noncode_replay_v3_agentsociety_20260905
```

结果必须分别报告 payload transport、功能 FullPass、原生身份边界和消息 ID
可观察性；不得据此给三个项目排总体名次。
