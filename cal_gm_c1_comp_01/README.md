# CAL-GM-C1-COMP-01

把 C1-01 Direct 里混在一起的三件事拆开：初始冲突检测、最终方案核验、冲突后重新分配。

不用 C1-01 冻结题。不开 L1。不改 C1-01。

## 结果

`status: component_gate_failed`。18 格 Coverage=1.0，组件门未过。`c1_02_allowed: false`。

不要把 0.5 说成半对半错：

| 组件 | control | intervention | 合计 |
| --- | ---: | ---: | ---: |
| A 初始冲突检测 | 3/3 | 3/3 | 6/6 |
| B 最终方案核验 | 0/3 | 3/3 | 3/6 |
| C 冲突后重新分配 | 3/3 | 0/3 | 3/6 |

B control 恒输出 `final_plan_conflict_free=false`。C intervention 恒交差 `{h8,h8}`。

报告：`output/cal_gm_c1_comp_01_20260825/REPORT.md`。

不建 C1-02。协议复测见 `cal_gm_c1_repair_01`（已过门，`c1_02_allowed=true`）。不回头改 C1-01。
