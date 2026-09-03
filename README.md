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
model: GLM-5.2
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

从框架建立到当前功能测封板的完整问题链、改正措施、复测效果、证据边界与方法论反思，见
[`docs/FUNCTIONAL_EVALUATION_RETROSPECTIVE_20260828.md`](docs/FUNCTIONAL_EVALUATION_RETROSPECTIVE_20260828.md)。该复盘区分“已在新任务上闭环”“核心单元修复已落地但端到端Gate仍开放”和“仅完成规则校准”三种状态。


| **任务族**    | **开发状态**       | **代表实验**      | **当前结论**                   | **留出状态** |
| ---------- | -------------- | ------------- | -------------------------- | -------- |
| T3 审核协作    | `pass`         | T3-03         | 独立Reviewer私有信息通过审核通道进入真实产物 | seed0同模式 |
| I1 核实传播    | `pass`         | EXP-GM-I1     | 核实、送达、采用形成完整因果链            | seed0同模式 |
| L1 中断恢复    | `pass`         | L1-01c        | 检查点、续做位置和角色接替形成闭环          | seed0同模式 |
| C1 集体协调    | `core_unit_fix_pending_e2e` | C1-02 至 C1-05 | retry语义与平台ID所有权已定位，核心单元修复已落地，正式Gate仍未通过 | 待新编号端到端回归 |
| REL1 可靠性更新 | `core_unit_fix_pending_e2e` | REL1 / REL1-02 / REL1-03 | 分阶段协议方向有效，动作证据绑定单元修复已落地，coverage Gate仍未关闭 | 待新编号端到端回归 |
| T4 多跳传播    | `v2_repeat_pass` | T4-01 / T4-02 | v2 full Track在seed0/1/2的六个任务变体组合均稳定通过 | 三次完成 |
| T5 政策因果链   | `two_model_replicated_pass` | T5-01 / T5-02 / T5-03 / HO-T5-03 / HO-T5-04 | GLM-5.2与gpt-5.4在四个新增表面双重复全过；Qwen配额中断轮保留但停止续跑 | 双模型密封复现完成，T5功能侧封板 |
| N1 一般信息更新  | `retired`      | EXP-GM-N1     | 构念由I1与REL1分别承接             | 历史结果冻结   |


当前开发状态可以概括为：

```
functional_development: largely_complete
functional_holdout: seed0_pattern_replication
ranking_eligible: false
formal_benchmark: next_stage

t4_rule_calibration: frozen
t4_glm52_control_full: 4/9
t4_glm52_model_contract: 9/9

h1_infrastructure: ready
h1_agent_stimuli: 18/18
h1_human_reference: 0/18
h1_formal_score: N/A

c1_core_implementation: handoff_required
rel1_protocol_and_core_implementation: handoff_required
t4_cross_model: blocked_by_gpt54_provider_quota
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

C1-04进一步把业务 assignments 与平台 ID 分开，36/36 响应满足严格 JSON，但 FullPass 仅
3/6，intervention retry 只恢复 1/3。C1-05增加“当前规范是唯一权威”的显式语义后，三个
intervention retry 全部恢复，严格 FullPass仍为4/6，说明目标模式得到缓解但整个 C1 链尚未
通过。故障位置、建议核心接口和验收条件见
[`C1 / REL1 核心实现交接`](docs/CORE_IMPLEMENTATION_HANDOFF_20260827.md)。评测仓不再代替
GAWorld 实现修复。

2026-08-28核心状态更新：GAWorld提交`ad93e9d`已经落实当前规范推进、陈旧计划拒绝和合法
proposal的平台ID分配。该提交回答了核心不变量问题，但尚未运行新编号C1端到端预注册回归，
所以本节历史Gate不变，C1仍不能标记为整体通过。

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

REL1-02把 latest-only update 和平台动作绑定接入新任务后，可测格中的更新与绑定均为4/4，
但共享阶段 Prompt 使 formation 只有1/4，另有两个 Observer 空列表导致 coverage=4/6。
REL1-03改为分阶段 Prompt和显式两来源计数，五个可测格全部 FullPass；第六格把 source ID
输出成整数 `1`，coverage=5/6，预注册 Gate仍为`measurement_invalid`。因此修复方向有支持，
但三个 REL1 action item 均未正式关闭。完整实现交接见
[`C1 / REL1 核心实现交接`](docs/CORE_IMPLEMENTATION_HANDOFF_20260827.md)。

2026-08-28核心状态更新：GAWorld提交`a14a748`已经落实信任动作与真实已采用消息的绑定。
本文档更新时，C1/REL1两组相关核心测试合计25项通过；但REL1尚无新任务端到端验收，
原有coverage Gate继续保持开放。

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

> **2026-08-28覆盖校正：** 当前`EXP-HF-H1-01`只是短程结构化团队互动的H1/H4管线Pilot，不是H1–H7完整Human Reference。18槽是3个协议模板、9个任务表面和2个条件，不是18种独立社会行为。正式18条采集暂停；当前网页最多用于三个认知试采槽。H2、H3、H5、H6、H7均保持`N/A`。总规划见[`docs/HUMAN_VALIDITY_MASTER_PLAN_20260828.md`](docs/HUMAN_VALIDITY_MASTER_PLAN_20260828.md)，下一版预注册草案见[`human_validity/h1_h4_v2/PREREGISTRATION.yaml`](human_validity/h1_h4_v2/PREREGISTRATION.yaml)。

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

当前进度（2026-08-27）：Agent 18/18；Human 正式采集 0/18。采集、槽位锁定、来源中立匿名化、盲评校验和隔离试采入口已完成自动测试，下一步是按[H1试采清单](docs/H1_PILOT_CHECKLIST_20260827.md)完成三个构念的认知试采；试采数据不计入正式分母。

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
collection:
  collection_mode
  team_code
  session_code
  role_assignments
  started_at_client
  duration_ms
  protocol_deviations
  consent_confirmed
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
Human Trace采集               正式0/18；试采入口已就绪
统一匿名渲染                  已完成来源中立ID与访问白名单
2–3人最小认知试采             当前步骤
5–8人认知访谈                 最小试采通过后扩展
15–20人内部Pilot              待开展
冻结刺激、Rubric和分析方案     待开展
约60名独立评委盲评            待开展
四维Human–Agent差距分析       待开展
```

### **12.9 启动H1实验室**

```powershell
$env:PYTHONPATH = 'F:\proj\gaworld_eval_bridge;F:\proj\GAWorld'

F:\proj\.venv_gaworld_eval\Scripts\python.exe `
  -m exp_hf_h1_01.serve `
  --out output\exp_hf_h1_01_pilot_sandbox_20260827 `
  --port 8765

# http://127.0.0.1:8765/human.html  采集Human Trace
# http://127.0.0.1:8765/viewer.html 匿名轨迹查看
# http://127.0.0.1:8765/rater.html  盲评页面
```

试采必须使用独立`--out`目录，避免覆盖冻结开发刺激或把页面调试数据误作正式Human Reference。完整现场步骤、最小三槽样本、认知访谈问题和正式放行门见[`docs/H1_PILOT_CHECKLIST_20260827.md`](docs/H1_PILOT_CHECKLIST_20260827.md)。

### **12.10 H1–H7覆盖与下一版边界**

原始规划中的H1–H7需要不同Human Reference，不能由同一套短任务和盲评量表代替。当前只有H1外在自然度管线和H4核验/交接终态的部分覆盖；H2个体行为、H3人际关系、H5长期轨迹、H6人群结构和H7干预反应没有匹配真人数据。

`EXP-HF-H1H4-02`将作为独立新版本：候选任务改为非代码、可自然表达且结构不同的修订、证据核验、中断交接和共同排序；远程系统必须提供三角色独立令牌、中央状态机、不可变事件日志和HTTPS。H1报告匹配自然度差、置信区间、评委一致性和来源猜测；H4分别报告发言、澄清、异议、核验、纠错采用、交接、重复劳动和越界，不合成总分。正式样本量在认知访谈和内部Pilot后由方差、最低可检测差异和评委信度决定。

四类候选Task Card及八个非代码任务表面已经形成草案，统一索引见[`human_validity/h1_h4_v2/tasks/INDEX.yaml`](human_validity/h1_h4_v2/tasks/INDEX.yaml)。每类任务已补充角色专属说明和功能/H4评分草案；统一H4编码见[`human_validity/h1_h4_v2/H4_CODEBOOK.yaml`](human_validity/h1_h4_v2/H4_CODEBOOK.yaml)，认知访谈与内部试采分别见[`COGNITIVE_INTERVIEW.md`](human_validity/h1_h4_v2/COGNITIVE_INTERVIEW.md)和[`INTERNAL_PILOT_RUNBOOK.md`](human_validity/h1_h4_v2/INTERNAL_PILOT_RUNBOOK.md)。这些材料均为尚未实际运行的草案；共同排序依赖C1或等价协调路径先通过Rule校准，所有卡仍为`formal_data_collection_allowed=false`。

2026-09-03新增Wave 1合成试采演练：按4队、12个合成角色、8条Synthetic Human轨迹、8条匹配Synthetic Agent占位轨迹和96份合成盲评记录走通分母与报告逻辑。该演练没有真人、没有模型调用、没有API费用，也没有解除任何采集门；结果与复现脚本见[`human_validity/h1_h4_v2/synthetic_pilot/`](human_validity/h1_h4_v2/synthetic_pilot/)。

---

## **13. 开放问题与下一阶段**

### **13.1 当前开放问题**


| **ID**      | **状态**  | **问题**                          | **下一动作**                                        |
| ----------- | ------- | ------------------------------- | ----------------------------------------------- |
| AP-C1-D-01  | handoff_to_core | NACK后联合方案可能移动受保护的高优先级Agent | 核心实现保护不变量；评测侧新编号回归 |
| AP-C1-F-01  | handoff_to_core | 模型参与`plan_id/spec_version`握手 | 核心改为accepted-only平台发号与旧规范拒绝 |
| AP-REL1-01  | handoff_to_protocol | `latest_is_binding=true`时仍可能沿用旧多数 | 分离formation/update协议；新表面验收 |
| AP-REL1-02  | handoff_to_protocol | formation可能忽略完整历史或默认首个来源 | 强制两来源计数与全部证据行 |
| AP-REL1-03  | handoff_to_core | Dispatcher可提交空、伪造或陈旧证据ID | 平台从已采用消息绑定action元数据 |
| AP-T4-01    | provider_blocked | GLM-5.2 v2三次稳定，gpt-5.4跨模型尚未执行 | 等待可用gpt-5.4额度后按冻结协议复测 |
| AP-T5-01    | two_model_replicated_pass | v3双模型密封通过；Qwen后37次被额度拒绝且联合Gate失败 | 保留失败分母；项目决定停止Qwen，不做recovery |
| AP-04e-E-01 | retired | typed patch声明与真实执行脱节            | 旧接口保留历史证据，正式流程采用已验证契约                           |


### **13.2 两项测量与平台改进**

**first_error覆盖**

`cover_first_error()`已经用于未来运行：FullPass=0且现有枚举缺少具体节点时，记录`unexplained_failure`与`first_error_enumerator_gap`。历史结果通过勘误保持解释连续性。

**核心实现交接**

C1与REL1的评测侧诊断、建议接口和验收矩阵已整理到
[`docs/CORE_IMPLEMENTATION_HANDOFF_20260827.md`](docs/CORE_IMPLEMENTATION_HANDOFF_20260827.md)。
GAWorld核心修复由其他开发同学负责；本评测仓不把本地原型视为已合并能力，也不会推送核心修复分支。

### **13.3 下一阶段里程碑**

1. 采集18条Human Trace，完成H1认知访谈和内部Pilot；
2. 为T3、I1、L1补充更多留出重复；
3. 由核心开发同学实现C1平台版本/保护不变量，评测侧随后做新编号NACK重试回归；
4. 由协议与核心开发同学处理REL1分阶段更新和动作证据绑定，评测侧随后验收；
5. 增加独立任务表面，检查跨任务迁移；
6. 在冻结协议上更换模型，检查平台结论的模型依赖性；
7. 冻结正式Benchmark版本、统计方案与排名资格门。

---

## **14. 证据等级与对外表述**

### **14.1 当前证据直接支持**

- 在当前开发任务、固定模型与eval_mode条件下，GAWorld的通信、权限控制和状态传播可以支撑可验证工作流；
- T3、I1、L1已经完成开发集闭环，并在各自seed0密封留出上复现同类正负控模式；
- C1已经具备基本冲突消解与私有约束整合能力；C1-04/05进一步把失败拆成保护优先级重规划、平台ID所有权和其他初始决策错误，正式Gate仍未通过；
- REL1已经把失败拆成formation历史计数、latest-binding更新和Dispatcher证据绑定；REL1-03五个有效格全过但coverage=5/6，正式Gate仍未通过；
- T4-v1暴露control转发歧义；T4-v2的六个full任务变体组合在seed0/1/2上Prompt哈希稳定，转发、完整路径、目标接受和FullPass均为100%；
- T5-v3在三任务、三状态、repeat 1/2上18/18格通过，72/72次scope语义与逐居民directive正确，且重复结果完全一致；
- T5-v3密封新任务在GLM-5.2与gpt-5.4上各9/9格通过，72/72次调用满足严格JSON；9/9个任务×状态组合的Prompt与注册结果跨模型完全一致；
- T5-v3扩展密封轮中GLM-5.2与gpt-5.4各24/24格通过；Qwen为14/24格，后37次因网关额度不足被拒绝，故三模型联合注册Gate失败且不补替；
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

API Key通过`PARATERA_API_KEY`环境变量或本地`GAWorld/.env`提供；真实Key不进入仓库，
仓库只提交`.env.example`作为配置模板。

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

### **16.5 T4/T5统一模型Pilot**

`model_pilot/`在冻结规则版本之上增加统一调用预算、严格JSON契约、Prompt/原始响应哈希和独立
Evidence JSONL。默认不调用真实Provider；先运行离线接线校准：

```powershell
F:\proj\.venv_gaworld_eval\Scripts\python.exe -m model_pilot.run `
  --fixture-oracle --experiment both --out $env:TEMP\gaworld_model_fixture
```

真实调用必须显式指定Provider和放行开关。GLM-5.2的低成本协议检查关闭Thinking，并先做一次
最多256 tokens的Smoke，再启动Seed-0 Pilot：

```powershell
$env:GAWORLD_LLM_THINKING = 'disabled'

F:\proj\.venv_gaworld_eval\Scripts\python.exe -m model_pilot.smoke `
  --provider paratera_glm --allow-live-model --max-tokens 256 `
  --out $env:TEMP\gaworld_model_smoke

F:\proj\.venv_gaworld_eval\Scripts\python.exe -m model_pilot.run `
  --provider paratera_glm --allow-live-model --experiment both --max-tokens 256 `
  --max-calls 160 `
  --out $env:TEMP\gaworld_model_seed0
```

上述真实Pilot最多包含36格；仍属于开发证据，`ranking_eligible`固定为`false`。

### **16.6 GLM-5.2 T4 control一致性Pilot进度**

2026-08-26完成`T4-CONTROL-CONSISTENCY-GLM52-v1`。本轮先在提交`03f1c8f`中固定任务、
Prompt、Scorer、三个repeat、指标和36次逻辑调用上限，再由提交`44aa027`中的独立入口执行。
固定条件为`paratera_glm / GLM-5.2 / temperature=0 / thinking=disabled / max_tokens=256`。

```powershell
$env:PARATERA_API_KEY = [Environment]::GetEnvironmentVariable(
  'PARATERA_API_KEY', 'User'
)

F:\proj\.venv_gaworld_eval\Scripts\python.exe `
  -m model_pilot.control_consistency `
  --provider paratera_glm --allow-live-model `
  --out output\model_pilot_live_t4_control_consistency_glm52_<run_id>
```

9格均测量有效，模型结构化契约9/9通过；实际使用26/36个逻辑调用。每个任务的源节点转发序列、
完整路径率和FullPass率如下：

| **任务** | **三次source_forward** | **一致率** | **完整路径率** | **FullPass率** |
| --- | --- | ---: | ---: | ---: |
| `t4_ferry_closure_001` | `false, false, true` | 66.67% | 33.33% | 33.33% |
| `t4_clinic_recall_001` | `true, true, true` | 100% | 100% | 100% |
| `t4_shelter_capacity_001` | `false, false, false` | 100% | 0% | 0% |

合并source转发率、完整路径率和FullPass率均为44.44%。每个任务的三次source Prompt SHA-256完全
一致，因此差异不能归因于Prompt漂移；结果显示GLM-5.2在当前协议下同时存在场景依赖和同输入
重复不一致。该结论是开发性诊断，不是跨模型结论或排行榜成绩，`ranking_eligible=false`。

运行期间底层HTTP适配器对一次TLS EOF进行了同一逻辑请求的传输重试；26表示Benchmark逻辑
调用数，不等于底层HTTP尝试总数。原始证据、逐格结果和完整清单位于
[`CONSISTENCY_MANIFEST.yaml`](output/model_pilot_live_t4_control_consistency_glm52_a79353a8c7cf4720a3efb411a438ccd7/CONSISTENCY_MANIFEST.yaml)，
简要报告位于同目录的[`REPORT.md`](output/model_pilot_live_t4_control_consistency_glm52_a79353a8c7cf4720a3efb411a438ccd7/REPORT.md)。

### **16.7 T4-v2显式注册传输协议**

`EXP-GM-T4-02`是独立实验，不覆盖或重算T4-v1。它新增水库水质、变电站负载和学校空气质量三
个任务表面，并规定有效的`registered_status_update`必须沿可用登记路径逐跳接受和转发；
`action_required`只决定目标动作，不决定消息是否传输。full Track中的目标接受与完整路径均为
临界Criterion。

规则矩阵18/18格测量有效并通过校准；离线Oracle-shaped模型矩阵同样完成18格，JSON契约率
100%，使用60/60个逻辑调用。`full`的control/intervention FullPass均为100%；
`remove_bridge`和`drop_bridge`均为control 100%、intervention 0%。这些只证明规则、Scorer、
Prompt接线和预算边界可用，不是GLM-5.2能力结果。

真实运行先在`model_pilot/registrations/T4_REGISTERED_TRANSPORT_GLM52_v2.yaml`冻结18格设计、60次
逻辑调用上限、输入哈希和停止规则，再以`paratera_glm / GLM-5.2 / temperature=0 /`
`thinking=disabled / max_tokens=256`执行。18/18格测量有效、60/60个结构化响应通过契约；所有
18个source均选择转发，full Track目标接受6/6。full的control/intervention均100%通过；两种
断桥Track均为control 100%、intervention 0%，且没有模型传输重试事件。

v1的control转发歧义在v2中没有复现；但v2同时改变了显式协议和任务表面，因此不能把差异单独
归因于Prompt措辞。它仍是seed0开发性证据，`ranking_eligible=false`。完整证据位于
[`RUN_MANIFEST.yaml`](output/model_pilot_live_t4_v2_glm52_cbf1c8069f254797ab6e5a795c898399/RUN_MANIFEST.yaml)，
审计简报位于同目录的[`REPORT.md`](output/model_pilot_live_t4_v2_glm52_cbf1c8069f254797ab6e5a795c898399/REPORT.md)。
预注册中的`not_run`是执行前冻结状态，保持不回写。cell内硬编码的离线phase标签勘误也登记在该
报告中，不影响Gate或得分，原始结果未事后改写。离线复现命令：

```powershell
F:\proj\.venv_gaworld_eval\Scripts\python.exe `
  -m exp_gm_t4_02.run_matrix --out $env:TEMP\gaworld_t4v2_rule

F:\proj\.venv_gaworld_eval\Scripts\python.exe `
  -m model_pilot.t4_v2_run --fixture-oracle --max-calls 60 `
  --out $env:TEMP\gaworld_t4v2_fixture
```

### **16.8 T4-v2重复稳定性与T5最小真实因果链**

T4-v2在先行提交的预注册下补跑repeat 1/2，共12个新格、48次逻辑调用。合并seed0/1/2后，
六个任务变体组合的source决策均为`true,true,true`，各组Prompt SHA-256一致；完整路径、目标接受、
模型契约和FullPass均为100%。证据和边界见
[`REPORT.md`](output/model_pilot_live_t4_v2_repeats_glm52_142003658f0d4235a38333f23ff17345/REPORT.md)。

T5随后以一个固定低排放区任务运行`no_policy / real_policy / placebo_policy`三格，共12次调用。
真实政策格正确改变两个目标居民；无政策格中模型仍尝试目标动作但被证据门拒绝；安慰剂格则把
`matched_nonbinding_notice`当作真实规则并改变同样两个居民。FullPass为`0 / 1 / 0`，变化率为
`0 / 0.5 / 0.5`，所以real-minus-placebo为0。完整逐居民诊断见
[`REPORT.md`](output/model_pilot_live_t5_minimal_glm52_2568149692c14faa864483801700c964/REPORT.md)。

两轮均为GLM-5.2开发证据，`ranking_eligible=false`；T5-v1不事后改Prompt，后续显式语义修复必须
使用新协议编号。

### **16.9 T5-v2显式政策语义Pilot**

T5-v2保留T5-v1代码和失败证据不动，在三个全新政策表面上显式定义`absence / binding /
nonbinding`，并在真实调用前由提交`fe5cad4`冻结任务、Prompt、Scorer、执行顺序和36次调用预算。
规则矩阵18格与离线模型矩阵9格均先通过，随后运行GLM-5.2 seed0真实矩阵。

真实运行的36个响应全部通过JSON契约，`notice_seen / binding`语义也36/36正确；absence与nonbinding
六格全部FullPass。三个binding格中，模型让每个任务的4位居民全部采取政策动作，实际变化率为1.0，
而预注册Oracle只允许2位目标居民变化。后续逐字段复核发现，非目标居民的外层字段为
`required_action=keep_current`，但嵌套notice里另有同名`required_action=政策动作`。因此原始评分与
溢出事实保持有效，但v2应解释为协议字段碰撞，不能作为干净的eligibility服从失败。原始报告见
[`REPORT.md`](output/model_pilot_live_t5_v2_glm52_9825ec9ec7c64b598dc80c1e59ce09af/REPORT.md)。
事后勘误见
[`POST_RUN_ADDENDUM.md`](output/model_pilot_live_t5_v2_glm52_9825ec9ec7c64b598dc80c1e59ce09af/POST_RUN_ADDENDUM.md)。

该结果仍是三任务、seed0开发诊断，`ranking_eligible=false`；修复必须使用新协议编号，不能修改
本轮Prompt补跑。

### **16.10 T5-v3 eligibility-scope repeat 1/2**

T5-v3由提交`4fa5fd4`在真实调用前完成预注册。协议将全局字段改为`policy_action`，并将
`resident_directive.action`设为唯一执行权；Prompt中不再存在`required_action`键。模型同时回报
`notice_seen / binding / target_match / authorized / action`，评分器从原始请求、响应和状态变化独立重建结果。

真实矩阵为三个冻结任务表面 × 三种政策状态 × repeat 1/2，共18格、72次GLM-5.2调用。18/18格
FullPass，JSON契约、scope语义、directive服从、政策响应和无越界变化均为100%；变化率严格为
`absence=0 / binding=0.5 / nonbinding=0`。九个任务×状态组合的逐居民Prompt SHA-256在两次repeat
间一致，结构化scope输出、动作和FullPass也全部精确一致。完整审计见
[`REPORT.md`](output/model_pilot_live_t5_v3_repeats_glm52_e052783444814bafa16c26c21ebad5c6/REPORT.md)。

这证明该显式scope协议在现有三个任务表面上可重复工作；由于任务是在v2诊断后复用，它仍属于
开发回归，不能与不同Prompt的v2 seed0合并，也不能替代全新任务留出、跨模型复测或Human Reference。

### **16.11 T5-v3密封新任务与跨模型复测**

`T5-V3-SEALED-CROSS-MODEL-v1`在任何正式留出调用前，以提交`50e7aeb`共同冻结三个全新任务、
GLM-5.2与gpt-5.4、Prompt字节、严格JSON契约、评分器、分母、72次总预算和停止规则。新任务的
任务ID、角色、群体、动作与状态字段均不复用T5开发集；先完整执行GLM-5.2，再在不能根据首个模型
结果调整设计的前提下执行gpt-5.4。

两个模型各自9/9格FullPass、36/36次调用通过严格JSON，行为变化率均严格为
`absence=0 / binding=0.5 / nonbinding=0`，scope语义、directive服从与政策响应均为100%。
9/9个任务×政策状态组合的Prompt SHA-256逐居民一致，scope布尔值、动作与FullPass跨模型
精确一致。独立审计同时确认binding下12/12个非授权居民未越界，nonbinding下12/12个目标居民
正确识别但未执行无约束建议，输出中未发现凭据。完整边界与证据见
[`REPORT.md`](output/t5_v3_sealed_cross_model_4b23257f73694663886c9394118dc887/REPORT.md)。

这是三任务、双模型、seed0的密封功能留出，不是广泛模型泛化、真人效度、现实政策效果或排行榜结论。

### **16.12 T5-v3四任务、三模型与双重复扩展**

`T5-V3-EXPANDED-3MODEL-REPEAT-v1`由提交`2eaa642`在任何新题调用前冻结四个新增任务、
GLM-5.2 / gpt-5.4 / qwen3.7-plus、seed 0/1、Prompt、评分器、固定分母和288次调用上限。
四个任务对全部既有T5任务的ID、政策ID、渠道、角色、群体、动作和状态字段均不相交；两个
repeat是byte-identical输入的独立调用标签。

288/288个逻辑调用均留下响应记录，注册设计遵循为true。GLM-5.2与gpt-5.4分别96/96次有效、
24/24格FullPass，两个seed各12/12格通过，行为变化率均为`0 / 0.5 / 0`。qwen3.7-plus
完成59个有效响应后，逻辑调用60–96全部被qweapi以HTTP 403额度不足拒绝；其seed0为12/12格、
seed1为2/12格，总计14/24格。按预注册固定分母和禁止补替规则，联合Gate为失败。

24/24个跨模型比较与36/36个模型内重复比较的Prompt完全一致；注册结果精确一致分别为
14/24与26/36。三个模型实际返回的251个有效响应中，251/251与冻结scope/directive精确一致，
但available-case诊断不能替代主结果。完整审计与恢复边界见
[`REPORT.md`](output/t5_v3_expanded_3model_repeats_b7814a7e906e4988a8e7ecf517d6e043/REPORT.md)。

项目决定停止Qwen，不再充值或建立recovery。本轮37个配额失败及联合失败Gate永久保留；T5功能侧以
GLM-5.2与gpt-5.4的两批密封复现作为当前结论，后续资源转向C1、REL1、T4跨模型与Human Reference。

---

## **17. 目录索引**


| **路径**                               | **作用**                              |
| ------------------------------------ | ----------------------------------- |
| `registry.yaml`                      | 正式实验登记、状态与证据等级                      |
| `backlog/agent_protocol.yaml`        | Agent协议层开放问题                        |
| `v0_first_batch/`                    | R0–R3统一Schema、compose与first_error覆盖 |
| `benchmark_core/`                    | 后续实验使用的版本化RunContext、R0证据门和只读审计器   |
| `benchmark_catalog.yaml`             | 当前构念到原T1–T6/M1–M9的映射与覆盖缺口             |
| `docs/FUNCTIONAL_EVALUATION_RETROSPECTIVE_20260828.md` | 功能评测阶段的问题发现方法、改正措施、复测效果、成果边界与方法论反思 |
| `docs/CORE_IMPLEMENTATION_HANDOFF_20260827.md` | C1/REL1故障位置、建议改法、实验来源与验收条件交接 |
| `docs/H1_PILOT_CHECKLIST_20260827.md` | H1隔离试采、认知访谈、匿名复核与正式采集放行门 |
| `docs/HUMAN_VALIDITY_MASTER_PLAN_20260828.md` | H1–H7定义、Human Reference证据门、当前覆盖和阶段路线 |
| `human_validity/MASTER_PLAN.yaml` | H1–H7机器可读覆盖状态、指标、缺口与声明边界 |
| `human_validity/h1_h4_v2/PREREGISTRATION.yaml` | H1/H4-v2目标人群、任务、远程采集、样本与分析草案 |
| `human_validity/h1_h4_v2/tasks/` | 四类非代码Task Card、八个任务表面及共同事件契约 |
| `human_validity/h1_h4_v2/{COGNITIVE_INTERVIEW.md,INTERNAL_PILOT_RUNBOOK.md,PILOT_PLAN.yaml,H4_CODEBOOK.yaml}` | 认知访谈、内部试采、固定分配与H4事件编码草案 |
| `human_validity/h1_h4_v2/synthetic_pilot/` | Wave 1合成试采生成器、机器可读结果与声明边界；不是真人或模型证据 |
| `releases/benchmark_v1_1_rule/`       | T4–T6规则校准的跨仓冻结清单与声明边界                  |
| `model_pilot/`                        | T4/T5统一模型预算、Prompt、原始响应与Seed-0 Runner      |
| `model_pilot/registrations/`          | T4真实模型重复实验的预注册设计与冻结输入哈希                  |
| `output/model_pilot_live_t4_control_consistency_glm52_*/` | GLM-5.2 T4重复运行的逐格证据与汇总       |
| `output/model_pilot_live_t4_v2_glm52_*/` | GLM-5.2 T4-v2预注册真实运行证据与审计简报       |
| `output/model_pilot_live_t4_v2_repeats_glm52_*/` | T4-v2 seed0/1/2稳定性证据             |
| `output/model_pilot_live_t5_minimal_glm52_*/` | T5最小真实政策因果链诊断证据                 |
| `output/model_pilot_live_t5_v2_glm52_*/` | T5-v2显式语义与binding目标资格诊断证据            |
| `output/model_pilot_live_t5_v3_repeats_glm52_*/` | T5-v3 eligibility-scope repeat 1/2证据      |
| `output/t5_v3_sealed_cross_model_*/` | T5-v3全新任务密封留出与GLM-5.2/gpt-5.4跨模型证据 |
| `output/t5_v3_expanded_3model_repeats_*/` | T5-v3四任务、三模型、seed0/1扩展证据与配额失败审计 |
| `exp_gm_t4_01/`                      | T4多跳传播、断桥与丢弃负控的规则校准                   |
| `exp_gm_t4_02/`                      | T4-v2显式注册传输协议、独立任务与规则校准               |
| `exp_gm_c1_0{4,5}/`                  | C1平台ID与权威当前规范的注册诊断回归                    |
| `exp_rel1_0{2,3}/`                   | REL1平台绑定、阶段分离与严格coverage回归                |
| `exp_gm_t5_01/`                      | T5无政策/真实政策/安慰剂政策因果链校准                 |
| `exp_gm_t5_02/`                      | T5-v2 absence/binding/nonbinding独立任务与评分       |
| `exp_gm_t5_03/`                      | T5-v3全局政策与逐居民执行权分离协议                    |
| `holdout_t5_v3/`                     | T5-v3三个密封新任务、Task Card与协议                  |
| `holdout_t5_v3_expanded/`            | T5-v3四个新增密封任务与三模型双重复协议                 |
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

GAWorld Evaluation Bridge已经形成一套从任务设计、测量校准、因果对照、规则评分到首错定位和修复回归的完整开发流程。T4-v1暴露隐式转发歧义后，T4-v2通过显式注册传输协议在GLM-5.2 seed0/1/2上稳定命中完整路径；T5-v1暴露政策语义混淆，T5-v2进一步暴露全局动作与居民动作的同名字段碰撞，T5-v3分离`policy_action`与唯一`resident_directive.action`后，在开发重复和第一批双模型密封留出中均完整通过。第二批四任务双重复中GLM-5.2与gpt-5.4继续完整通过；qwen3.7-plus因额度耗尽只形成部分证据，联合Gate按预注册判为失败并永久保留，项目不再续跑Qwen。两条修复链和这次运营失败共同说明JSON契约通过只是起点，字段命名、单一权威来源、因果对照、密封留出、固定失败分母和R3证据链仍不可省略。

下一阶段将围绕三条主线推进：在已经合并的核心修复上为C1/REL1做新编号、新表面的独立端到端回归；固定T4-v2协议补第二模型复测；保留当前三槽认知试采，并在H1/H4-v2目标人群、远程角色隔离、独立样本和分析方案冻结后才启动正式Human Reference。H2、H3、H5、H6、H7继续标记为`N/A`。
