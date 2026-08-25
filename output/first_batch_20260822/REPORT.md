# GAWorld 第一批 Workflow-Rubric 跑批报告

- 时间：2026-08-22（UTC 16:07）
- 宿主：`/home/wuxingye/projects/GAWorld`（`main` @ `ebdad18`）
- 工厂：`gaworld_eval_bridge/v0_first_batch/`
- 原始格子表：`gaworld_eval_bridge/output/first_batch_20260822/cell_table.json`

**这不是模型榜。** 本批只验证：评测工厂能否接到 GAWorld 现有代码，以及默认运行是否满足测量门。烟雾仿真用 Mock LLM。TMS、集体重规划、H1–H7 排名按规划保留为 planned，没有假分数。

契约题、产物题的 FullPass Rate 是**正负控通过率**（题库里故意放了散文、占位符、抄 reference），不能读成「GAWorld 能力 0.4」。

---

## 0. 九个接口落地状态

| 接口 | 本批做法 | 状态 |
|---|---|---|
| TaskSpec–Agent–Environment | 工厂在仓库外调用 GAWorld；未改主循环默认行为 | 部分 |
| Workflow 准入 | 正式题是契约 / 产物 / 唯一干预；Probe 只做诊断 | 已执行 |
| Task Card 七部分 | 每题一张卡；1 日烟雾不当成 264 小时人类效度卡 | 已执行 |
| R0–R3 | 先 Gate 再评分，代码组合 | 已执行 |
| 确定性 Scorer | 无 LLM Judge | 已执行 |
| FullPass + TaskScore + ProcessProfile | 每格三输出 | 已执行 |
| Instance→Workflow→Construct | 同一张 `cell_table.json` 派生 | 已执行 |
| 能力 / 人类双轴 | HumanScore 与算术 quiz 强制不可排名 | 已执行 |
| H1–H7 | schema 保留，本批全 N/A | 未开排名 |
| **Eval-mode Environment Contract（增补）** | 默认配置会改写活动；关闭 flag 后冻结 | **未通过** |

---

## 1. 先看测量门：默认 `run` 现在测不到模型

`eval_mode_environment_001` 整格 `measurement_invalid`。原因不是仿真崩了，而是协议不够：

| Gate | 结果 | 证据 |
|---|---|---|
| CONFIG 有 `eval_mode` | 失败 | 仓库内无此键 |
| 默认不改写 Agent 活动 | 失败 | `dynamic_behavior.enabled=True` |
| 关闭动态行为后活动冻结 | 通过 | `changed=False`，活动仍是「工作」 |
| 访谈无散文复用 | 失败 | `interview_agent` 解析失败时把同一段散文贴到每题 |
| 改写可检测 | 通过（诊断） | 饥饿=0.95 时「工作」被改成「找点吃的」 |

结论：正式能力榜不能用当前默认 `python generative_city_sim.py run`。评测运行必须显式关闭（并记录）`dynamic_behavior`、日记 fallback 和访谈散文复用。

烟雾仿真里已经出现脚手架代做：`daily_diary response too short for agent 4 (13 chars), using fallback`。评测器若把这篇日记当模型产物，会把台子成功记成模型成功。

---

## 2. Workflow 结果（格子级）

### 2.1 `contract_interview_001`｜访谈 JSON 契约

覆盖 1.0。正控 2/2 过；负控 3/3 被 R1 拒绝。这就是收紧契约的价值。

| instance | measurement_valid | FullPass | TaskScore | 含义 |
|---|---|---|---|---|
| valid_object_json | 是 | 1 | 1.0 | 标准 `{question,answer}` 数组 |
| valid_pair_array_json | 是 | 1 | 1.0 | `[q,a]` 数组，现解析器接受 |
| prose_no_json | 是 | 0 | 0.0 | 散文无 JSON，紧契约记 0 |
| runtime_prose_fallback | 是 | 0 | 0.0 | 复现当前 `interview_agent` 回退 |
| partial_missing_answers | 是 | 0 | 0.0 | 缺答不能当完整访谈 |

### 2.2 `work_artifact_r1_001`｜真实 WorkAdapter 的 R1

四个适配器（content / code / web_design / teaching）均用 GAWorld 原实现。正控 4 格过；空文件、占位符、抄 hidden reference、语法错误、非 HTML 均被 gate 为 0。

| 正控 | FullPass | 负控 | FullPass |
|---|---|---|---|
| content_ok | 1 | content_empty / placeholder / copy_reference | 0 |
| code_ok | 1 | code_syntax_fail | 0 |
| web_html_ok | 1 | web_html_invalid | 0 |
| teaching_ok | 1 | — | — |

### 2.3 `compare_event_unique_path_001`｜唯一干预审计

现有 `_compose_comparison_rows` 会对**全部** state 指标算 Δ。本 workflow 只登记 `mobility_intent`：

| instance | 测量是否有效 | FullPass | 含义 |
|---|---|---|---|
| unique_path_only | 是 | 1 | 只动登记路径，可解释为改手 |
| spillover_unregistered_metrics | **否** | N/A | stress/emotion 同时动，禁止当因果分 |
| null_no_change | 是 | 1 | 零效应对照，登记路径确实没变 |

覆盖 0.67 是因为溢出格被正确标成 `measurement_invalid`，所以这张卡 **ranking_eligible=false**。这是审计在工作，不是题目坏了。

### 2.4 `causal_diagnostic_suite_001`｜量表改写的成对 Probe

沿用已有两道 rubric（信任返还、保留工资）：

| 批次 | 覆盖 | Strict Pair | 可解释为 |
|---|---|---|---|
| capable_traces | 1.0 | 1.0 | 条件变了手变了 |
| locked_yes_traces | 1.0 | **0.0** | 对照对、干预锁死；不是 0.5 |
| missing_target_action | 0.5 | 整批不可排名 | 缺动作不记 0 |

WorkDiag 18 对、SocietyDiag 16 对仍在原宿主，本批没有重跑，也没有改名塞进 GAWorld。

### 2.5 `sim_smoke_mock_llm_001`｜1 日 × 2 Agent 执行门

Mock LLM，Agent 4/5，`dynamic_behavior` 关闭。仿真完成，日志非空，调度了 `schedule / planning / reflection / daily_diary` 等任务。FullPass=1 只证明**台子能跑完**，`ranking_eligible=false`。

### 2.6 人类效度与假能力题：强制不可排名

| workflow | 状态 | 原因 |
|---|---|---|
| life_history_mock_score_001 | diagnostic | `create_mock_scores()`；主循环未接 `LifeHistoryEngine` |
| capability_quiz_not_workflow_001 | placeholder | `agent_capability_test.py` 是算术/类比题，不是 workflow |

HumanScore 原数值仍保留在格子 JSON 里（例如 memory 63.3%），但不进 P5 排名。

---

## 3. 六个对外指标包（导航，不加总）

| 包 | 本批结论 | 可否排名 |
|---|---|---|
| P0 测量完整性 | 工厂可评分；默认 run 无 eval_mode；pytest 337 过、1 个协议失败 | 否 |
| P1 Workflow 表现 | Adapter 正负控可用；烟雾 FullPass=1（Mock） | 否（无真实模型） |
| P2 因果适应 | 唯一路径审计有效；Probe capable=1 / locked=0 | 校准通过，非正式榜 |
| P3 系统鲁棒 | 未跑 Focused/E2E | 外部 v0.3 仍是 pilot |
| P4 多智能体过程 | TMS / 集体重规划未跑 | planned |
| P5 人类效度 | HumanScore mock；出行 JSD 仍在 AgentSociety | 否 |

---

## 4. P0 平台健康（GAWorld `pytest tests`）

- **337 passed，1 failed**，12 warnings（中文字体缺失，与评分无关）
- 失败：`tests/test_profile_context_diversity.py::TestPlanActionDiversity::test_li_vs_zhou_planning_differs`
- 原因：测试调用真实 `planning()` → `call_llm()`，本机 `localhost:11434` Ollama 未开。这是 **协议/夹具失败**，不是「李泽宇 vs 周婉清规划无差异」的能力结论
- 同文件里走 Mock / 离线路径的多样性测试已包含在 337 通过中

因此 P0 记：`platform_pytest=false`，失败归因 = `missing_local_llm_fixture`，不改任何能力分母。

---

## 5. 故意不跑 / 外部注册

本批不跑：

- `tms_expert_handoff_001`：没有私有 v2 owner、发布权限、request→ack→verify 事件链
- `collective_replanning_001`：地图不是可 replay 的路网，没有车辆时窗与配送完成状态
- `human_fidelity_svo_society_001`：人类样本不在本仓库；SocietyDiag 轨迹也不在 GAWorld `run` 里

外部实验继续留在原宿主，数字不迁入 GAWorld 总榜：

| 批次 | 状态 | 宿主 |
|---|---|---|
| WorkDiag v0.2 focused | formal | YuLan-OneSim |
| WorkDiag v0.3 Seed 0 双轨 | pilot | YuLan-OneSim |
| SocietyDiag v0.2 社会博弈 | formal | AgentSociety |
| 出行 no_shock JSD 45.15 | diagnostic | AgentSociety |

---

## 6. 下一步（仍按「先能测，再谈题」）

1. 给 GAWorld 加 `eval_mode`：关闭动态改写、日记 fallback、访谈散文复用，并写入 `run_manifest`。
2. 让 `interview` 只接受 1:1 JSON，失败记 R1=0，不再回填。
3. 把 `compare-event` 的正式轨改成「manifest 只登记一条路径」。
4. 真模型矩阵只在 eval_mode 下跑 `personal-what-if` 保留工资对 + 偶遇返还对。
5. 环境原语齐了再开 TMS / 集体重规划。

---

## 结论边界

- 本批证明评测工厂能接到 interview、WorkAdapter、compare-event 和主循环烟雾。
- 不证明任何 GLM / MiniMax 的职业或社会能力。
- 默认城市 `run` 目前不能作为能力评测宿主。
- HumanScore 与算术 quiz 可以继续作为工程自检，但不能进能力轴或人类效度轴。
