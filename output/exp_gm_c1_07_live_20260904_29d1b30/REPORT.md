# EXP-GM-C1-07 运行报告

## 结论

本轮完成固定分母，但Gate为`measurement_invalid`，不能宣称C1端到端回归通过，
也不能据此判定GAWorld核心修复失败。

| 指标 | 结果 |
|---|---:|
| 注册格 | 6/6完成 |
| 逻辑调用 | 36/36 |
| 物理尝试 | 36 |
| 传输重试 | 0 |
| 可测格 | 1/6（coverage=0.1667） |
| 可测格FullPass | 1/1 |
| Provider SSL错误 | 8次 |
| 结构合法但字段值非法 | 1次`slot_invalid` |

唯一可测格是solar-array intervention；它完整经过保护NACK、spec升级、旧plan拒绝、
权威current-spec重提案、平台发号、双Agent确认与世界写入，FullPass=1。其余5格
至少有一个模型响应无效，因此按测量门不评分；其中4格含TLS SSL EOF，另1格同时
出现TLS错误与`slot_invalid`。

## 解释边界

- 通过格证明已合并核心代码能够承载一条完整正向链，但样本太少，不能关闭C1 Gate。
- 大量SSL失败发生在模型响应进入GAWorld机制之前，不能归因于协调通道。
- C1-06的有效intervention失败同时表明：即使平台不变量正确，GLM-5.2仍可能在
  权威重规划中选错“首个未占用可行项”。
- 预注册规定本轮后停止新增C1编号，因此不再为追求通过而补跑。
