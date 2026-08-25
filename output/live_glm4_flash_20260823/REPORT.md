# 真模型试跑：Paratera GLM-4-Flash

- 时间：2026-08-23
- 通道：`https://llmapi.paratera.com/v1`，模型 **`GLM-4-Flash`**
- 协议：eval_mode 风格，只收 `target_action` JSON；散文不计 0
- 格子：`live_structured_pairs_001.json`

## 通道

第一次 403 是模型名写错。本团队不能访问 `openai/glm-4-flash`；`GLM-4-Flash` 返回 200。`check_llm.py` 预览为「好」。

## 两对 Strict Pair

| pair | 对照 | 干预 | Pair |
|---|---|---|---|
| 信任返还 `trust_reciprocity_scale_001` | 还 30（≥10） | 还 0 | **1** |
| 保留工资 `reservation_wage_apply_001` | 9000 → accept | 6500 仍 accept（应为 reject） | **0** |

- 覆盖 1.0，可评分
- Macro Pair **0.5**
- FullPass 0（两对没有都过）
- 能力 Oracle，不是人类效度

保留工资干预锁死，和 SocietyDiag 里 Flash「对照对、条件变了手不变」是同一类失败，不是缺测。
