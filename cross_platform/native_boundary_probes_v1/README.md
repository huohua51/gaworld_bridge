# 三平台原生身份、权限与追溯探针 v1

本实验对 GAWorld、YuLan-OneSim 和 AgentSociety 2 的固定原生接口执行四个完全离线的负向/追溯探针：身份冒用、私有数据读取、越权最终写入、消息 ID 关联。它解决上一轮共享载荷重放没有对三平台执行同一组对抗操作的问题。

实验刻意不输出综合分。三个接口的抽象层并不相同：GAWorld `ReviewChannel` 自带私有区和产物 ACL；YuLan `EventBus` 是路由总线；AgentSociety `SimpleSocialSpace` 是邮箱。某项原语不存在时记为 `not_applicable`，不会伪装成安全通过。

## 固定环境

- GAWorld commit `bfcd2a665a299ddc25660a33102169f8bcfd856e`；
- YuLan-OneSim commit `9829d722b528b733f8c8317315637071fa23b206`；
- AgentSociety commit `13e28b5e67a2a8f2f43d640ebf27859126da622e`；
- Python 分别使用工作区内 `.venv_gaworld_eval`、`.venv_yulan_onesim_eval`、`.venv_agentsociety_eval`；
- 新模型调用固定为 0。

正式运行会校验预注册、评测代码哈希、三份上游提交和被测源文件哈希。AgentSociety worker 会在导入前覆盖继承的模型凭据，使用无效哨兵值及 `127.0.0.1:9`，因此不会读取或消费用户 API Key。

```powershell
$env:PYTHONPATH = 'F:\proj\gaworld_eval_bridge;F:\proj\GAWorld;F:\proj\YuLan-OneSim-official\src'
F:\proj\.venv_agentsociety_eval\Scripts\python.exe `
  -m cross_platform.native_boundary_probes_v1.run `
  --phase formal `
  --out output\cross_platform_native_boundary_probes_v1_20260905
```

详细判定规则见 `protocol.md`。正式结果目录包含各平台原生回执、`probe_results.json`、`cell_table.json`、`capability_matrix.csv`、`RUN_MANIFEST.yaml`、`REPORT.md` 和 `INDEPENDENT_AUDIT.md`。

