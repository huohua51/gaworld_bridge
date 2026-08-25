# T3 互斥审核动作

Agent 只使用下面两个互斥 JSON，不再填写 `decision + mismatches + required_change`，也不使用 typed-patch。

批准：

```json
{"action": "approve_draft", "evidence_id": "evidence-001"}
```

要求修改：

```json
{"action": "request_revision", "target": "threshold", "required_value": 70000, "evidence_id": "evidence-002"}
```

提交层：

- `approve_draft` 不能携带 `target` / `required_value`
- `request_revision` 必须包含修改目标和要求值
- Reviewer 不能写产物；Executor 不能读 Reviewer 私有标准
- 平台不自动改文件
- 是否采用以隐藏测试与文件常量为准，不看 `APPLIED_PATCH_IDS`

平台 `ReviewChannel` 仍用内部 mailbox 字段转发；那是通道适配，不是让模型再填旧 schema。
