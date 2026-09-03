# YuLan T5-v3 v1 离线校准失败记录

本目录是付费调用前的规则夹具校准，模型为离线 oracle，真实 API 调用数为 0。

## 观察

- `absence` 三格各完成 4 次离线调用；
- `binding` 与 `nonbinding` 六格均未进入模型调用；
- YuLan EventBus 确实把 `PolicyNotice` 送到了四名居民，但居民读取不到
  `policy_id`、`signal` 与 `eligible`。

## 首错与原因

首错发生在接收者 `add_event`：`Event` 对象没有 `policy_id`。检查官方
`Event.__init__` 后确认，基础类只保存核心事件字段，不会自动把任意 `kwargs`
变成对象属性。v1 适配器错误地把政策载荷作为普通关键字参数传给基础
`Event`，导致载荷被静默丢弃。

## 处理边界

这不是 GLM-5.2 的失败，也不是 T5 语义结果；它只证明 v1 适配器不合格。
失败目录保留，不补写结果。v2 在任何付费调用前改为显式事件子类，并重新
冻结代码指纹和运行设计。
