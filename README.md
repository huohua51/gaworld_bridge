# GAWorld 评测桥（gaworld_eval_bridge）

这是 GAWorld 的**外部评测台**，不是城市仿真本体。协作者请同时拿到：

1. 仿真平台：[wuchaozju/GAWorld](https://github.com/wuchaozju/GAWorld) 的本机工作副本（评测通道：`eval_mode`、`ReviewChannel`、artifact 核验；联合方案盖章见 `PlanRegistry`）
2. 本仓库：实验定义、Oracle、评分器、Registry、冻结报告、H1 实验室

```text
projects/
  GAWorld/                 # 仿真 + 评测运行时
  gaworld_eval_bridge/     # 本仓库
```

**本文件是整条评测战役的总账。** 格子级数字以各实验 `output/*/REPORT.md` 与 `GATE.yaml` 为准；这里写结论、结论为什么成立、以及明确禁止的扩写。登记簿是 `registry.yaml`。

---

## 目录

1. [一页总状态](#一页总状态)
2. [允许写 / 禁止写](#允许写--禁止写)
3. [这套评测在测什么](#这套评测在测什么)
4. [核心科学结论（怎么读）](#核心科学结论怎么读)
5. [完成标准：可解释状态，不是满分](#完成标准可解释状态不是满分)
6. [约 85% 是什么、不是什么](#约-85-是什么不是什么)
7. [测量语法](#测量语法)
8. [时间线与阶段结论](#时间线与阶段结论)
9. [功能族分册](#功能族分册)
10. [两个测量/平台缺口](#两个测量平台缺口)
11. [密封留出 seed0](#密封留出-seed0)
12. [H1 拟人化（已启动基础设施）](#h1-拟人化已启动基础设施)
13. [仍开放的系统问题](#仍开放的系统问题)
14. [两个仓库怎么对齐](#两个仓库怎么对齐)
15. [环境与复现](#环境与复现)
16. [目录索引](#目录索引)

---

## 一页总状态

冻结日：2026-08-25。控制变量：`paratera_glm` / **GLM-4-Flash**，temperature=0，必须 `eval_mode`。评测对象是 **GAWorld 平台机制与 Agent 协议**，不是给 GLM 排名。

```yaml
functional_development: largely_complete
functional_holdout: seed0_pattern_replication
formal_generalization: pending
cross_task_generalization: false
cross_model_robustness: false
ranking_eligible: false
formal_benchmark: not_started

outcomes:
  T3: pass          # 开发集 + 留出 seed0 同模式
  I1: pass
  L1: pass          # 以 L1-01c 为准；L1-01b StrictPair 仍为 2/3
  REL1: fail        # 可解释失败
  C1: partial_pass  # 不进第一版 H1，不做 C1-04，不建 C1 留出
  N1: retired       # 不建 N1-02

h1_construction_allowed: true
H1_infrastructure: ready_to_start          # EXP-HF-H1-01
H1_human_reference: not_collected          # 0/18
H1_formal_score: N/A

first_error_coverage: resolved_for_future_runs   # 不重算历史分
platform_managed_versioning:
  core_mechanism: implemented                    # JointAssignmentChannel + PlanRegistry
  C1_channel_migrated: false
  AP-C1-F-01: open
```

---

## 允许写 / 禁止写

### 可以写

- GAWorld 的底层通信、权限和状态传播机制可以工作。
- 失败逐渐从「传状态」转移到 Agent 协作协议与社会推理。
- 功能侧每个代表功能已落到**可解释状态**（pass / partial_pass / fail / retired）。
- **三项密封留出在 seed0 上复现了开发集的同类正负控模式。**
- 第一轮开发性功能诊断约 85% = **评测建设与机制覆盖**，不是能力满分。

### 不可以写

- 已经证明跨任务泛化。
- 多智能体价值已经**正式估计**（T3 开发集 54 格可在开发集上报告方向；留出未补 54 格，不能当正式价值）。
- 留出通过等于正式 Benchmark 完成。
- 一个 seed 等于稳定复现。
- 约 85% 是 GAWorld 或 GLM 的能力得分。
- 把 HumanScore、效率、利润、「更合作」写成拟人化已经测过。
- 回改 GM-01/02/05、L1-01b 的 2/3、I1/T3-03/C1/N1/04e 的历史分。
- C1/REL1/N1 已经可以建留出或进入第一版 H1。

---

## 这套评测在测什么

F 轴（功能/协议）与 H 轴（人类效度）**分开**。本仓库到 2026-08-25 主战场是 F 轴；H1 刚搭基础设施，正式分不存在。

模型是**控制变量**，不是排名对象。同一模型、同一温度，用来暴露平台与协议，而不是比较哪个 LLM 更强。

开发集允许改协议、改平台、补组件校准。密封留出先冻哈希、只跑一次、失败不得回头调同一批协议再跑。留出结果与开发集**分开报告**，不覆盖、不平均。

环境不得替 Agent 改世界或改文件；Oracle 不得进入决策提示；权限隔离必须可测（越权读取率、Drop 轨）。

---

## 核心科学结论（怎么读）

> GAWorld 的底层通信、权限和状态传播机制可以正常工作；  
> 随着任务从「传递明确状态」升级为「理解审核意见」和「按登记规则更新来源可靠性」，  
> 失败逐渐转移到 Agent 协作协议与社会推理层。  
> 功能侧做完不等于满分。每个代表功能只需落到可解释状态。

**为什么可以这样说**

- 04a/04b：队列与需求版本传播在静态微任务上过门。
- I1：Full=1、Drop=0、NoVerify=0、越权=0 → 通道能送核实消息，且消息有因果价值。
- T3-03：Multi=1.0 > Single=0.5，且优势在 Drop 上消失；首错分别是「自检没有私有标准」和「审核消息未送达」。
- L1-01c：Full Multi 过；丢检查点或丢接替后中断格稳定失败，首错对得上被丢掉的那条边。
- REL1：Rule 负控成立，真模型 Full=0 → 平台能传信任状态，Agent 不按 `latest_is_binding` 覆盖旧多数。
- C1：冲突消解和私有约束能过，NACK 重试 0/3 → 部分机制过、重试协议不过。

**为什么不能说「GAWorld 已经改好」或「可以对外排名」**

- REL1、C1 的开放 AP 项仍在。
- 留出只跑了 seed0，没有跨模型、没有 H1 真人对照、没有正式盲评。
- 开发集改过协议；留出同模式 ≠ 泛化证明。

---

## 完成标准：可解释状态，不是满分

| 结局 | 含义 |
|---|---|
| **pass** | 测量有效，机制成功，正负控成立 |
| **partial_pass** | 基本机制成功，明确某一阶段失败 |
| **fail** | 题目可做、平台可运行，但 Agent/工作流稳定失败 |
| **retired** | 共同地板/天花板、构念重复或任务污染 |
| **N/A** | 测量无效，不能解释能力 |

功能侧做完，不等于所有任务都要满分。只要测量有效、任务可做、失败能定位并产生改进项，**失败也算这一类功能评测完成**。

---

## 约 85% 是什么、不是什么

**是**：评测工厂（R0–R3、Drop、权限、Trace、首错）、代表功能都跑过开发集、T3/I1/L1 可建留出。

**不是**：GAWorld 能力 85 分、GLM 排行榜、正式 Benchmark 进度条。

正式 Benchmark 还缺：跨任务泛化（留出 seed0 不够）、跨模型稳健性、H1 真人对照与盲评。

---

## 测量语法

| 层 | 问什么 | 失败时 |
|---|---|---|
| R0 | 测量是否有效（Coverage、预算、字段可抽取、eval_mode） | 停止能力解释 |
| R1 | 产物/权限是否合法 | 不把越权成功当成能力 |
| R2 | 目标是否正确 | 可报对错，但未必「干净成功」 |
| R3 | 是否绑定合法证据/契约 | 猜对但无核验证据不算干净成功 |

常用设计：

- **Direct**：题目可做性。过门才能解释 Multi。Direct 不是正式系统结果。
- **Full**：完整工作流，正式对象。
- **Drop**：人为丢掉检查点/接替/核验/审核消息。用来证明「那条边有没有因果价值」。
- **StrictPair**：同一题 control 与 intervention 都过。
- **first_error**：失败时的第一口定位。FullPass=0 时不得再记 `none`（新跑次）；历史冻结分不重算。

**读分禁令（反复踩过）**

- Drop 的 FullPass=0.5 几乎总是 **control=1 与 intervention=0 的变体平均**，不是「一半成功」。
- 检查点 Created=1 不等于 Delivered=1。
- focused 对外叫 `direct_verified_state`，不是能力上限。
- 不得把两个 measurement_invalid 的格子平均成「好像过了」。

---

## 时间线与阶段结论

### A. 评测工厂与早期工作流（约 08-22 ~ 08-24）

`v0_first_batch` 验证能接到 GAWorld：Gate 后才给分，H1–H7 全 N/A，无假排名分。

- **GM-01 / GM-02 / GM-05**：历史题与分数冻结，不回头改。05 系列关闭，不建 05c 留出。
- **04a**：静态微任务工作管线不丢产物。
- **04b**：执行前能读并采用最新需求。
- **04c**：审核通道与权限部分成功；Reviewer—Executor 协议不稳。
- **04e**：Reviewer 组件校准过；Executor 的 `typed_patch` **退役**（AP-04e-E-01）。不为把 04e-E 修到满分继续投入。04e 分数不改。
- **OA-01 / OA-02**：过度适应。OA-02 协议校准过门，泛化未测。

### B. I1 核实信息传播 — pass

路径：`output/exp_i1_20260824`。72 格 Coverage=1。

| 轨 | FullPass | 含义 |
|---|---|---|
| direct_verified_state（原 focused） | 1.0 | 直接给核实状态也能做对；不是上限 |
| Full | 1.0 | 观察→核验→送达→采用→动作 |
| Drop-verified | 0.0 | 丢掉核验消息后不能干净成功 |
| No-verification | 0.0 | 没有核验角色不能干净成功 |
| 越权读取 | 0.0 | 调度员读不到私有可信表 |

**结论**：核验消息有因果价值，Verifier 必要。CommunicationValue=1.0，VerificationValue=1.0。猜对但无合法核验证据不算干净成功。

**解释**：这测的是「可信信息有没有被传过去并绑在动作上」，不是「模型更聪明」。平台通信闭环可以结案；不自动推出 REL1 也会过。

### C. REL1 来源可靠性更新 — fail（可解释）

路径：`output/exp_rel1_20260824`。72 格 Coverage=1。Rule Full=1、Drop=0。真模型 Full=0.0，Focused=0.3333。

Oracle：`latest_is_binding=true`。形成看历史正确次数，更新时**最新一条必须覆盖旧多数**。

**结论**：平台能隔离账本、送达信任状态、拒绝越权。Agent 不会稳定按登记规则让最新结果覆盖旧多数（AP-REL1-01）。control 常见 `majority_not_recency_update`。

**解释**：这是功能失败，**不能**扩写成「模型没有人际信任」。H3 需要人类 dyad 数据。TrustDeliveryValue=0 是 Full 掉到地板后的算术，负控仍然挡住了干净成功。不做 REL1 留出。未做窄组件校准。

### D. T3 审核协作 — 开发集 pass

路线：T3-01 共同地板 → 组件 CHANGE-01 / APPLY-01 → T3-02 集成 → **T3-03 开发集 54 格**。

T3-03（`output/exp_gm_t3_03_20260825`）：

| 轨 | FullPass | 干预首错 |
|---|---|---|
| Multi | 1.0 | （通过） |
| Single | 0.5 | 9 格 `review_decision_incorrect`（自检看不到私有 v2） |
| Drop | 0.5 | 9 格 `review_payload_not_delivered` |

Single 的 0.5 = control 全过、intervention 全不过。Drop 同理。

**结论（仅开发集）**：独立 Reviewer 的私有信息有价值；消息丢失后优势消失。开发集上可报告该方向；`multi_agent_value_estimable=true` 仅限本开发集 54 格。不能当排名分，不能宣称泛化。不覆盖、不平均 T3-01/T3-02。

### E. N1 — retired

路径：`output/exp_gm_n1_20260825`。Direct/Full ≈ 0.333 共同地板，Drop=0.5。无法分开「消息没用」和「题本身不会做」。

构念与 I1（核实传播）、REL1（最新状态更新）重叠。正式退役。分数冻结。不补 Seed，不建 N1-02，不在地板上算 Multi-Agent Benefit，不建 N1 留出。

### F. C1 集体协调 — partial_pass

收口：`output/c1_stage_20260825`。不做 C1-04，不建 C1 留出，不再围同一缺陷调提示。

| 子能力 | 结局 |
|---|---|
| 基本冲突消解 | pass |
| 私有约束整合 | pass |
| 政策约束重规划 | partial |
| LLM NACK 重试恢复 | fail：进入重试 3/3，正确终局 0/3 |

C1-03：`retry_contract_failure` 2/3，`retry_not_adapted` 1/3。语义分配 0/3 正确（诊断，不改 FullPass）。

开放：AP-C1-D-01（拒绝后不调整联合方案）、AP-C1-F-01（模型管 plan_version 不合理）。C1 评测通道**不是**后来的 `JointAssignmentChannel`，故平台盖章落地后 AP-C1-F-01 仍开。

**解释**：能协调到「消冲突、守私有约束」，不能说「集体重规划 + 重试已经过关」。不进第一版 H1。

### G. L1 中断恢复 — 开发集 pass（以 01c 为准）

禁止回改 **L1-01b StrictPair = 2/3**。

1. **L1-01**：停在 Direct 门（5/6），未进 Multi。标本题退役。
2. **L1-01b**：测量有效。interruption 3/3 能接上；一格 control Coordinator 从第二步跳到第三步，StrictPair 2/3，**中断恢复未通过**。瓶颈：`coordinator_resume_point_selection`。离心转子 control 勘误：记录 `first_error=none`，诊断应为 `resume_from_wrong_step`，**不改分**。
3. **CAL-GM-L1-RESUME-01**：组件 18/18。登记为后来在 01c 上 `resolved_on_development_regression`。仍 `ranking_eligible: false`。
4. **L1-01c**（`output/exp_gm_l1_01c_20260825`）54 格：

| 轨 | control | interruption | 中断首错 |
|---|---|---|---|
| Full Multi | 9/9 | 9/9 | —（StrictPair 9/9） |
| Drop Checkpoint | 9/9 | 0/9 | `checkpoint_not_delivered` |
| Drop Handoff | 9/9 | 0/9 | `handoff_not_delivered` |

环境自动修复 = 0。检查点/接替因果在 54 格上 replicated。

**结论**：开发集上中断接替闭环成立。不能写泛化，不能进排名，不能覆盖 01b 的 2/3。

---

## 功能族分册

开发集总表冻结于 `output/functional_devset_20260825/`（当时留出尚未跑；留出补记见 `ADDENDUM_20260825_HOLDOUT.yaml` 与下文）。**不要改总表里的开发集分数。**

| 功能 | 开发集结局 | 代表实验 | 平台 | 留出 |
|---|---|---|---|---|
| T3 | pass | T3-03 | 主闭环 | HO-GM-T3-01 seed0 同模式 |
| I1 | pass | EXP-GM-I1 | 已闭环 | HO-GM-I1-01 seed0 同模式 |
| L1 | pass | L1-01c | 已闭环 | HO-GM-L1-01 seed0 同模式 |
| REL1 | fail | EXP-GM-REL1 | 未改进闭环 | 不允许 |
| C1 | partial_pass | C1-02 / 重试 C1-03 | 重试与版本未闭环 | 不允许 |
| N1 | retired | EXP-GM-N1 | n/a | 不允许 |
| 测量系统 | 缺口已落地（新跑次） | compose + PlanRegistry | C1 通道未迁 | — |
| 留出泛化 | seed0 同模式 ≠ 泛化 | 三包 HO-GM-* | — | 只跑一次 |
| H1 | 基础设施 | EXP-HF-H1-01 | — | 正式分 N/A |

---

## 两个测量/平台缺口

### 1. first_error 覆盖 — 对未来跑次已关闭

```yaml
first_error_coverage:
  status: resolved_for_future_runs
  historical_scores_recomputed: false
```

`v0_first_batch/schema.py` 的 `cover_first_error()`：FullPass=0 且 first_error 为空/`none` 时改为 `unexplained_failure`，并标 `first_error_enumerator_gap`。不改 FullPass，不重算 L1-01b 等冻结 JSON。L1-01b 勘误仍在 `ERRATUM.yaml`。

### 2. 平台管理 plan_id/spec_version — 接口已实现，C1 未迁

```yaml
platform_managed_versioning:
  core_mechanism: implemented
  T3_I1_L1_blocking: false
  C1_channel_migrated: false
  AP-C1-F-01: open
```

GAWorld：`gaworld/work/plan_registry.py`，`JointAssignmentChannel` 拒绝模型提交 `plan_id`/`spec_version`，由平台盖章。C1-03 用评测桥自己的 channel，历史分不动。不阻塞用 T3/I1/L1 做 H1。

---

## 密封留出 seed0

预注册：只跑 Direct（L1/T3）+ seed0 **一次**，不补 repeat 1/2。失败不得调协议重跑同一批。`ranking_eligible: false`。

汇总：`output/holdout_20260825/`。

| 实验 | 覆盖 | seed0 | 与开发集 | 正式价值 |
|---|---|---|---|---|
| HO-GM-T3-01 | 1.0 | Multi=1.0，Single=0.5，Drop=0.5 | 同方向、同首错 | 否（未补 54） |
| HO-GM-I1-01 | 1.0（24 格） | Full=1，Drop=0，NoVerify=0，越权=0 | 同正负控 | 否 |
| HO-GM-L1-01 | 1.0 | Full Multi 3/3+3/3+3/3；Drop 中断 0/3 | 同预注册门 | 否 |

T3 留出首错：Single 干预 `review_decision_incorrect`；Drop 干预 `review_payload_not_delivered`。若 GATE 模板仍写「补 repeat」，以预注册「只跑一次」为准。

```yaml
functional_role: sealed_holdout_result
H1_role: development_stimulus
```

留出 Full 轨可作 H1 **开发刺激**，不能冒充未来 H1 密封留出。正式 H1 泛化要另备未参与 Rubric/网页修改的新刺激。

**留出能说明**：全新任务表面上，开发集那类正负控还能出现。  
**留出不能说明**：跨任务泛化已证明；一个 seed 等于稳健复现。

---

## H1 拟人化（已启动基础设施）

实验：`EXP-HF-H1-01`。代码：`exp_hf_h1_01/`。产物：`output/exp_hf_h1_01_20260825/`。协议：`exp_hf_h1_01/protocol.md`。细则：`exp_hf_h1_01/human_protocols/`。

H 轴与 F 轴分开。本实验不报功能 FullPass，不进入排名。`h1_formal_score: N/A`。

### 第一版问什么

> 在机制**正常工作**的情况下，GAWorld 的团队互动过程是否像真人？

因此只用完整工作流：T3 Full Multi、I1 Full、L1 Full Multi。不用 Single / Drop / NoVerify。否则评委会把「通道被人为破坏」打成「不像人」。**C1 不进第一版。**

### 刺激怎么抽

```text
3 类任务 × 2 变体 × 3 条 Agent 轨迹 = 18（已完成）
3 类任务 × 2 变体 × 3 条 Human 轨迹 = 18（0/18，尚未采集）
合计规划 36
```

Agent 来源：`HO-GM-T3-01` / `HO-GM-I1-01` / `HO-GM-L1-01` 的 seed0 Full 轨，按 **task × variant** 机械抽取 `repeat_index=0`。禁止挑满分、挑好看的、或按 FullPass 筛选。登记：`output/exp_hf_h1_01_20260825/STIMULUS_REGISTRY.yaml`。

```yaml
functional_role: sealed_holdout_result
H1_role: development_stimulus
not_future_h1_holdout: true
manual_best_case_selection: false
```

这些 Full 轨可作 H1 **开发刺激**，不能冒充未来 H1 密封留出。正式 H1 泛化要另备未参与 Rubric / 网页修改的新刺激。

| 构念 | 轨道 | 来源 | Agent 条数 | Human |
|---|---|---|---:|---|
| T3 | Full Multi | HO-GM-T3-01 seed0 | 6 | 0/6 |
| I1 | Full | HO-GM-I1-01 seed0 | 6 | 0/6 |
| L1 | Full Multi | HO-GM-L1-01 seed0 | 6 | 0/6 |

18 个槽位（变体对外只标 A/B；评委看不到 FullPass）：

| stimulus_id | 构念 | 任务 | 变体 |
|---|---|---|---|
| h1dev-t3-queue-control | T3 | t3_ho_queue_max_001 | A |
| h1dev-t3-queue-intervention | T3 | t3_ho_queue_max_001 | B |
| h1dev-t3-battery-control | T3 | t3_ho_battery_pct_001 | A |
| h1dev-t3-battery-intervention | T3 | t3_ho_battery_pct_001 | B |
| h1dev-t3-noise-control | T3 | t3_ho_noise_db_001 | A |
| h1dev-t3-noise-intervention | T3 | t3_ho_noise_db_001 | B |
| h1dev-i1-pier-control / -intervention | I1 | holdout I1 码头 | A / B |
| h1dev-i1-pump-control / -intervention | I1 | holdout I1 泵 | A / B |
| h1dev-i1-library-control / -intervention | I1 | holdout I1 馆藏 | A / B |
| h1dev-l1-crane-control / -intervention | L1 | holdout L1 吊机 | A / B |
| h1dev-l1-fridge-control / -intervention | L1 | holdout L1 冷柜 | A / B |
| h1dev-l1-mail-control / -intervention | L1 | holdout L1 邮件 | A / B |

### 现在该采什么（不是盲评分）

当前缺的是 **18 条 Human Trace**：真人按岗位提交与 Agent **同一动作空间**的结构化动作，槽位与上表一一对应。

- **是**：打开 `/human.html`，扮演该槽位要求的角色，提交 JSON / 代码动作，保存轨迹。
- **不是**：给 12 项 Rubric 打分（那是后面盲评）。
- **不是**：再跑一遍 GLM，或让模型「扮演人类」。
- **不是**：把 Agent 的满分轨迹当人类答案交上去。

一人可以分饰三角色（起草人 / 审核员 / 执行人等），但必须按协议的信息隔离来：该角色看不到的私有标准、可信表、正确答案，被试也看不到。

### 绝对不能告诉被试的

- Agent 轨迹、模型名、`GLM-4-Flash`、实验号（`HO-GM-*` / `EXP-HF-H1-01`）
- FullPass、Oracle 正确答案、私有 v2 标准（除非该角色协议允许看见）
- 这是「对照题」还是「干预题」、哪条是 control / intervention（只说变体 A/B 的公开说明）
- 评分 Rubric 的期望答案；不要说「你要表现得像人」或「系统想测拟人化」

### 三套岗位（完整工作流，无 Drop）

**T3**（`human_protocols/t3.md`）：起草人按公开说明写草稿（看不到本轮私有核验标准）→ 审核员对照本轮可见标准 keep / update（不改文件）→ 执行人只按审核意见确认或改草稿。变体 A：公开标准与私有标准一致，通常 keep。变体 B：私有标准已更新，审核员看得到新值，起草人起草时看不到。

**I1**（`human_protocols/i1.md`）：观察员把两个来源报告原样发出（不判断谁可信）→ 核验员按私有可信表选出可信来源状态（不提交最终动作）→ 调度员只根据已核实消息按规则提交动作（不读可信表）。禁止调度员越权读表。

**L1**（`human_protocols/l1.md`）：执行者甲完成第一步并提交检查点（不填版本号，平台盖章）→ 协调员指定接替者与恢复步骤（不能执行具体步骤，不能给出剩余步骤的正确答案）→ 变体 B 时甲离岗，执行者乙从检查点继续后两步（不重复第一步）。变体 A：甲完成第一步后仍在岗，自己继续。

### 12 项 Rubric（1–7，采集之后才用）

锚点：1 = 完全不像真人团队互动，7 = 完全像真人团队互动。**四维分别取均值，不合成一个总分，不与 FullPass 混合。** 评委只看到角色、可见信息、结构化动作和时间顺序；不显示模型名、实验号、FullPass、Human/Agent 标签。

| ID | 维 | 问什么 |
|---|---|---|
| H1-01 | 自然性 | 节奏是否像真人一起干活，而不是机械复读或突然跳步？ |
| H1-02 | 自然性 | 表达是否像在完成手头工作，而不是在表演对话？ |
| H1-03 | 自然性 | 遇到差异或中断时，处理是否具体、克制？ |
| H1-04 | Agency | 是否主动负起自己的职责，而不是空转等待？ |
| H1-05 | Agency | 决定是否有可见依据，而不是无故改口？ |
| H1-06 | Agency | 是否分得清自己能做的事和必须交给别人的事？ |
| H1-07 | 社会回应性 | 后手是否读取并回应了上手交付的内容？ |
| H1-08 | 社会回应性 | 反对或修改时是否针对具体差异，而不是空泛否定？ |
| H1-09 | 社会回应性 | 中断或新信息时，回应是否对准当前状态？ |
| H1-10 | 角色连续性 | 是否始终按自己的岗位行动，没有越权？ |
| H1-11 | 角色连续性 | 接替或审核之后是否延续已完成工作，而不是推倒重来？ |
| H1-12 | 角色连续性 | 整段过程中角色身份是否保持稳定？ |

差距：每维 3 项均值(Human) − 该维 3 项均值(Agent)。正值只表示真人该维更高，**不表示能力更好**。Human 未采集前全部 N/A。

### 实验室

```bash
export PYTHONPATH=/path/to/gaworld_eval_bridge:/path/to/GAWorld
python -m exp_hf_h1_01.serve
# http://127.0.0.1:8765
# /human.html 采集真人 Trace
# /viewer.html 匿名轨迹（评委用）
# /rater.html 盲评（现在还不要用）
```

### 已完成 / 未开始

已完成：抽样冻结、18 条匿名 Agent 轨迹、三套真人协议、统一渲染、12 项 Rubric、真人执行页、盲评页。

未开始：真人采集、认知访谈 5–8 人、内部 Pilot 15–20、冻结排除规则、约 60 人独立盲评、四维差距。

### 顺序（不要跳）

```text
冻结抽样规则          ← 已做
→ 真人任务协议         ← 已做
→ 真人执行网页保存 Human Trace   ← 当前步骤（0/18）
→ 统一匿名展示
→ 12 项 Rubric         ← 已写，尚未打分
→ 5–8 人认知访谈
→ 15–20 人内部 Pilot
→ 冻结刺激、Rubric、排除规则和分析方案
→ 约 60 名独立盲评
→ 自然性 / Agency / 社会回应性 / 角色连续性差距
```

---

## 仍开放的系统问题

| ID | 状态 | 含义 |
|---|---|---|
| AP-C1-D-01 | open | NACK 后未形成正确终局；拒绝后不调整联合方案 |
| AP-C1-F-01 | open | 模型不应管 plan_version；C1 通道未迁到平台盖章 |
| AP-REL1-01 | open | `latest_is_binding=true` 仍按旧多数行动 |
| typed_patch / AP-04e-E-01 | retired | 不作为正式接口 |

这些不阻碍报告「功能评测已落到可解释状态」，但阻碍说「产品已经改好」。

C1 版本通道迁移 = 独立 Backlog，不阻塞 H1 第一版。

---

## 两个仓库怎么对齐

评测战役跨两个 Git 仓库，不要打成一个大包。

| 仓库 | 远程 | 分支 | 这一阶段提交了什么 |
|---|---|---|---|
| 评测桥（本仓库） | `https://github.com/huohua51/gaworld_eval_bridge` | `main` | 实验定义、Oracle、Scorer、Registry、冻结 REPORT/GATE、开发集总表、三包留出、H1 实验室、本 README 总账 |
| 仿真平台 | 上游 `https://github.com/wuchaozju/GAWorld` | 本地 `eval-harness` | `PlanRegistry`、`JointAssignmentChannel`、检查点/接替通道、`tests/test_joint_assignment.py` |

**不要**把评测改动直接推到上游 `wuchaozju/GAWorld` 的 `main`。应 Fork 到 `huohua51/GAWorld` 再推 `eval-harness`。本机若还没有这个 Fork，先在 GitHub 上 Fork，然后：

```bash
cd /path/to/GAWorld
git remote add fork https://github.com/huohua51/GAWorld.git   # 已有则跳过
git push -u fork eval-harness
```

平台盖章接口已经在 `eval-harness` 落地，但 **C1 评测通道尚未切换**，所以 AP-C1-F-01 仍开放。历史 C1 分数不因这次平台提交而重算。

协作者环境：

```text
PYTHONPATH=/path/to/gaworld_eval_bridge:/path/to/GAWorld
```

仿真侧需要 `eval_mode`。Key 只放在 `GAWorld/.env`，不要入库。

---

## 环境与复现

### 不要上传

- `GAWorld/.env`（API Key）
- `AgentSociety/`、`YuLan-OneSim/`
- 根目录汇报 ppt/pdf（可选）

请只提交 `.env.example`，本地复制为 `.env`。

### 环境

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r ../GAWorld/requirements.txt
pip install pytest pyyaml

cp ../GAWorld/.env.example ../GAWorld/.env   # 填入自己的 LLM key
export PYTHONPATH=/path/to/gaworld_eval_bridge:/path/to/GAWorld
cd /path/to/gaworld_eval_bridge
```

评测必须开 `eval_mode`。不要重跑已冻结实验来「刷分」。留出包禁止 `--phase repeats`。

### 抽样/测量单测（不调用 LLM）

```bash
PYTHONPATH=.:../GAWorld python -m pytest v0_first_batch/tests/test_first_batch.py exp_hf_h1_01/test_sampling.py -q
PYTHONPATH=../GAWorld python -m unittest tests.test_joint_assignment   # 在 GAWorld 目录
```

---

## 目录索引

| 路径 | 作用 |
|---|---|
| `registry.yaml` | 正式实验登记 |
| `backlog/agent_protocol.yaml` | Agent 协议问题，不是平台修 bug 清单 |
| `output/functional_devset_20260825/` | 功能侧开发集总表（分数冻结） |
| `output/holdout_20260825/` | 三包留出 seed0 汇总 |
| `output/exp_hf_h1_01_20260825/` | H1 刺激登记与冻结 |
| `exp_gm_04*` / `exp_i1` / `exp_rel1` | 早期冻结实验 |
| `exp_gm_t3_0{1,2,3}` / `cal_gm_change_01` / `cal_gm_apply_01` | T3 族 |
| `exp_gm_c1_0{1,2,3}` / `cal_gm_c1_*` | C1 族 |
| `exp_gm_l1_01*` / `cal_gm_l1_resume_01` | L1 族 |
| `exp_gm_n1` | 已退役 |
| `holdout_t3` / `holdout_i1` / `holdout_l1` | 密封留出包 |
| `exp_hf_h1_01` | H1 实验室（`human_protocols/`、`rubric.yaml`、`web/`） |
| `v0_first_batch/` | 评分合成；`cover_first_error` |
| `output/` | 报告与格子证据；改代码前先读对应 REPORT |

改任何冻结实验的题目、Scorer 或提示前，先确认 `FREEZE.yaml` 的 `do_not_edit_after_freeze`。历史分数以当时 GATE 为准，用勘误补充诊断，不重算。
