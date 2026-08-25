# EXP-GM-T3-03

区分度实验。保留 T3-02 已验证的 keep/update 与 required_changes 契约，以及 payload 三段哈希。使用全新题目。

要回答的问题：在任务本身可做、协议已经校准的情况下，独立 Reviewer 的私有核验信息是否让 Multi 比 Single 更可靠；信息被丢弃时，这一优势是否消失？

## 信息隔离

- Direct：决策者看得到本轮私有要求值。用于可做性检查。Direct 失败则停止，不解释 Multi vs Single。
- Single 自检：只看公开 v1 简报和当前草稿，看不到 intervention 的私有要求值。
- Multi / Drop 的 Reviewer：看得到私有核验信息。
- Drop：Reviewer 正常输出，通道丢弃，Executor 读不到 payload。
- 通道只允许保存 → 传输 → 读取。不改写 Reviewer 意见。环境不改文件。Oracle 不进提示。

## 顺序

```text
新题 Direct 可做性检查
→ Rule 正负控
→ 冻结题目与 Oracle
→ Single / Multi / Drop 等预算 repeat 0
→ R0 有效且不共地板、不共天花板
→ 才补 repeat 1/2
```

T3-02 只证明集成已经修好。本实验不覆盖 T3-01/T3-02，不平均它们，不开 C1，不建留出。
