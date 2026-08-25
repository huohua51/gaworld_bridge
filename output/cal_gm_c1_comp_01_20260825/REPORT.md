# CAL-GM-C1-COMP-01

```yaml
status: component_gate_failed
role: conflict_detection_allocation_decoupling
measurement_result: pass
platform_conformance_result: pass
agent_component_result: fail
first_broken_stage: conflict_resolution
secondary_failure: final_state_validation_polarity_lock
coverage: 1.0
pass_gate: false
A_initial_conflict: 1.0
B_final_conflict_free: 0.5
C_reallocate: 0.5
c1_02_allowed: false
multi_agent_value: N/A
ap_items: [AP-C1-B-01, AP-C1-C-01]
ranking_eligible: false
generalization_claim: false
multi_agent_matrix_run: false
parent: EXP-GM-C1-01
not_c1_01_items: true
```

Rule 正负控已过。18 格 Coverage=1.0。不用 C1-01 冻结题。不开 L1。不改 C1-01。不建 C1-02。

不要把 B/C 的 0.5 说成“半对半错”。三次重复完全一致，失败只发生在一个变体上。

## 按变体拆开

| 组件 | control | intervention | 合计 | 稳定行为 |
| --- | ---: | ---: | ---: | --- |
| A 初始冲突检测 | 3/3 | 3/3 | 6/6 | 能判断调整前是否同一资源同一时段 |
| B 最终方案核验 | 0/3 | 3/3 | 3/6 | 三格都输出 `final_plan_conflict_free=false` |
| C 冲突后重新分配 | 3/3 | 0/3 | 3/6 | 无冲突时交差正确；被告知冲突后仍把两人分到 `h8` |

| 指标 | 结果 | 含义 |
| --- | ---: | --- |
| A FullPass | 6/6 | 单字段 `initial_conflict_detected` 可用 |
| B control | 0/3 | 最终方案 `bench-1`/`bench-2` 无重复，模型仍标 `false` |
| B intervention | 3/3 | 最终方案两人同占 `bench-1`，标 `false` 碰巧正确 |
| C control | 3/3 | 无冲突，首选不同，交差 `{h8, h9}` |
| C intervention | 0/3 | 已告知初始冲突和优先级规则，仍交差 `{h8, h8}` |
| 多智能体价值 | N/A | 组件校准，不跑 Multi |

## 对照解释表

| 检测 | 分配 | 本实验 |
| --- | --- | --- |
| 失败 / 通过 | 通过 | 否。A 通过，但 C 在冲突后失败 |
| 通过 | 失败 | **最接近。** A 能发现初始冲突；C 不会按规则把低优先级挪到最早空闲 |
| 两者都通过 | C1-01 失败 | 否。B、C 未过门，不能把 C1-01 归因成完整上下文接口退化 |
| 两者都失败 | Direct 地板，停止 C1 | 否。A 全过，C control 全过，不是能力为零 |
| 两者都通过 | 可以建立 C1-02 | **否。不建 C1-02。** |

B 的 0.5 不能并进“检测通过”。它说明模型没有稳定区分“最终已无冲突”和“最终仍有冲突”：本实例上布尔极性塌缩为恒 `false`。这与 C1-01 含糊 `conflict` 字段的问题同类，但不能回改 C1-01。

C 的 0.5 不能并进“会重新分配”。无冲突时抄首选即可过门；真正要重新分配的 intervention 三格全失败。

## 结论

测量有效，组件门未过。`c1_02_allowed: false`。

当前更准确的问题不是“模型不会做集体协调”，也还不是“单组件会做、完整上下文才会退化”。拆开之后：

1. **会判断初始冲突**（A=1.0）。
2. **不会稳定断言最终方案已经无冲突**（B control 恒 `false`）。
3. **被告知冲突后，不会按“高优先级保留、低优先级最早空闲”重新分配**（C intervention 恒 `{h8,h8}`）。

## 因果链

```text
初始约束输入
    ↓
冲突检测：通过（A=1.0）
    ↓
按优先级重新分配：失败（C intervention 保持冲突分配）
    ↓
最终方案核验：极性锁死（B 恒 false）
    ↓
联合协调闭环无法成立
```

首要瓶颈是 AP-C1-C-01：`conflict_detected_but_not_repaired`。其次才是 AP-C1-B-01：`final_state_validation_polarity_lock`。二者都在 Agent 协议层，不是测量台问题。

下一步：给 GAWorld 增加「冲突证据 → 重新提案 → 约束核验」闭环，用全新组件题 `CAL-GM-C1-REPAIR-01` 复测。组件门通过前，不开 C1-02、不跑 Multi、不开始 L1、不改 C1-01。
