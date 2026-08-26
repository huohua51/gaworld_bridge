# **GAWorld Evaluation Bridge**

`gaworld_eval_bridge` 是 GAWorld 的外部评测仓库。GAWorld 继续负责世界状态、角色权限、通信通道和模型调用；本仓库负责把社会能力问题变成可运行任务，组织对照实验，保存证据，执行规则评分，并维护冻结结果。

```
projects/
├─ GAWorld/                 世界、通道、权限、状态与 LLM 路由
└─ gaworld_eval_bridge/     Task Card、Oracle、协议、Scorer、Registry、报告与 H1 实验室
```

当前功能实验固定使用：

```
model_provider: paratera_glm
model: GLM-4-Flash
temperature: 0
eval_mode: true
```

固定模型的目的，是让主要变化集中在 GAWorld 平台机制与 Agent 协作协议上。当前结果用于机制诊断；正式跨模型排行榜将在任务、留出和排名资格门全部冻结后另行开展。

格子级结果以各实验目录中的 `REPORT.md`、`GATE.yaml` 和 `cell_result.json` 为准；`registry.yaml` 保存冻结后的实验登记。

---

## **目录**

1. [评测框架的整体逻辑](#1-%E8%AF%84%E6%B5%8B%E6%A1%86%E6%9E%B6%E7%9A%84%E6%95%B4%E4%BD%93%E9%80%BB%E8%BE%91)
2. [一次实验从问题到结论](#2-%E4%B8%80%E6%AC%A1%E5%AE%9E%E9%AA%8C%E4%BB%8E%E9%97%AE%E9%A2%98%E5%88%B0%E7%BB%93%E8%AE%BA)
3. [一格实验如何定义](#3-%E4%B8%80%E6%A0%BC%E5%AE%9E%E9%AA%8C%E5%A6%82%E4%BD%95%E5%AE%9A%E4%B9%89)
4. [R0–R3：先确认测到了什么](#4-r0r3%E5%85%88%E7%A1%AE%E8%AE%A4%E6%B5%8B%E5%88%B0%E4%BA%86%E4%BB%80%E4%B9%88)
5. [F1–F5：从同一批格子回答五个功能问题](#5-f1f5%E4%BB%8E%E5%90%8C%E4%B8%80%E6%89%B9%E6%A0%BC%E5%AD%90%E5%9B%9E%E7%AD%94%E4%BA%94%E4%B8%AA%E5%8A%9F%E8%83%BD%E9%97%AE%E9%A2%98)
6. [如何增加一道新题](#6-%E5%A6%82%E4%BD%95%E5%A2%9E%E5%8A%A0%E4%B8%80%E9%81%93%E6%96%B0%E9%A2%98)
7. [代码模块如何协作](#7-%E4%BB%A3%E7%A0%81%E6%A8%A1%E5%9D%97%E5%A6%82%E4%BD%95%E5%8D%8F%E4%BD%9C)
8. [T3一格真实工作流示例](#8-t3%E4%B8%80%E6%A0%BC%E7%9C%9F%E5%AE%9E%E5%B7%A5%E4%BD%9C%E6%B5%81%E7%A4%BA%E4%BE%8B)
9. [当前功能侧结果](#9-%E5%BD%93%E5%89%8D%E5%8A%9F%E8%83%BD%E4%BE%A7%E7%BB%93%E6%9E%9C)
10. [各任务族的证据与结论](#10-%E5%90%84%E4%BB%BB%E5%8A%A1%E6%97%8F%E7%9A%84%E8%AF%81%E6%8D%AE%E4%B8%8E%E7%BB%93%E8%AE%BA)
11. [密封留出](#11-%E5%AF%86%E5%B0%81%E7%95%99%E5%87%BA)
12. [H1人类效度](#12-h1%E4%BA%BA%E7%B1%BB%E6%95%88%E5%BA%A6)
13. [开放问题与下一阶段](#13-%E5%BC%80%E6%94%BE%E9%97%AE%E9%A2%98%E4%B8%8E%E4%B8%8B%E4%B8%80%E9%98%B6%E6%AE%B5)
14. [证据等级与对外表述](#14-%E8%AF%81%E6%8D%AE%E7%AD%89%E7%BA%A7%E4%B8%8E%E5%AF%B9%E5%A4%96%E8%A1%A8%E8%BF%B0)
15. [两个仓库如何协作](#15-%E4%B8%A4%E4%B8%AA%E4%BB%93%E5%BA%93%E5%A6%82%E4%BD%95%E5%8D%8F%E4%BD%9C)
16. [环境与复现](#16-%E7%8E%AF%E5%A2%83%E4%B8%8E%E5%A4%8D%E7%8E%B0)
17. [目录索引](#17-%E7%9B%AE%E5%BD%95%E7%B4%A2%E5%BC%95)

---

## **1. 评测框架的整体逻辑**

这套框架的目标不止是得到成功率，还要把多智能体社会中的问题定位到可以修改的模块。每项实验都沿着同一条链运行：

```
提出一个可修改的社会机制问题
        ↓
写成 Task Card 与唯一干预
        ↓
将完成条件拆成 Rubric
        ↓
把 Rubric 翻译成 Scorer Spec
        ↓
Rule / Direct 校准题目与测量台
        ↓
运行 Single / Full Multi / Drop 等对照轨
        ↓
R0–R3 判定测量、产物、结果与过程
        ↓
聚合 F1–F5、StrictPair 与 first_error
        ↓
组件校准、协议修改和完整回归
        ↓
密封留出复测
```

### **1.1 四类对象分别处在什么位置**


| **类别** | **本仓库中的表示**               | **解决的问题**       | **彼此关系**                                  |
| ------ | ------------------------- | --------------- | ----------------------------------------- |
| 评价目标   | 功能轴 F1–F5；人类效度轴 H1–H7     | 最后要回答哪类科学问题     | 两条轴共享 Trace，分别使用 Oracle 与 Human Reference |
| 任务族    | T3、I1、L1、C1、REL1 等        | 用什么社会任务承载问题     | 各任务族并列接入同一评测工厂                            |
| 机制开关   | 通信、核验、权限、审核、检查点、协调、Drop 等 | 本次实验改变哪条平台边     | 形成 Single、Full、Drop、NoVerify 等对照条件        |
| 证据门    | R0–R3                     | 当前格子的证据是否足以支持解释 | 按 R0→R1/R2→R3 的顺序检查                       |


T3、I1、L1是任务族；F1、F2、F3是对任务结果的不同观察角度。二者属于不同层级。H轴也使用轨迹，但它根据真人参照评价人类效度，单独形成结果。

### **1.2 四个核心工具**


| **工具**          | **作用**           | **主要内容**                                     |
| --------------- | ---------------- | -------------------------------------------- |
| Task Card       | 把抽象问题变成一道明确任务    | 角色、信息、权限、起止窗口、目标、Oracle、control/intervention |
| Rubric          | 把“完成”拆成可核验条件     | R0测量、R1产物、R2结果、R3过程                          |
| Scorer Spec     | 把Rubric条件翻译成程序规则 | 字段路径、比较方式、阈值、缺失处理、输出格式                       |
| Evidence Bundle | 保存本次运行实际发生的事情    | 配置、Prompt、动作、消息、状态、产物、权限事件和环境记录              |


它们按照下面的关系工作：

```
Task Card 定义任务事实
        ↓
Rubric 选择需要核验的事实
        ↓
Scorer Spec 规定如何读取和比较证据
        ↓
Evidence Bundle 提供真实运行证据
```

---

## **2. 一次实验从问题到结论**

### **2.1 从可修改的问题出发**

合格的问题需要同时包含行为、可能原因和改进接口。例如：

> 当最新标准只掌握在Reviewer手里时，团队能否通过审核消息更新Executor的产物？失败发生在Reviewer判断、消息交付还是Executor采用？

这个问题可以对应三类改进：

- Reviewer证据绑定协议；
- 审核消息的投递与完整性；
- Executor对审核意见的采用方式。

### **2.2 把问题变成Task Card**

Task Card至少登记：

- 参与角色与角色职责；
- 每个角色可见的公开信息和私有信息；
- 每个角色可以调用的工具与动作；
- workflow开始事件与结束条件；
- control和intervention之间唯一变化的字段；
- 正确动作、最终状态或隐藏产物Oracle；
- Drop、NoVerify、Single等必要对照；
- 调用预算、模型配置和重复策略。

### **2.3 先做Rule与Direct校准**

Rule角色使用确定性函数产生标准动作。它确认任务、平台通道和Scorer能够形成预期的成功与失败模式。

Direct把必要状态直接交给决策角色，用来确认固定模型具备完成这道题的基础能力。Direct通过后，Full Multi与Drop之间的差异才具有清晰含义。

### **2.4 运行完整矩阵**

典型开发矩阵为：

```
3道题 × 2个变体 × 3条轨 × 3次重复 = 54格
```

seed0通常先运行18格。预注册门通过后再补repeat 1/2；共同地板、共同天花板或测量门异常会触发停止条件。

### **2.5 用首错进入改进闭环**

完整流程失败后，`first_error`把问题定位到最早出现证据的节点。随后通过组件校准区分：

- 单个角色本身的判断能力；
- 消息格式与接口兼容性；
- 通道交付与权限；
- 完整工作流中的上下文传播；
- 环境自动修复或其他脚手架影响。

协议修改采用新实验编号和新任务复测。开发题保留历史结果，新任务承担修复后的完整回归。

---

## **3. 一格实验如何定义**

每个`instance_id`至少由四个坐标组成：


| **字段**      | **示例**                                 | **含义**        |
| ----------- | -------------------------------------- | ------------- |
| `task_id`   | `t3_alert_celsius_001`                 | 当前表面任务        |
| `variant`   | `control` / `intervention`             | 唯一登记条件的两个取值   |
| `track`     | `direct` / `single` / `multi` / `drop` | 当前启用的工作流与机制开关 |
| `repeat_id` | `0` / `1` / `2`                        | 重复运行编号        |


### **3.1 常用实验轨**


| **轨道**       | **回答的问题**                             | **在结论中的角色** |
| ------------ | ------------------------------------- | ----------- |
| Rule         | 正确行为能否通过平台并被Scorer识别                  | 题目与测量台正控    |
| Direct       | 角色直接获得必要状态时，题目是否可做                    | 可做性门        |
| Single       | 同一Agent自检或独立完成时的表现                    | Multi对照     |
| Full / Multi | 完整多角色工作流的表现                           | 主要系统结果      |
| Drop         | 上游角色继续运行，指定消息在交付处被切断                  | 因果负控        |
| NoVerify     | 原始信息继续传播，核验环节被省略                      | I1核验机制负控    |
| Component    | 只运行Reviewer、Executor、Coordinator等单一组件 | 首错定位与校准     |


轨道均值需要拆回control和intervention解释。例如Drop FullPass=0.5通常表示control=1、intervention=0，含义是指定机制对干预格具有必要作用。

### **3.2 公平性约束**

同一`task × variant × repeat`的Single、Multi与Drop复用相同初稿哈希，并保持相同模型、temperature和调用预算。这样可以把轨道差异归因到协作机制，而不是初稿难度或资源差异。

---

## **4. R0–R3：先确认测到了什么**

统一实现位于`v0_first_batch/schema.py::compose()`。评分器使用规则和隐藏Oracle，一格运行完成后无需再次调用大模型评分。


| **层级**   | **核心问题**                | **典型检查**                                   | **结果用途**                      |
| -------- | ----------------------- | ------------------------------------------ | ----------------------------- |
| R0 测量有效性 | 当前运行是否提供了完整、可解释的证据      | 调用预算、字段提取、Oracle隔离、eval_mode、Drop隔离、共享初稿哈希 | 决定该格能否进入能力解释                  |
| R1 产物与来源 | 必需动作、事件、文件和状态是否存在且来源合规  | 最终文件、生产者身份、ACL拒绝、环境写入                      | 排除空交、越权或环境代做                  |
| R2 目标结果  | 动作、数值、约束和最终状态是否符合Oracle | 隐藏pytest、字段比较、状态重放                         | 生成TargetCorrect与任务结果          |
| R3 互动过程  | 信息是否发送、送达、核验、采用并形成闭环    | payload哈希、消息链、步骤事件、交接状态                    | 生成Process Profile与first_error |


`compose()`遵循以下合成逻辑：

```
R0关键门通过
    ↓
检查R1产物来源
    ↓
检查R2目标结果
    ↓
检查R3必要过程
    ↓
形成FullPass与first_error
```

R0异常的格子登记为`measurement_invalid`，与能力结果分开保存。R1–R3任一临界条件偏离时，FullPass为0，并记录最早可证实的失败节点。未来运行若暂时缺少更具体的枚举，`cover_first_error()`会写入`unexplained_failure`，为人工复核保留入口。

历史冻结JSON保持原值；解释修订通过`ERRATUM.yaml`登记。

---

## **5. F1–F5：从同一批格子回答五个功能问题**

F1–F5是同一格矩阵的五种分析视角，各自保留独立含义。


| **维度**    | **核心问题**                          | **计算方式**                                   |
| --------- | --------------------------------- | ------------------------------------------ |
| F1 任务完成   | 完整多智能体流程是否做成任务                    | Full/Multi轨的FullPass均值                     |
| F2 条件适应   | control条件变成intervention后，系统是否相应调整 | StrictPair                                 |
| F3 协作闭环   | 信息、权限、核验、采用和交接是否闭环                | Process Profile、payload完整性、ACL和first_error |
| F4 流程传播   | 局部可做性进入完整流程后是否保持                  | Direct、Full、Drop的配对比较                      |
| F5 多智能体价值 | 独立角色与私有信息是否带来额外结果                 | 等预算下Multi−Single，并结合Drop验证价值来源             |


### **5.1 FullPass**

FullPass要求目标结果正确、必要事件链成立、产物来源合法，并且环境记录中没有代做关键业务动作。

### **5.2 StrictPair**

`_strict_pair()`按`task_id × track × repeat`配对control与intervention。两格同时通过，说明系统能够随着登记条件变化而更新行为。

### **5.3 Multi−Single**

`paired_mean(multi, single)`比较同任务、同变体、同repeat和同预算下的两条轨。共同地板或共同天花板会使差值失去区分能力，此时`GATE.yaml`将其登记为`N/A`。

### **5.4 first_error**

首错沿真实事件链寻找最早的偏离。例如审核payload在交付处被切断，后续终稿错误会归因到`review_payload_not_delivered`，从而把改进目标定位到消息边。

### **5.5 T3-03如何同时回答五个问题**

```
                control             intervention
Single          通过                失败：缺少私有v2
Multi           通过                通过：审核闭环成立
Drop            通过                失败：审核消息未交付
```

由此可以同时读取：

- F1：Multi完成任务；
- F2：Multi的control/intervention成对通过；
- F3：审核判断、payload完整性与Executor采用形成闭环；
- F4：Drop把优势定位到审核消息边；
- F5：开发集上Multi相对Single产生0.5的结果增益。

---

## **6. 如何增加一道新题**

下面以`exp_gm_t3_03/`为模板。I1、L1和其他任务族沿用相同顺序，替换通道、角色动作和Oracle。

### **B1. 明确构念与改进接口**

在`task_card.yaml`和`protocol.md`中写清：

- 想发现哪一种社会失败；
- 改善后可以修改哪个平台模块或Agent协议；
- 哪个角色拥有私有信息；
- control与intervention唯一改变什么；
- 什么结果由Oracle判定；
- 哪条边用于Drop或NoVerify。

### **B2. 编写表面任务**

在`tasks/<id>.yaml`中提供公开规则与v1条件。intervention的v2值、可信表或私有约束仅进入对应角色的私有上下文。

### **B3. 编写隐藏Oracle**

```
oracle/test_*_v1.py
oracle/test_*_v2.py
```

隐藏Oracle由Scorer读取，角色提示中只出现完成任务所需的公开说明。

### **B4. 编写提示与动作契约**

`prompts.py`按照角色和轨道组织可见信息；动作契约定义JSON字段、枚举和数值类型。结构化契约让格式错误、业务错误和测量错误能够分别登记。

### **B5. 编写工作流**

`loop.py`调用GAWorld通道。Drop在`deliver(drop=True)`处切断指定消息；ACL和私有读取路径保留显式审计记录。

### **B6. 编写规则评分器**

`scorer.py`读取最终文件、通道痕迹、权限事件与隐藏Oracle，再调用`compose()`生成统一格子结果。

### **B7. Rule正负控**

```
python -m exp_gm_t3_03.run_matrix --phase rule
```

Rule control/intervention应形成Task Card登记的正确结果；Drop、越权、错值和捷径形成预期失败。

### **B8. 冻结版本**

`freeze.py`对Task Card、任务、Oracle、协议、Scorer和Runner计算SHA-256，并写入：

```
output/<experiment>_<date>/FREEZE.yaml
```

冻结后，开发修订通过新实验编号和新任务实现。

### **B9. Direct可做性**

```
python -m exp_gm_t3_03.run_matrix --phase direct
```

3题×2变体形成6格。Coverage和Direct门达到预注册条件后，进入多轨矩阵。

### **B10. seed0矩阵**

```
python -m exp_gm_t3_03.run_matrix --phase seed0
```

典型规模为3题×2变体×3轨×repeat0，共18格。输出包括：

```
runs/<instance_id>/cell_result.json
runs/<instance_id>/prompts/
runs/<instance_id>/trace/
REPORT.md
GATE.yaml
cell_table.json
```

### **B11. 读取预注册门**

检查Coverage、调用预算、初稿公平、Drop隔离、共同地板与共同天花板。具备区分度后补repeat 1/2；稳定首错进入组件校准与修复流程。

### **B12. 回归与留出**

组件修复使用新实例校准；完整工作流回归使用另一组新任务；密封留出在冻结后一次性运行。三类数据分别承担诊断、修复验证和初步外推。

### **6.1 新增T3题最少涉及的文件**

```
exp_gm_<family>/tasks/<new_id>.yaml
exp_gm_<family>/oracle/test_*_v1.py
exp_gm_<family>/oracle/test_*_v2.py
exp_gm_<family>/loader.py
registry.yaml
```

### **6.2 常用入口**

```
python -m exp_gm_t3_03.run_matrix --phase rule
python -m exp_gm_t3_03.run_matrix --phase direct
python -m exp_gm_t3_03.run_matrix --phase seed0

python -m exp_i1.run_exp_i1
python -m exp_gm_l1_01c.run_matrix
```

---

## **7. 代码模块如何协作**

### **7.1 总体调用图**

```
registry.yaml
        │  登记实验身份、父实验、状态与证据等级
        ▼
run_matrix.py / run_exp_*.py
        │  固定模型、开启eval_mode、展开task×variant×track×repeat
        │
        ├─ freeze.py
        │     计算冻结哈希并生成FREEZE.yaml
        │
        ├─ loader.py
        │     读取YAML任务并绑定Oracle路径
        │
        ├─ prompts.py / contract.py
        │     组织角色可见信息与结构化动作
        │
        ├─ loop.py
        │     运行一格真实工作流
        │     │
        │     ├─ GAWorld通道
        │     │     ReviewChannel              T3审核
        │     │     RelayChannel               I1核实
        │     │     WorkflowCheckpointChannel  L1检查点与接替
        │     │     JointAssignmentChannel     C1目标通道，评测迁移待完成
        │     │
        │     └─ LLMRouter
        │           生成草稿、审核、动作和执行结果
        │
        ├─ Evidence Bundle
        │     保存Prompt、Trace、消息、权限、产物、哈希与环境记录
        │
        ├─ scorer.py
        │     读取证据与隐藏Oracle
        │     └─ compose()
        │           统一生成FullPass、first_error与Process Profile
        │
        └─ aggregate.py
              汇总Coverage、StrictPair、轨道差值、GATE和REPORT
                      ↓
                 registry.yaml
```

### **7.2 三条职责边界**

1. **LLM负责行为生成**：草稿、审核意见、业务动作和最终产物。
2. **GAWorld负责机制执行**：消息保存与传递、权限、检查点、状态更新和版本盖章。
3. **Scorer负责独立判定**：根据冻结Oracle读取真实证据并计算结果。

### **7.3 仿真侧模块**


| **模块**                      | **路径**                          | **评测用途**                             |
| --------------------------- | ------------------------------- | ------------------------------------ |
| `eval_mode`                 | `gaworld/eval_mode.py`          | 固定评测环境，关闭动态改写和日记兜底，记录运行配置            |
| `CONFIG` + `LLMRouter`      | `config.py`、`llm_providers.py`  | 统一模型、temperature和供应商配置               |
| `ReviewChannel`             | `gaworld/work/review.py`        | 保存Reviewer私有标准、审核写入权限与产物ACL          |
| `IntegrityMailbox`          | `exp_gm_t3_02/integrity.py`     | 维护审核payload哈希链并实现T3 Drop             |
| `RelayChannel`              | `gaworld/comm/relay.py`         | 区分原始报告与核实消息，保护私有可信表                  |
| `WorkflowCheckpointChannel` | `gaworld/work/continuity.py`    | 记录步骤、生成检查点、传递接替与续做位置                 |
| `JointAssignmentChannel`    | GAWorld联合分配通道                   | 保存联合方案、检查权限并连接平台版本管理；C1迁移待完成         |
| `PlanRegistry`              | `gaworld/work/plan_registry.py` | 生成`plan_id`与`spec_version`，让模型聚焦业务分配 |


`v0_first_batch/paths.py`把GAWorld与评测桥加入`sys.path`。入口通过`os.chdir(GAWORLD_ROOT)`切换到仿真仓库，使LLM配置与`.env`沿用GAWorld设置。

标准城市`run`使用日常模拟配置；功能格显式开启`eval_mode`，实例化当前任务需要的通道并调用LLM，从而精确控制角色信息、干预字段和调用预算。

---

## **8. T3一格真实工作流示例**

T3测试：新标准只掌握在Reviewer手里时，审核信息能否到达Executor并落实到真实文件。

### **8.1 加载任务**

`load_tasks()`读取YAML并挂载v1/v2 Oracle路径。control使用v1标准；intervention在Reviewer私有上下文中使用v2标准。

### **8.2 生成共享初稿**

`generate_shared_draft()`只使用公开v1简报生成`artifact_before.py`并计算SHA-256。同一任务和变体的三条轨复用该初稿。

### **8.3 运行角色链**

`run_track_from_draft()`依次完成：

1. `ReviewChannel.put_private()`写入Reviewer本轮标准；
2. Reviewer读取草稿和授权标准，提交结构化审核结果；
3. `IntegrityMailbox.emit()`保存payload及哈希；
4. `deliver()`向Executor交付消息，Drop轨在这里形成断边；
5. Executor读取草稿和inbox，生成`artifact_after.py`；
6. 评测桥使用非授权角色尝试写产物，记录ACL拒绝；
7. Scorer检查文件、消息链、权限和Oracle。

### **8.4 评分条件**

`exp_gm_t3_03/scorer.py`检查：

- control产物通过v1隐藏测试，intervention产物通过v2隐藏测试；
- 登记符号与Oracle匹配；
- 修改范围与审核意见一致；
- Reviewer判断相对当前草稿具有真实证据；
- Multi中Reviewer、Channel和Executor三段payload哈希一致；
- Drop干预的inbox为空，并记录`review_payload_not_delivered`；
- 文件来源与ACL符合Task Card；
- 环境记录中没有业务答案写入。

这些条件共同形成`oracle_conditioned_success`，随后由`compose()`生成FullPass与first_error。

---

## **9. 当前功能侧结果**

冻结基准日：2026-08-25。


| **任务族**    | **开发状态**       | **代表实验**      | **当前结论**                   | **留出状态** |
| ---------- | -------------- | ------------- | -------------------------- | -------- |
| T3 审核协作    | `pass`         | T3-03         | 独立Reviewer私有信息通过审核通道进入真实产物 | seed0同模式 |
| I1 核实传播    | `pass`         | EXP-GM-I1     | 核实、送达、采用形成完整因果链            | seed0同模式 |
| L1 中断恢复    | `pass`         | L1-01c        | 检查点、续做位置和角色接替形成闭环          | seed0同模式 |
| C1 集体协调    | `partial_pass` | C1-02 / C1-03 | 基础冲突消解成立，优先级NACK重试为开放问题    | 下一阶段     |
| REL1 可靠性更新 | `fail`         | EXP-GM-REL1   | 平台状态传播成立，Agent最新状态采用失败     | 下一阶段     |
| N1 一般信息更新  | `retired`      | EXP-GM-N1     | 构念由I1与REL1分别承接             | 历史结果冻结   |


当前开发状态可以概括为：

```
functional_development: largely_complete
functional_holdout: seed0_pattern_replication
ranking_eligible: false
formal_benchmark: next_stage

h1_infrastructure: ready
h1_agent_stimuli: 18/18
h1_human_reference: 0/18
h1_formal_score: N/A
```

这里的“约85%”表示评测工厂和代表机制覆盖进度：R0–R3、因果对照、权限审计、Trace、首错、组件校准、完整回归均已落地，T3/I1/L1也进入密封留出阶段。正式Benchmark还需要跨任务留出、更多重复、跨模型稳健性与H1真人对照。

---

## **10. 各任务族的证据与结论**

### **10.1 早期工作流与评测工厂**


| **实验**                | **作用**                             | **结论**                                   |
| --------------------- | ---------------------------------- | ---------------------------------------- |
| `v0_first_batch`      | 建立R0–R3、FullPass与统一Evidence Bundle | 测量门先于能力解释                                |
| GM-01 / GM-02 / GM-05 | 早期任务与难度校准                          | 历史结果冻结，承担开发证据                            |
| 04a                   | 基础工作队列正控                           | 静态微任务中管线能够保存产物                           |
| 04b                   | 需求版本传播                             | 执行前能够读取并采用最新需求                           |
| 04c                   | Reviewer–Executor闭环                | 通道与权限有效，角色协议出现可定位缺口                      |
| 04e-R                 | Reviewer证据绑定                       | FalsePositiveRevisionRate降至0，Grounding=1 |
| 04e-E                 | typed patch执行                      | 声明采用与真实采用分离，typed patch接口退役              |
| OA-01 / OA-02         | 过度适应诊断                             | OA-02协议校准通过，泛化留待后续                       |


### **10.2 T3：审核协作**

T3经历了完整的诊断与修复链：

```
T3-01完整流程共同地板
        ↓
CHANGE-01：判断该不该改，通过
APPLY-01：正确意见能否落实，通过
        ↓
T3-02：组件接口重新接通，Single/Multi均到天花板
        ↓
T3-03：Reviewer私有信息形成区分度
```

T3-03开发集54格：


| **轨道** | **FullPass** | **变体拆分**                 | **稳定首错**                       |
| ------ | ------------ | ------------------------ | ------------------------------ |
| Multi  | 1.0          | control=1，intervention=1 | none                           |
| Single | 0.5          | control=1，intervention=0 | `review_decision_incorrect`    |
| Drop   | 0.5          | control=1，intervention=0 | `review_payload_not_delivered` |


开发集结论：独立Reviewer的私有信息产生可识别价值；消息交付被切断后，该优势随之消失。

### **10.3 I1：核实信息传播**

I1使用`Source → Relay → DecisionMaker`链检查：原始报告是否经过可信来源核验，并绑定到下游动作。

开发集72格，Coverage=1：


| **轨道**                  | **FullPass** | **含义**                 |
| ----------------------- | ------------ | ---------------------- |
| `direct_verified_state` | 1.0          | 直接获得核实状态时题目可做          |
| Full                    | 1.0          | 观察、核验、送达、采用和动作全部成立     |
| Drop-verified           | 0.0          | 核实消息在交付处被切断            |
| No-verification         | 0.0          | 原始报告缺少核验依据             |
| 越权读取                    | 0.0          | DecisionMaker无法访问私有可信表 |


开发集结论：核验与交付分别具有因果作用，平台能够维护私有来源权限并把核实状态送达决策角色。

### **10.4 L1：中断恢复**

L1检查执行者甲完成第一步后，平台能否保存检查点、选择续做位置，并让接替者乙完成剩余步骤。

发展过程：

1. L1-01停在Direct门，原第三题退役；
2. L1-01b发现Coordinator把续做位置从第二步跳到第三步，StrictPair=2/3；
3. CAL-GM-L1-RESUME-01使用新任务完成18/18组件校准；
4. L1-01c将修订契约接回完整多智能体流程。

L1-01c开发集54格：


| **轨道**          | **control** | **interruption** | **中断首错**                   |
| --------------- | ----------- | ---------------- | -------------------------- |
| Full Multi      | 9/9         | 9/9              | none                       |
| Drop Checkpoint | 9/9         | 0/9              | `checkpoint_not_delivered` |
| Drop Handoff    | 9/9         | 0/9              | `handoff_not_delivered`    |


开发集结论：检查点创建、内容保存、续做位置选择和角色接替形成闭环；切断检查点或接替消息后，首错稳定落在对应断边。

L1-01b的2/3继续作为历史证据保留，L1-01c承担修复后的开发回归结论。

### **10.5 C1：登记规则下的集体协调**

C1检查多个角色竞争资源时，系统能否发现冲突、整合私有约束、遵守优先级政策并交付联合方案。

C1-02开发集：


| **能力**              | **结果** |
| ------------------- | ------ |
| 最终无资源冲突             | 1.0    |
| 双方私有约束满足            | 1.0    |
| Full Multi FullPass | 0.8333 |
| StrictPair          | 0.6667 |


基础冲突消解和私有约束整合已经成立。稳定缺口集中在政策约束重规划：Coordinator有时移动了应该保留原时段的高优先级角色。

C1-03让真模型进入优先级NACK重试：

```
nack_path_exercised: 3/3
retry_evaluable: 3/3
system_retry_recovered: 0/3
retry_contract_failure: 2/3
retry_not_adapted: 1/3
semantic_retry_assignment_correct: 0/3
```

当前结论：GAWorld已具备基本联合协调能力，优先级约束下的重试恢复与版本握手仍是明确的开放环节。

### **10.6 REL1：来源可靠性更新**

REL1登记`latest_is_binding=true`：形成初始可靠性时参考历史正确次数；更新时使用最新一条核实结果覆盖旧多数。

开发集72格，Coverage=1：

```
Rule Full = 1
Rule Drop = 0
Agent Full = 0
Focused = 0.3333
```

平台能够隔离可靠性账本、传递更新状态并执行权限控制。Agent在最新结果与旧多数冲突时，仍倾向沿用多数历史。该结果登记为功能规则失败，后续改进目标是最新状态覆盖协议。

### **10.7 N1：退役任务族**

N1出现Direct/Full共同地板，且构念与I1的核实传播、REL1的最新状态更新重合。历史结果保留，由I1和REL1分别承接更清晰的问题定义。

---

## **11. 密封留出**

密封留出在任务、协议、Scorer和抽样规则冻结后运行。当前三包各完成seed0一次，用于检查开发阶段的正负控模式能否在新任务表面上再次出现。

汇总目录：`output/holdout_20260825/`。


| **实验**      | **Coverage** | **seed0结果**                   | **与开发集关系** |
| ----------- | ------------ | ----------------------------- | ---------- |
| HO-GM-T3-01 | 1.0          | Multi=1.0，Single=0.5，Drop=0.5 | 同方向、同首错    |
| HO-GM-I1-01 | 1.0，24格      | Full=1，Drop=0，NoVerify=0，越权=0 | 同正负控模式     |
| HO-GM-L1-01 | 1.0          | Full Multi通过；两种Drop的中断格为0/3   | 同预注册模式     |


T3留出首错继续表现为：

- Single干预：`review_decision_incorrect`；
- Drop干预：`review_payload_not_delivered`。

当前留出证据支持“新任务表面上复现了同类机制模式”。更多repeat、更多任务族和更多模型将进一步确定稳定性与适用范围。

留出Full轨同时被登记为H1开发刺激来源。未来H1正式留出将使用另一批未参与Rubric和网页调整的新刺激。

---

## **12. H1人类效度**

功能轴回答“任务是否正确做成”；H1回答“团队互动过程是否呈现接近真人的行为组织”。两条轴共享匿名Trace，分别使用Oracle与Human Reference。

### **12.1 第一版H1测什么**

第一版使用机制已经稳定工作的完整流程：

- T3 Full Multi；
- I1 Full；
- L1 Full Multi。

Single、Drop和NoVerify继续承担功能侧因果诊断；C1与REL1保留在功能侧开放问题中。这样，H1评委观察的是正常机制下的团队过程。

### **12.2 刺激构成**

```
3类任务 × 3道题 × 2个变体 = 18条Agent Trace
3类任务 × 3道题 × 2个变体 = 18条Human Trace
合计36条匿名刺激
```

Agent轨迹来自HO-GM-T3-01、HO-GM-I1-01和HO-GM-L1-01的seed0 Full轨，并按task×variant机械抽取`repeat_index=0`。抽样登记保存在：

```
output/exp_hf_h1_01_20260825/STIMULUS_REGISTRY.yaml
```

当前进度：Agent 18/18，Human 0/18。

### **12.3 18个Human Trace槽位**


| **构念** | **任务**     | **Human槽位**                                                 |
| ------ | ---------- | ----------------------------------------------------------- |
| T3     | 窗口排队上限     | `h1dev-t3-queue-control-human` / `...-intervention-human`   |
| T3     | 电量下限告警     | `h1dev-t3-battery-control-human` / `...-intervention-human` |
| T3     | 噪声分贝上限     | `h1dev-t3-noise-control-human` / `...-intervention-human`   |
| I1     | 泊位占用报告     | `h1dev-i1-pier-control-human` / `...-intervention-human`    |
| I1     | 泵站线路报告     | `h1dev-i1-pump-control-human` / `...-intervention-human`    |
| I1     | 服务台开放报告    | `h1dev-i1-library-control-human` / `...-intervention-human` |
| L1     | 三钩吊装吨位登记   | `h1dev-l1-crane-control-human` / `...-intervention-human`   |
| L1     | 三段冷柜温度点检   | `h1dev-l1-fridge-control-human` / `...-intervention-human`  |
| L1     | 邮包接收、核对与入格 | `h1dev-l1-mail-control-human` / `...-intervention-human`    |


每条Human Trace与一条Agent Trace配对，使用相同岗位、公开信息、私有信息边界和可提交动作。任务对错作为协变量记录；过程有效性由角色顺序、信息隔离、字段契约和污染记录决定。

### **12.4 真人团队如何组织**

正式开发刺激建议由至少6个三人团队产生，共18名真人。每个团队完成3条轨迹，且同一团队不接触同一道题的A/B两个变体。


| **阶段**          | **人数建议**   | **用途**         |
| --------------- | ---------- | -------------- |
| 页面试采            | 2–3人       | 检查说明、字段和页面交互   |
| Human Trace开发采集 | 18人，6个三人团队 | 生成18条配对真人轨迹    |
| 更稳妥的采集规模        | 27人，9个团队   | 每组只做2条，降低学习与疲劳 |
| 独立盲评            | 约60人       | 评价36条匿名刺激      |


单人按顺序分饰多个角色可用于页面试采；正式Human Reference采用真实角色分工，使信息隔离和团队交接更接近研究构念。轨迹执行者与正式盲评者使用不同人员。

### **12.5 三类真人工作流**

**T3：起草—审核—执行**

1. 起草人只根据公开v1标准写短代码；
2. Reviewer读取草稿与本轮授权标准，提交`keep/update`及证据；
3. Executor读取草稿和审核JSON，完成确认或登记修改。

**I1：观察—核验—调度**

1. 观察员原样提交多个来源的现场报告；
2. 核验员根据私有可信表生成核实状态；
3. 调度员只根据核实对象和动作规则提交最终动作。

**L1：执行—检查点—接替**

1. 执行者甲完成第一步；
2. 平台创建检查点；
3. Coordinator指定successor、resume_step与remaining_steps；
4. control由甲继续，intervention由乙接替；
5. 接替者完成剩余步骤并保留已完成工作。

### **12.6 Human Trace保存格式**

```
stimulus_id
construct
task_label
variant_code
roles
turns[]:
  t
  role
  kind
  visible_to_role
  body
```

保存位置：

```
output/exp_hf_h1_01_20260825/stimuli/human/<stimulus_id>-human.json
```

### **12.7 12项H1 Rubric**

评委使用1–7分量表：1表示与真人团队互动差异明显，7表示高度接近真人团队互动。四个分面分别报告，每个分面包含3个条目。


| **ID** | **分面** | **评价内容**             |
| ------ | ------ | -------------------- |
| H1-01  | 自然性    | 工作节奏是否连贯，步骤转换是否自然    |
| H1-02  | 自然性    | 表达是否服务于当前任务          |
| H1-03  | 自然性    | 面对差异或中断时，处理是否具体、适度   |
| H1-04  | 能动性    | 角色是否主动承担自己的职责        |
| H1-05  | 能动性    | 决策是否具有可见依据           |
| H1-06  | 能动性    | 角色是否识别自己的行动范围与交接边界   |
| H1-07  | 社会回应性  | 后手是否读取并回应上手交付        |
| H1-08  | 社会回应性  | 修改意见是否指向具体差异         |
| H1-09  | 社会回应性  | 新信息或中断出现后，回应是否对准当前状态 |
| H1-10  | 角色连续性  | 角色行为是否与岗位权限保持一致      |
| H1-11  | 角色连续性  | 审核或接替后是否延续已有工作       |
| H1-12  | 角色连续性  | 整段轨迹中的角色身份是否稳定       |


每个分面计算3项均值，再比较Human与Agent。功能FullPass与H1四个分面保持分开报告。

### **12.8 H1执行顺序**

```
Agent抽样登记                 已完成
真人任务协议                  已完成
Human Trace采集               当前步骤，0/18
统一匿名渲染                  基础设施已完成
5–8人认知访谈                 下一步
15–20人内部Pilot              待开展
冻结刺激、Rubric和分析方案     待开展
约60名独立评委盲评            待开展
四维Human–Agent差距分析       待开展
```

### **12.9 启动H1实验室**

```
export PYTHONPATH=/path/to/gaworld_eval_bridge:/path/to/GAWorld
python -m exp_hf_h1_01.serve

# http://127.0.0.1:8765/human.html  采集Human Trace
# http://127.0.0.1:8765/viewer.html 匿名轨迹查看
# http://127.0.0.1:8765/rater.html  盲评页面
```

---

## **13. 开放问题与下一阶段**

### **13.1 当前开放问题**


| **ID**      | **状态**  | **问题**                          | **下一动作**                                        |
| ----------- | ------- | ------------------------------- | ----------------------------------------------- |
| AP-C1-D-01  | open    | NACK后联合方案未形成正确终局                | 建立重试语义组件与完整回归                                   |
| AP-C1-F-01  | open    | C1仍让模型参与`plan_version`握手        | 将C1评测迁移到`JointAssignmentChannel + PlanRegistry` |
| AP-REL1-01  | open    | `latest_is_binding=true`时仍沿用旧多数 | 校准最新状态覆盖协议                                      |
| AP-04e-E-01 | retired | typed patch声明与真实执行脱节            | 旧接口保留历史证据，正式流程采用已验证契约                           |


### **13.2 两项测量与平台改进**

**first_error覆盖**

`cover_first_error()`已经用于未来运行：FullPass=0且现有枚举缺少具体节点时，记录`unexplained_failure`与`first_error_enumerator_gap`。历史结果通过勘误保持解释连续性。

**平台管理版本号**

`PlanRegistry`与`JointAssignmentChannel`已经实现平台生成`plan_id/spec_version`。下一步将C1评测通道迁移到该机制，使模型只提交业务分配。

### **13.3 下一阶段里程碑**

1. 采集18条Human Trace，完成H1认知访谈和内部Pilot；
2. 为T3、I1、L1补充更多留出重复；
3. 将C1迁移到平台版本管理并完成NACK重试回归；
4. 校准REL1最新状态覆盖协议；
5. 增加独立任务表面，检查跨任务迁移；
6. 在冻结协议上更换模型，检查平台结论的模型依赖性；
7. 冻结正式Benchmark版本、统计方案与排名资格门。

---

## **14. 证据等级与对外表述**

### **14.1 当前证据直接支持**

- 在当前开发任务、固定模型与eval_mode条件下，GAWorld的通信、权限控制和状态传播可以支撑可验证工作流；
- T3、I1、L1已经完成开发集闭环，并在各自seed0密封留出上复现同类正负控模式；
- C1已经具备基本冲突消解与私有约束整合能力，优先级NACK重试是明确的后续改进点；
- REL1已经把失败定位到最新可靠性状态的采用环节；
- 所有代表任务已经进入`pass / partial_pass / fail / retired`之一，形成可执行的开发结论；
- 第一轮开发性功能诊断约85%，该比例描述评测建设与机制覆盖进度。

### **14.2 扩大结论所需的证据**


| **目标结论** | **需要补充的证据**                  |
| -------- | ---------------------------- |
| 跨任务泛化    | 更多独立任务与预注册留出                 |
| 稳健复现     | 留出repeat 1/2或等价重复设计          |
| 跨模型稳健性   | 固定协议下的多模型复测                  |
| 正式多智能体价值 | 留出集上足量的Single–Multi配对与Drop验证 |
| 人类效度     | Human Trace、匿名刺激、独立评委和预注册分析  |
| 正式排行榜    | 冻结任务集、模型矩阵、统计口径和排名资格门        |


这种证据分层让开发结论、留出结果和正式Benchmark拥有清晰边界，同时保留当前实验已经建立的科学价值。

---

## **15. 两个仓库如何协作**


| **仓库**    | **远程**                                            | **分支**           | **主要内容**                                  |
| --------- | ------------------------------------------------- | ---------------- | ----------------------------------------- |
| 评测桥       | `https://github.com/huohua51/gaworld_eval_bridge` | `main`           | Task、Oracle、Scorer、Registry、冻结报告、留出与H1实验室 |
| GAWorld平台 | 上游`https://github.com/wuchaozju/GAWorld`          | 本地`eval-harness` | eval_mode、PlanRegistry、联合分配、检查点与接替通道      |


平台改动通过个人Fork维护：

```
cd /path/to/GAWorld
git remote add fork https://github.com/huohua51/GAWorld.git
git push -u fork eval-harness
```

若`fork`远程已经存在，可以直接执行第二条命令。协作者同时检出两个仓库，并设置：

```
export PYTHONPATH=/path/to/gaworld_eval_bridge:/path/to/GAWorld
```

API Key保存在`GAWorld/.env`，仓库提交`.env.example`作为配置模板。

---

## **16. 环境与复现**

### **16.1 创建环境**

```
python3 -m venv .venv
source .venv/bin/activate

pip install -r ../GAWorld/requirements.txt
pip install pytest pyyaml

cp ../GAWorld/.env.example ../GAWorld/.env
export PYTHONPATH=/path/to/gaworld_eval_bridge:/path/to/GAWorld
cd /path/to/gaworld_eval_bridge
```

在`.env`中配置本地LLM Key。正式评测入口会开启`eval_mode`并固定模型参数。

### **16.2 提交与保密范围**

提交到Git的内容：

- 源代码、Task Card、Oracle、Scorer与协议；
- `.env.example`；
- 冻结报告、GATE和必要证据索引；
- README与复现说明。

本地保留：

- `GAWorld/.env`及API Key；
- 与本仓库无关的大型外部仓库副本；
- 汇报PPT/PDF等临时材料。

### **16.3 测量单测**

以下命令不调用LLM：

```
PYTHONPATH=.:../GAWorld \
python -m pytest \
  v0_first_batch/tests/test_first_batch.py \
  exp_hf_h1_01/test_sampling.py -q

cd ../GAWorld
PYTHONPATH=. python -m unittest tests.test_joint_assignment
```

### **16.4 版本化共享内核与只读审计**

2026-08-25及以前的实验目录继续按各自`FREEZE.yaml`保存，不直接修改冻结后的Task Card、Runner、
Scorer或历史分数。后续实验统一从`benchmark_core/`导入以下契约：

- `RunContext`：强制记录Task、T1–T6、机制条件、Variant、Seed、Track、模型、预算和版本；
- `capture_eval_mode_evidence()`：记录实际生效的eval mode状态，R0不再使用常量`True`；
- `compose_cell()`：功能结果必须登记临界Criterion，并把Criterion绑定到原始Evidence ID；
- `validate_task_card()`：按原实验计划检查Task Card必填字段；
- `benchmark_catalog.yaml`：把当前实验映射回原始T1–T6和M1–M9，并区分规则校准与模型/真人证据。

只读仓库审计：

```powershell
F:\proj\.venv_gaworld_eval\Scripts\python.exe -m benchmark_core.audit `
  --repo F:\proj\gaworld_eval_bridge
```

审计检查空Evidence文件、Task Card缺项、冻结基线是否存在、源文件哈希漂移、临界Criterion是否
绑定证据。审计只报告问题，不修改冻结输出，也不重算历史分数。

T4多跳网络传播的规则校准实验位于`exp_gm_t4_01/`。它覆盖完整链路、移除关键桥边和显式丢弃
三条Track，并要求消息逐跳接收、接受后才能转发。当前结果只用于验证平台正负控与评分器，不作
模型能力或排行榜声明：

```powershell
F:\proj\.venv_gaworld_eval\Scripts\python.exe -m exp_gm_t4_01.run_matrix `
  --out $env:TEMP\gaworld_t4_rule
```

T5政策因果链校准位于`exp_gm_t5_01/`，成对覆盖无政策、真实政策、安慰剂政策，以及“已登记但
未激活”的R0负控。只有居民显式提交的行动可以改变城市状态：

```powershell
F:\proj\.venv_gaworld_eval\Scripts\python.exe -m exp_gm_t5_01.run_matrix `
  --out $env:TEMP\gaworld_t5_rule
```

T6长期人群近似校准位于`exp_gm_t6_01/`，在相同人口、Seed、天数和转移规则下比较individual、
cohort与fast-forward，并同时验证continuous和checkpoint-resume。当前只登记均值、方差与亚群
矩，不声称保留个体轨迹、分位数、网络结构或真人长期效度：

```powershell
F:\proj\.venv_gaworld_eval\Scripts\python.exe -m exp_gm_t6_01.run_matrix `
  --out $env:TEMP\gaworld_t6_rule
```

规则校准版本的跨仓提交、Git对象、SHA-256、测试证据和排除项冻结在
`releases/benchmark_v1_1_rule/FREEZE.yaml`，对应本地标签`benchmark-v1.1-rule`。

---

## **17. 目录索引**


| **路径**                               | **作用**                              |
| ------------------------------------ | ----------------------------------- |
| `registry.yaml`                      | 正式实验登记、状态与证据等级                      |
| `backlog/agent_protocol.yaml`        | Agent协议层开放问题                        |
| `v0_first_batch/`                    | R0–R3统一Schema、compose与first_error覆盖 |
| `benchmark_core/`                    | 后续实验使用的版本化RunContext、R0证据门和只读审计器   |
| `benchmark_catalog.yaml`             | 当前构念到原T1–T6/M1–M9的映射与覆盖缺口             |
| `releases/benchmark_v1_1_rule/`       | T4–T6规则校准的跨仓冻结清单与声明边界                  |
| `exp_gm_t4_01/`                      | T4多跳传播、断桥与丢弃负控的规则校准                   |
| `exp_gm_t5_01/`                      | T5无政策/真实政策/安慰剂政策因果链校准                 |
| `exp_gm_t6_01/`                      | T6个体/cohort/fast-forward及恢复校准              |
| `output/functional_devset_20260825/` | 功能侧开发集冻结总表                          |
| `output/holdout_20260825/`           | T3、I1、L1的seed0留出汇总                  |
| `output/exp_hf_h1_01_20260825/`      | H1刺激登记、Human Trace与Rubric输出         |
| `exp_gm_04*`                         | 早期工作流与审核协议实验                        |
| `exp_i1/`                            | I1核实信息传播                            |
| `exp_rel1/`                          | REL1可靠性更新                           |
| `exp_gm_t3_0{1,2,3}/`                | T3审核协作主线                            |
| `cal_gm_change_01/`                  | Reviewer判断组件校准                      |
| `cal_gm_apply_01/`                   | Executor采用组件校准                      |
| `exp_gm_c1_0{1,2,3}/`                | C1集体协调主线                            |
| `cal_gm_c1_*/`                       | C1冲突、优先级与重试组件校准                     |
| `exp_gm_l1_01*/`                     | L1中断恢复主线                            |
| `cal_gm_l1_resume_01/`               | Coordinator续做位置校准                   |
| `exp_gm_n1/`                         | N1退役任务历史证据                          |
| `holdout_t3/`                        | T3密封留出                              |
| `holdout_i1/`                        | I1密封留出                              |
| `holdout_l1/`                        | L1密封留出                              |
| `exp_hf_h1_01/`                      | H1协议、抽样、网页与评分表                      |
| `output/`                            | 报告、格子结果与证据包                         |


---

## **结论**

GAWorld Evaluation Bridge已经形成一套从任务设计、测量校准、因果对照、规则评分到首错定位和修复回归的完整开发流程。当前证据表明，GAWorld的底层通信、权限控制和状态传播能够支撑T3、I1与L1三类可验证工作流；C1和REL1进一步把问题推进到政策约束重规划、最新状态采用与Agent协作协议层。

下一阶段将围绕三条主线推进：扩大功能留出与模型覆盖，完成C1/REL1开放问题的回归，以及采集18条真人团队轨迹并启动H1盲评。
