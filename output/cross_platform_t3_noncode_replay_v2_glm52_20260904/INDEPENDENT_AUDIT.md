# T3 非代码共享审核载荷重放：独立结果审计

审计日期：2026-09-04

## 1. 预注册与运行顺序

预注册及冻结实现先以提交 `eb0cb2c` 推送到远端，之后才进行了任何本实验付费调用。[注册文件](../../cross_platform/t3_noncode_replay_v2/registration_t3_noncode_replay_glm52.yaml) SHA-256 为 `932706c306dc99d43ec2345f1cdb13543f1dddea3e9e7849d9db6f23ffc58c9b`。实验复用了 v1 的三个已知任务，目的只是隔离此前发现的独立采样混淆，不是新任务留出。

运行分三步：零费用 Oracle 全矩阵、2 次不计分真实接口校准、6 次固定分母 reviewer 采样与双平台重放。没有事后改提示词、补调用或替换失败样本。

## 2. 不计分校准

校准实际解析到的 Provider/模型是 `paratera_glm / GLM-5.2`，并锁定 `thinking=disabled`、`temperature=0`、`max_tokens=256`、`response_format={type: json_object}`、`retry_attempts=1` 和 `json_normalization=strict`。

两次响应均为严格 JSON：2 个逻辑调用对应 2 个物理尝试，0 次内部重试，0 次围栏规范化。两次 reviewer 也都命中 Oracle，但语义正确性按注册规则没有参与 go/no-go。[校准 manifest](../cross_platform_t3_noncode_replay_v2_calibration_20260904/RUN_MANIFEST.yaml) SHA-256 为 `b8b6f4cd6794b9e1238ebfeadbec9ff20156106ced9ea144720321b64ebdc749`。

## 3. 正式 reviewer 样本

| 任务 | 条件 | 严格响应 | Oracle | 共享载荷 SHA-256 |
|---|---|---:|---:|---|
| 社区降温点 | support | 通过 | 通过 | `a7a4770e6a1a3c1c13a6e55e448cfa22ecf25a45638abbdc291f5bcd90ca3acc` |
| 社区降温点 | conflict | 通过 | 通过 | `13a9a41fe2ced76213f9a24d516c710a3e34d82e2cf810360e1dbd0761c5c93c` |
| 图书馆延时 | support | 通过 | 通过 | `161a6014a480e348e88f3df8264c3b0402695186592f7b7a956a9357a73a7c20` |
| 图书馆延时 | conflict | TLS失败 | 不可评价 | `74234e98afe7498fb5daf1f36ac2d78acc339464f950703b8c019892f982b90b`（JSON `null`） |
| 食物银行配送 | support | 通过 | 通过 | `636843015fec0176a220342c77805534636af1e34bc0f9bc1914f41389f61122` |
| 食物银行配送 | conflict | 通过 | 通过 | `7bcbc985c695293538ca89e366b898401083ae02b858d8a97346cacd703d6349` |

正式阶段有 6 个 `model_request`、6 个 `model_transport_attempt` 和 6 个 `model_response`。每个逻辑调用都只有一个物理尝试，内部重试为 0。第 4 次调用发生 `SSLError`；证据只保存错误类型，没有持久化第三方异常正文。API Key 和 Bearer Header 均未出现在校准或正式模型证据中。

严格固定分母结果是 5/6 有效，5/5 有效 reviewer 样本全部命中 Oracle。失败样本没有补跑，也没有用围栏清洗或其他响应替换。

## 4. 双平台重放

对 5 个有效 reviewer 样本，GAWorld 和 YuLan-OneSim 引用相同模型 evidence ID，并分别接收同一个共同审核对象。独立读取 12 个 cell 结果得到：

| 平台 | 总格 | transport 可评价 | transport 通过 | joint FullPass（固定6格） |
|---|---:|---:|---:|---:|
| GAWorld | 6 | 5 | 5 | 5/6 |
| YuLan-OneSim | 6 | 5 | 5 | 5/6 |

5/5 个可评价成对单位的入口审核哈希、接收对象和确定性 executor 输出完全一致，观察到的平台差异为 0。第 6 对因为共同 reviewer 请求先发生 TLS 失败，两个平台都没有可运输的审核对象；它计入 joint FullPass 失败，但不归因于任一平台。

## 5. 可以和不可以得出的结论

这轮修复了 v1 最关键的因果识别问题：平台不再各自抽样模型。在当前五个有效对象上，没有观察到 `ReviewChannel` 与 `EventBus` 改变共同审核载荷或其确定性执行结果。

这不等于证明两个平台“总体等效”。样本只有 5 个可评价对，任务仍是三个既有 Benchmark 表面，而且 executor 是统一确定性规则，不是平台原生自由行为。更准确的表述是：在本次注册的 T3 共享载荷重放协议上，两条适配运输路径均为 5/5，未观察到平台差异；唯一固定分母失败来自平台之前的 GLM-5.2 TLS 传输。

## 6. 关键文件哈希

- `RUN_MANIFEST.yaml`: `c2f7d0ba8f500adc8f3f63c60114413765381a4f7cebe889253d599f44428f60`
- `model_trace.jsonl`: `0f80ad6aa00474ff928db794850c93b91d58948acf611be973d822da5aa3895c`
- `cell_table.json`: `023f9ced26178d36b976075654301af98d5549adbed3130555bde86eab46ec07`
