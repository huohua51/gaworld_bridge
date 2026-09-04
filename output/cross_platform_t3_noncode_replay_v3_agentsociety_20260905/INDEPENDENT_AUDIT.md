# AgentSociety 2 T3 共享载荷横向扩展：独立审计

- 审计日期：2026-09-05
- 预注册提交：`4374b23`
- 预注册编号：`CROSS-PLATFORM-T3-NONCODE-AGENTSOCIETY-EXTENSION-v3`
- 预注册文件 SHA-256：`ef15d7c2824c82949309747f0d7381147561c7dd234a4c65b29967202d673742`

## 一、这次比较究竟控制了什么

本轮没有重新请模型回答问题，而是直接复用 T3 v2 已经送入 GAWorld 和
YuLan-OneSim 的六个 reviewer 样本。审计逐项比较源文件与 AgentSociety 输出中的
`evidence_id`，六项的数量、内容与顺序全部相同。这样平台之间若出现差异，就不能再用
“模型这次随机答得不一样”解释。

六项中五项是结构化有效且符合 Oracle 的审核对象；另一个图书馆冲突条件在原始模型请求时
发生 `SSLError`，没有产生有效审核对象。按照冻结规则，它继续留在六项功能分母中，但不进入
平台运输分母，也没有被补跑或替换。

## 二、结果

| 平台/接口 | 可评价载荷运输 | 六项固定功能分母 | 本轮原生角色边界证据 |
| --- | ---: | ---: | --- |
| GAWorld `ReviewChannel` | 5/5 | 5/6 | 历史 v2 的两类负向操作均被拒绝，6/6 |
| YuLan-OneSim `EventBus` | 5/5 | 5/6 | v2 未做同等对抗探针，记为 `not_tested` |
| AgentSociety 2 `SimpleSocialSpace` | 5/5 | 5/6 | 声明他人 `agent_id` 的读取被接受，原生隔离 0/6 |

AgentSociety 的五个有效审核对象均满足：接收内容与源对象完全相等、规范化 SHA-256 相等、
原生 sender/receiver 记录正确、确定性 executor 转移正确、最终消息到达 result sink。因此，
在这个最小 T3 邮箱表面上，三条适配路径都能忠实承载同一审核决定。

AgentSociety 的身份探针回答的是另一个问题。被测
`SimpleSocialSpace.receive_messages(agent_id)` 只接收调用方提供的 ID，没有同时接收经过认证的
“当前调用者”身份。测试上下文以 reviewer 的 ID 读取 reviewer 私有标记，6/6 都成功；返回对象
也不包含内部 `message_id`。所以这里的严格角色隔离分为 0/6。这个结论只适用于当前公开工具
边界；如果实际部署在外层增加认证网关、按角色生成受限工具或代理级访问控制，整体系统可能有
额外保护，不能据此断言 AgentSociety 的所有模块都不安全。

## 三、复现与工程发现

- 固定 AgentSociety Git 提交为
  `13e28b5e67a2a8f2f43d640ebf27859126da622e`，上游源码未修改。
- 安装得到的 distribution 元数据版本为 2.8.4，但包内 `agentsociety2.__version__` 为 2.8.3。
  两个值均写入逐格证据，避免复现者误以为它们一致。
- 预注册的 `source_experiment.experiment_id` 文字多写了 `GLM52`，而冻结源
  `RUN_MANIFEST.yaml` 中的实际 ID 是 `CROSS-PLATFORM-T3-NONCODE-SHARED-REPLAY-v2`。
  预注册同时冻结了唯一源目录和 `RUN_MANIFEST.yaml`、`review_samples.json`、`cell_table.json`
  的 SHA-256，运行时三份哈希全部匹配，因此该登记文字差异不改变输入身份、分母或结果；为保留
  时间边界，原预注册不作事后回改。
- AgentSociety 2 在顶层导入时即要求 LLM API key 和 base URL，即使本实验只调用本地邮箱。
  适配器在自己的进程内强制使用基准占位凭据和 `http://127.0.0.1:9`，没有读取用户真实 key，
  新模型调用数为 0。
- 每格主流程记录 4 次原生工具调用、2 份接收回执，同时保存载荷哈希、最终状态和独立身份探针。

## 四、能下什么结论，不能下什么结论

可以说：在冻结的五个有效 T3 审核对象上，AgentSociety 2 的本地邮箱能够像已有 GAWorld/YuLan
适配路径一样无损传递载荷并支持确定性后续状态转移；同时，其被测接收接口本身不绑定经过认证的
调用者身份，审计标识的可观察性也弱于内部消息模型。

不能说：AgentSociety、GAWorld 与 YuLan 总体能力相同或谁“排名第一”。本轮没有测试城市、经济、
移动、记忆、群体规模、自由生成执行，也没有建立 H1–H7 真人参照。三平台的 ACL 探针范围也不完全
相同，YuLan 在本轮尤其是缺测而不是通过。

下一步若继续扩展，优先级应是：先为三平台定义完全同构的身份冒用、私有读取、越权写入和消息 ID
追踪探针；再选择 T5 政策作用域或 T6 长期轨迹中的一个原生场景做第二类机制比较。不要扩大模型矩阵，
因为当前主要未知量是平台机制覆盖而不是模型差异。

## 五、证据索引

- [正式运行清单](RUN_MANIFEST.yaml)
- [逐格结果](cell_table.json)
- [正式简报](REPORT.md)
- [预注册](../../cross_platform/t3_noncode_replay_v3/registration_agentsociety_v1.yaml)
- [协议边界](../../cross_platform/t3_noncode_replay_v3/protocol.md)
- [AgentSociety 官方仓库](https://github.com/tsinghua-fib-lab/AgentSociety)
