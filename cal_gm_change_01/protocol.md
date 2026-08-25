# CAL-GM-CHANGE-01

只回答：当前值已经满足要求时能否保持不变；当前值与最新要求冲突时能否更新。

没有通信、Reviewer、文件生成或隐藏复合逻辑。

```json
{"decision": "keep", "evidence": {"path": "registered_field", "observed": 40, "required": 40}, "required_change": null}
{"decision": "update", "evidence": {"path": "registered_field", "observed": 40, "required": 35}, "required_change": {"path": "registered_field", "old_value": 40, "new_value": 35}}
```

keep 时 `required_change` 必须为 null。update 时必须给出 path / old_value / new_value。
evidence.observed 必须等于当前值，evidence.required 必须等于本变体要求值。
