# T4/T5 Seed-0 Model Pilot

本Pilot建立在本地标签`benchmark-v1.1-rule`上，不修改该标签中的规则校准协议。

- 默认拒绝真实模型调用；只有同时提供`--provider`和`--allow-live-model`才会进入GAWorld路由。
- 每次调用写入请求、Prompt SHA-256、原始响应、响应SHA-256、严格JSON解析、延迟和Evidence ID。
- T4由模型逐节点决定接受、转发和目标行动。
- T5只向模型展示居民可见的政策内容，不展示`real_policy`/`placebo_policy`隐藏标签。
- Seed-0结果是开发Pilot，`ranking_eligible`始终为`false`。
- 离线Oracle Fixture只校准Runner和Scorer，不是模型能力结果。

先用`python -m model_pilot.smoke --provider NAME --allow-live-model`做一次最多64 tokens的
真实Provider连通性与严格JSON测试。只有Smoke通过后才运行36格Pilot。
