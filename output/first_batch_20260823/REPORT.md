# GAWorld 第二拍：eval_mode 已落地并复跑

- 时间：2026-08-23（UTC 17:29）
- 相对第一批：补上 Environment Contract，默认 `run` 行为不变
- 格子表：`gaworld_eval_bridge/output/first_batch_20260823/cell_table.json`

**仍不是模型榜。** 真模型矩阵要等本机 LLM 可用，且必须加 `--eval-mode`。

---

## 做了什么

在 GAWorld 增加 opt-in `eval_mode`：

| 开关 | 默认 `run` | `--eval-mode` |
|---|---|---|
| `dynamic_behavior` | 可改写活动 | 强制关闭 |
| `maybe_adjust_activity` | 可改程 | 冻结原计划 |
| `interview` 散文回填 | 保留（产品路径） | 拒绝，返回 `[]` |
| 日记 fallback | 保留 | 拒绝，返回空串 |
| `run_manifest.json` | 不写 | 写入 `output/run_manifest.json` |
| compare-event 正式轨 | 全指标 Δ 探索报告 | `--registered-metric` 写 `unique_path_audit.json` |

CLI：

```bash
python generative_city_sim.py run --eval-mode
python generative_city_sim.py interview --eval-mode --agent-id 4 --question "..."
python generative_city_sim.py compare-event --eval-mode --registered-metric mobility_intent ...
python generative_city_sim.py personal-what-if --eval-mode --registered-metric mobility_intent ...
```

代码：`gaworld/eval_mode.py`；测试：`tests/test_eval_mode.py`（已过）。

---

## 复跑结果

### eval_mode 合同

| instance | FullPass | 含义 |
|---|---|---|
| current_default_config | 0 | 默认仍会改写，不能当能力宿主 |
| eval_mode_enabled_runtime | **1** | 开启后：访谈拒散文、日记拒补写、改程冻结 |

### 结构化动作 Probe（Mock JSON，经 `parse_structured_action`）

| instance | 测量有效 | FullPass |
|---|---|---|
| capable_structured_json | 是 | 1 |
| locked_structured_json | 是 | **0**（锁死不是 0.5） |
| prose_no_action | 否 | N/A |

其余契约 / R1 / 唯一路径 / 烟雾与第一批一致。烟雾仍是默认模式，所以日志里还有 `daily_diary ... using fallback`——这正好说明**没开 eval_mode 时脚手架仍会代做**。

### P0 平台

`348 passed, 1 deselected`。跳过的是会打本机 Ollama 的 `test_li_vs_zhou_planning_differs`（11434 未开，属协议失败，不是能力失败）。

---

## 六个包（仍不加总）

| 包 | 本拍 | 可否排名 |
|---|---|---|
| P0 | `eval_mode` 已声明；默认 run 仍不合格；开启后合同成立 | 否 |
| P1 | Adapter 正负控、烟雾不变 | 否（无真模型） |
| P2 | 唯一路径审计 + 结构化 Pair 校准 | 校准通过 |
| P3 / P4 | 未跑 | planned |
| P5 | HumanScore / quiz 仍不可排名 | 否 |

---

## 下一步

1. 有可用 LLM 时，只在 `--eval-mode` 下跑保留工资对 + 偶遇返还对。
2. 烟雾仿真也应默认走 eval_mode，避免日记 fallback 再被记成模型产物。
3. TMS / 集体重规划仍等环境原语。
